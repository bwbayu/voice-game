import asyncio
import json
import logging
import os
import random
import threading

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from ai.intent_parser import IntentAction, IntentParser
from ai.mistral_client import MistralClient
from ai.narrator import Narrator
from ai.tts_client import TTSClient
from audio.audio_manager import AudioManager
from audio.deepgram_stt import DeepgramSTTWorker
from config import (
    GAME_STATE_FILE, MAP_FILE, SAMPLE_RATE, CHUNK_DURATION_MS, STT_MODEL,
    ITEMS_FILE, BOSSES_FILE, BOSSES_AUDIO_DIR, MONSTERS_FILE,
)
from game.monster_ai import MonsterManager
from game.combat import CombatManager, CombatResult
from game.dungeon_map import DungeonMap
from game.game_state import GameState
from ui.signals import AppSignals


# ── Worker Threads ─────────────────────────────────────────────────────────────

class NarrationWorker(QThread):
    """
    Runs Narrator.narrate_room() off the main thread.
    Emits finished(text, wav_path) on success, error(msg) on failure.
    Store as an instance attribute on GameController to prevent GC while running.
    """
    finished = pyqtSignal(str, str)   # (narration_text, wav_path)
    error    = pyqtSignal(str)

    def __init__(self, narrator: Narrator, room: dict,
                 named_exits: dict[str, str], previous_room_name: str | None,
                 room_items: list[str] | None = None):
        super().__init__()
        self._narrator           = narrator
        self._room               = room
        self._named_exits        = named_exits
        self._previous_room_name = previous_room_name
        self._room_items         = room_items

    def run(self) -> None:
        try:
            text, wav_path = self._narrator.narrate_room(
                self._room, self._named_exits, self._previous_room_name,
                self._room_items,
            )
            self.finished.emit(text, wav_path)
        except Exception as e:
            self.error.emit(str(e))


class WinNarrationWorker(QThread):
    """Generates victory narration for reaching the exit room."""
    finished = pyqtSignal(str, str)   # (text, wav_path)
    error    = pyqtSignal(str)

    def __init__(self, narrator: Narrator, room_name: str):
        super().__init__()
        self._narrator  = narrator
        self._room_name = room_name

    def run(self) -> None:
        try:
            text, wav_path = self._narrator.narrate_win(self._room_name)
            self.finished.emit(text, wav_path)
        except Exception as e:
            self.error.emit(str(e))


class SimpleNarrationWorker(QThread):
    """
    Generic worker that calls any zero-arg callable returning (text, wav_path).
    Used for boss entry, boss defeat, exit blocked, pickup narrations.
    """
    finished = pyqtSignal(str, str)
    error    = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            text, wav_path = self._fn()
            self.finished.emit(text, wav_path)
        except Exception as e:
            self.error.emit(str(e))


class RealtimeSTTWorker(QThread):
    """
    Streams microphone audio to Mistral's realtime transcription API.

    Lifecycle:
      1. Instantiated and started when the player presses Space.
      2. Opens a PyAudio input stream and yields chunks to Mistral.
      3. When stop_event is set (Space released), the async generator exits.
      4. Mistral finalises the transcription and emits TranscriptionStreamDone.
      5. transcript_ready is emitted with the full text.

    Uses threading.Event (not asyncio.Event) because it is set from the
    main Qt thread — threading.Event.is_set() is safe under Python's GIL.
    """
    transcript_delta = pyqtSignal(str)   # live partial text for UI display
    transcript_ready = pyqtSignal(str)   # final complete transcript
    error            = pyqtSignal(str)

    def __init__(self, api_key: str, stop_event: threading.Event):
        super().__init__()
        self._api_key    = api_key
        self._stop_event = stop_event

    def run(self) -> None:
        asyncio.run(self._stream())

    async def _stream(self) -> None:
        from mistralai import Mistral
        from mistralai.models import (
            AudioFormat,
            TranscriptionStreamTextDelta,
            TranscriptionStreamDone,
            RealtimeTranscriptionError,
        )
        try:
            from mistralai.extra.realtime import UnknownRealtimeEvent
            _has_unknown = True
        except ImportError:
            _has_unknown = False

        client       = Mistral(api_key=self._api_key)
        audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE)
        full_text    = ""

        try:
            async for event in client.audio.realtime.transcribe_stream(
                audio_stream=self._iter_microphone(),
                model=STT_MODEL,
                audio_format=audio_format,
            ):
                if isinstance(event, TranscriptionStreamTextDelta):
                    full_text += event.text
                    self.transcript_delta.emit(event.text)
                elif isinstance(event, TranscriptionStreamDone):
                    break
                elif isinstance(event, RealtimeTranscriptionError):
                    self.error.emit(f"Realtime STT error: {event}")
                    return
        except Exception as e:
            self.error.emit(str(e))
            return

        self.transcript_ready.emit(full_text)

    async def _iter_microphone(self):
        import pyaudio
        p             = pyaudio.PyAudio()
        chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=chunk_samples,
            )
        except Exception as e:
            self.error.emit(f"PyAudio open failed: {e}")
            p.terminate()
            return

        loop = asyncio.get_running_loop()
        try:
            while not self._stop_event.is_set():
                data = await loop.run_in_executor(
                    None, stream.read, chunk_samples, False
                )
                yield data
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()


# ── GameController ─────────────────────────────────────────────────────────────

class GameController(QObject):
    """
    Central orchestrator. Instantiated on the main thread.
    Owns all subsystem instances and manages the high-level game loop.

    All public methods (start_game, on_recording_started, on_recording_stopped)
    are called from the main thread.
    All signal slots (_on_narration_done, _handle_action, etc.) run on the
    main thread via Qt's auto-queued connection.
    """

    def __init__(self, signals: AppSignals):
        super().__init__()
        self._signals = signals

        # ── Data layer ──────────────────────────────────────────────────
        self._dungeon = DungeonMap(MAP_FILE)
        self._state   = GameState(GAME_STATE_FILE)

        # ── Item / boss / monster registries ────────────────────────────
        self._item_registry: dict[str, dict] = {
            i["id"]: i for i in json.loads(ITEMS_FILE.read_text())["items"]
        }
        self._boss_registry: dict[str, dict] = {
            b["id"]: b for b in json.loads(BOSSES_FILE.read_text())["bosses"]
        }
        self._monster_registry: dict[str, dict] = {
            m["id"]: m for m in json.loads(MONSTERS_FILE.read_text())["monsters"]
        }

        # ── AI layer ────────────────────────────────────────────────────
        self._mistral       = MistralClient()
        self._tts           = TTSClient()
        self._narrator      = Narrator(self._mistral, self._tts)
        self._intent_parser = IntentParser(self._mistral)

        # ── Combat layer ─────────────────────────────────────────────────
        self._combat_manager            = CombatManager()
        self._monster_manager           = MonsterManager()
        self._in_combat:  bool          = False
        self._current_enemy: dict | None = None   # enemy dict + current_hp
        self._enemy_type:   str | None   = None   # "boss" | "monster"
        self._last_attack_item_id: str   = ""

        # ── Audio layer ─────────────────────────────────────────────────
        self._audio = AudioManager()

        # ── Worker thread references ─────────────────────────────────────
        # Stored as attrs to prevent Python GC-ing threads while they run.
        self._narration_worker: QThread | None = None
        self._stt_worker: RealtimeSTTWorker | None = None
        self._stt_stop_event: threading.Event | None = None

        # ── Narration context ─────────────────────────────────────────────
        self._previous_room_name: str | None = None

        # ── Recording guard ───────────────────────────────────────────────
        # Prevents starting a new recording while one is in progress.
        self._is_recording = False

        # ── Validate boss audio ───────────────────────────────────────────
        self._validate_boss_audio()

        # ── Scatter items on first run ────────────────────────────────────
        if self._state.needs_item_scatter():
            self._scatter_items()

        # Start background audio (gracefully skips if file is absent)
        self._audio.play_bg("normal")

    # ── Public API ────────────────────────────────────────────────────────────

    def reset_game_state(self) -> None:
        """Reset to defaults on clean exit — next launch will re-scatter everything."""
        self._state.reset()

    def start_game(self) -> None:
        """
        Called once from main.py via QTimer after the event loop starts.
        Emits initial state and triggers narration for the starting room.
        If the saved state puts the player inside an uncleared boss room,
        combat is resumed immediately.
        """
        self._emit_state()
        self._emit_room_items()
        self._emit_inventory()

        if self._state.needs_monster_scatter():
            self._scatter_monsters()

        self._emit_map()

        room_id = self._state.current_room_id
        boss_id = self._dungeon.get_boss_id(room_id)
        if boss_id and not self._state.is_boss_cleared(boss_id):
            self._start_combat(boss_id, room_id)
        else:
            self._trigger_narration()

    def on_recording_started(self) -> None:
        """Called from MainWindow.keyPressEvent when Space is pressed."""
        if self._is_recording:
            return
        self._is_recording = True
        self._stt_stop_event = threading.Event()
        # self._stt_worker = RealtimeSTTWorker(self._mistral.api_key, self._stt_stop_event)  # Mistral STT (kept for reference)
        self._stt_worker = DeepgramSTTWorker(self._stt_stop_event)
        self._stt_worker.transcript_delta.connect(self._on_transcript_delta)
        self._stt_worker.transcript_ready.connect(self._on_transcript_ready)
        self._stt_worker.error.connect(self._on_stt_error)
        self._stt_worker.start()
        self._signals.listening_started.emit()

    def on_recording_stopped(self) -> None:
        """Called from MainWindow.keyReleaseEvent when Space is released."""
        if not self._is_recording:
            return
        self._is_recording = False
        if self._stt_stop_event:
            self._stt_stop_event.set()   # signals the async generator to stop
        self._signals.processing_started.emit()

    # ── State helpers ─────────────────────────────────────────────────────────

    def _emit_state(self) -> None:
        """Build and emit the state_updated payload for the UI."""
        room_id = self._state.current_room_id
        room    = self._dungeon.get_room(room_id)
        raw_exits = self._dungeon.get_exits(room_id)   # {direction: room_id}
        exits = {
            direction: self._dungeon.get_room(target_id)["name"]
            for direction, target_id in raw_exits.items()
        }   # {direction: room_name}
        payload = {
            "room": room,
            "exits": exits,
            "player": {
                "current_room": room_id,
                "hp":           self._state.hp,
                "max_hp":       self._state.max_hp,
                "inventory":    self._state.inventory,
            },
        }
        self._signals.state_updated.emit(payload)

    def _emit_room_items(self) -> None:
        """Emit room_items_changed for the current room."""
        room_id = self._state.current_room_id
        self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))

    def _emit_inventory(self) -> None:
        """Emit inventory_updated with current equipment payload."""
        self._signals.inventory_updated.emit(self._equipment_payload())

    def _emit_map(self) -> None:
        """Emit full map state: player location, items, monsters, boss status per room."""
        monster_positions = self._state.get_monster_positions()
        monsters_by_room: dict[str, list[str]] = {}
        for mid, rid in monster_positions.items():
            monsters_by_room.setdefault(rid, []).append(mid)

        unlocked = set(self._state.unlocked_rooms)
        rooms_payload: dict[str, dict] = {}

        for room_id in self._dungeon.all_room_ids:
            item_names = [
                self._item_registry[iid]["name"]
                for iid in self._state.get_room_items(room_id)
                if iid in self._item_registry
            ]
            monster_names = [
                self._monster_registry[mid]["name"]
                for mid in monsters_by_room.get(room_id, [])
                if mid in self._monster_registry
            ]
            boss_id      = self._dungeon.get_boss_id(room_id)
            boss_name    = self._boss_registry[boss_id]["name"] if boss_id else None
            boss_cleared = self._state.is_boss_cleared(boss_id) if boss_id else False
            is_locked    = self._dungeon.is_locked(room_id) and room_id not in unlocked

            rooms_payload[room_id] = {
                "items":        item_names,
                "monsters":     monster_names,
                "boss":         boss_name,
                "boss_cleared": boss_cleared,
                "locked":       is_locked,
            }

        self._signals.map_state_changed.emit({
            "player_room": self._state.current_room_id,
            "rooms":       rooms_payload,
        })

    def _equipment_payload(self) -> dict:
        """Build the dict payload for inventory_updated: {equipped, bag}."""
        eq_ids = self._state.equipped
        equipped_dicts = {
            slot: (self._item_registry[iid] if iid and iid in self._item_registry else None)
            for slot, iid in eq_ids.items()
        }
        bag_dicts = [
            self._item_registry[iid] for iid in self._state.bag
            if iid in self._item_registry
        ]
        return {"equipped": equipped_dicts, "bag": bag_dicts}

    def _inventory_as_dicts(self) -> list[dict]:
        """Flat list of all carried items — used for intent parser context only."""
        return [self._item_registry[iid] for iid in self._state.inventory
                if iid in self._item_registry]

    def _room_items_as_dicts(self, room_id: str) -> list[dict]:
        return [self._item_registry[iid] for iid in self._state.get_room_items(room_id)
                if iid in self._item_registry]

    # ── Item scatter ──────────────────────────────────────────────────────────

    def _scatter_items(self) -> None:
        """Distribute items randomly among eligible rooms (not home/boss/exit)."""
        eligible = [
            r for r in self._dungeon.all_room_ids
            if self._dungeon.get_room(r)["type"] not in ("home", "boss", "exit")
        ]
        if not eligible:
            return
        items = [iid for iid, item in self._item_registry.items() if item.get("scatter", True)]
        random.shuffle(items)
        for i, item_id in enumerate(items):
            room = eligible[i % len(eligible)]
            current = self._state.get_room_items(room)
            self._state.set_room_items(room, current + [item_id])
        self._state.save()
        self._emit_map()
        logging.info(
            f"GameController: scattered {len(items)} items across {len(eligible)} rooms."
        )

    def _scatter_monsters(self) -> None:
        """Place all monsters into random eligible rooms (type == 'normal')."""
        monster_ids = list(self._monster_registry.keys())
        self._monster_manager.scatter(monster_ids, self._dungeon, self._state)
        self._state.save()
        self._emit_map()
        logging.info(f"GameController: scattered monsters {monster_ids}")

    # ── Boss audio validation ─────────────────────────────────────────────────

    def _validate_boss_audio(self) -> None:
        for boss in self._boss_registry.values():
            for skill in boss["skills"]:
                path = BOSSES_AUDIO_DIR / boss["id"] / f"{skill['id']}.wav"
                if not path.exists():
                    logging.warning(
                        f"Boss audio missing: {path}  →  "
                        f"run scripts/pregenerate_boss_audio.py"
                    )

    # ── Narration triggers ────────────────────────────────────────────────────

    def _trigger_narration(self) -> None:
        """Spawn a NarrationWorker for the current room."""
        self._signals.narration_started.emit()
        room_id     = self._state.current_room_id
        room        = self._dungeon.get_room(room_id)
        named_exits = self._dungeon.get_named_exits(room_id)
        room_item_names = [
            self._item_registry[iid]["name"]
            for iid in self._state.get_room_items(room_id)
            if iid in self._item_registry
        ]

        self._narration_worker = NarrationWorker(
            self._narrator, room, named_exits, self._previous_room_name,
            room_item_names or None,
        )
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_win_narration(self, room_name: str) -> None:
        """Spawn a WinNarrationWorker for the exit room."""
        self._signals.narration_started.emit()
        self._narration_worker = WinNarrationWorker(self._narrator, room_name)
        self._narration_worker.finished.connect(self._on_win_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_boss_entry_narration(self, boss_id: str, room_id: str) -> None:
        """Spawn narration for entering a boss room."""
        self._signals.narration_started.emit()
        boss = self._boss_registry[boss_id]
        room = self._dungeon.get_room(room_id)
        prev = self._previous_room_name

        def fn():
            return self._narrator.narrate_boss_entry(boss["name"], room, prev)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_boss_entry_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_combat_round_narration(
        self, result: CombatResult, enemy_hp: int, player_hp: int
    ) -> None:
        """Spawn narration for a combat round result."""
        self._signals.narration_started.emit()
        enemy     = self._current_enemy
        item_name = self._item_registry.get(
            self._last_attack_item_id, {"name": "weapon"}
        )["name"]

        def fn():
            return self._narrator.narrate_combat_round(
                boss_name=enemy["name"],
                item_name=item_name,
                player_damage=result.player_damage,
                skill_name=result.skill_name,
                boss_damage=result.boss_damage,
                player_hp=player_hp,
                boss_hp=enemy_hp,
            )

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_boss_defeat_narration(self) -> None:
        """Spawn boss defeat narration."""
        self._signals.narration_started.emit()
        boss_name = self._current_enemy["name"]

        def fn():
            return self._narrator.narrate_boss_defeat(boss_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_boss_defeat_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_exit_blocked_narration(self) -> None:
        """Spawn exit blocked narration."""
        self._signals.narration_started.emit()

        def fn():
            return self._narrator.narrate_exit_blocked()

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_pickup_narration(self, item_name: str) -> None:
        """Spawn pickup narration."""
        self._signals.narration_started.emit()
        room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

        def fn():
            return self._narrator.narrate_pickup(item_name, room_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    # ── Narration slots ───────────────────────────────────────────────────────

    def _on_narration_done(self, text: str, wav_path: str) -> None:
        """Play the TTS clip. Schedule temp file deletion after 30 s."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_win_narration_done(self, text: str, wav_path: str) -> None:
        """Emit game_won so the UI can show the victory dialog."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        room_id   = self._state.current_room_id
        room_name = self._dungeon.get_room(room_id)["name"]
        self._signals.game_won.emit(room_name, wav_path)
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_boss_entry_narration_done(self, text: str, wav_path: str) -> None:
        """After boss entry narration, emit combat_started to show HP in UI."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        enemy = self._current_enemy
        self._signals.combat_started.emit({
            "name":          enemy["name"],
            "player_hp":     self._state.hp,
            "player_max_hp": self._state.max_hp,
            "enemy_hp":      enemy["current_hp"],
            "enemy_max_hp":  enemy["max_hp"],
        })
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_boss_defeat_narration_done(self, text: str, wav_path: str) -> None:
        """After boss defeat narration, emit combat_ended and re-enable movement."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        self._signals.combat_ended.emit()
        self._in_combat      = False
        self._current_enemy  = None
        self._enemy_type     = None
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_narration_error(self, msg: str) -> None:
        self._signals.narration_finished.emit()
        self._signals.error_occurred.emit(f"Narration failed: {msg}")
        logging.error(f"GameController: narration error — {msg}")

    # ── STT / intent slots ────────────────────────────────────────────────────

    def _on_transcript_delta(self, text: str) -> None:
        self._signals.transcript_delta.emit(text)

    def _on_transcript_ready(self, transcript: str) -> None:
        logging.debug(f"GameController: transcript='{transcript}'")

        room_id    = self._state.current_room_id
        exits      = self._dungeon.get_exit_names(room_id)
        weapons    = [i for i in self._inventory_as_dicts() if i.get("type") == "weapon"] if self._in_combat else []
        room_items = self._room_items_as_dicts(room_id)
        action = self._intent_parser.parse(transcript, exits, weapons, room_items)
        self._handle_action(action)

    def _on_stt_error(self, msg: str) -> None:
        self._signals.processing_finished.emit()
        self._signals.error_occurred.emit(f"Voice error: {msg}")
        logging.error(f"GameController: STT error — {msg}")

    # ── Action handler ────────────────────────────────────────────────────────

    def _handle_action(self, action: IntentAction) -> None:
        self._signals.processing_finished.emit()

        if action.action == "unknown":
            self._signals.error_occurred.emit(
                "Command not understood. Hold [SPACE] and try again."
            )
            return

        if action.action == "move":
            self._handle_move(action)
        elif action.action == "pickup":
            self._handle_pickup(action)
        elif action.action == "attack":
            self._handle_attack(action)

    def _handle_move(self, action: IntentAction) -> None:
        direction = action.direction
        room_id   = self._state.current_room_id
        target_id = self._dungeon.resolve_direction(room_id, direction)

        if target_id is None:
            self._signals.error_occurred.emit(
                f"You can't go '{direction}' from here."
            )
            return

        # Record current room name before moving (for narration context)
        self._previous_room_name = self._dungeon.get_room(room_id)["name"]

        # 1. Exit gate: all bosses must be defeated
        if self._dungeon.get_room(target_id)["type"] == "exit":
            boss_room_ids = self._dungeon.get_all_boss_room_ids()
            boss_ids = [self._dungeon.get_boss_id(r) for r in boss_room_ids]
            if not all(self._state.is_boss_cleared(b) for b in boss_ids if b):
                self._trigger_exit_blocked_narration()
                return

        # 2. Locked room check
        if (self._dungeon.is_locked(target_id)
                and target_id not in self._state.unlocked_rooms):
            required_key = self._dungeon.get_required_key(target_id)
            key_name = (
                self._item_registry.get(required_key, {}).get("name")
                if required_key else None
            )
            if required_key and required_key in self._state.inventory:
                # Player has the key — consume, unlock, move, then narrate unlock
                self._state.unlock_room(target_id)
                self._state.remove_from_inventory(required_key)
                self._state.move_player(target_id)
                self._state.set_last_action(f"unlocked and moved {direction}")
                self._state.save()
                self._emit_state()
                self._emit_room_items()
                self._signals.inventory_updated.emit(self._equipment_payload())
                self._emit_map()
                self._trigger_unlock_narration(target_id)
                return
            else:
                # Blocked — no key
                room_name = self._dungeon.get_room(target_id)["name"]
                self._trigger_locked_room_narration(room_name, key_name)
                return

        # 3. Boss room entry
        boss_id = self._dungeon.get_boss_id(target_id)
        if boss_id and not self._state.is_boss_cleared(boss_id):
            self._state.move_player(target_id)
            self._state.set_last_action(f"moved {direction}")
            self._state.save()
            self._emit_state()
            self._emit_room_items()
            self._emit_map()
            self._start_combat(boss_id, target_id)
            return

        # 4. Normal movement — cancel any active combat if the player flees
        if self._in_combat:
            self._in_combat     = False
            self._current_enemy = None
            self._enemy_type    = None
            self._signals.combat_ended.emit()

        self._state.move_player(target_id)
        self._state.set_last_action(f"moved {direction}")
        self._state.save()
        self._emit_state()
        self._emit_room_items()
        self._emit_map()

        new_room = self._dungeon.get_room(target_id)

        # 5. Win condition
        if new_room["type"] == "exit":
            self._trigger_win_narration(new_room["name"])
            return

        # 6. Move monsters + check encounter
        self._monster_manager.move_all(self._dungeon, self._state)
        self._state.save()
        self._emit_map()
        monsters_here = self._state.get_monsters_in_room(target_id)
        if monsters_here:
            self._start_monster_combat(monsters_here[0], target_id)
            return

        # 7. Normal room narration
        bg_track = new_room.get("type", "normal")
        if bg_track in ("home", "exit"):
            bg_track = "normal"
        self._audio.play_bg(bg_track)

        self._trigger_narration()

    def _handle_pickup(self, action: IntentAction) -> None:
        room_id    = self._state.current_room_id
        room_items = self._state.get_room_items(room_id)

        if action.item_id not in room_items:
            self._signals.error_occurred.emit("That item is not here.")
            return

        item      = self._item_registry.get(action.item_id)
        if not item:
            self._signals.error_occurred.emit("Unknown item.")
            return
        item_type = item.get("type")

        if item_type == "key":
            if not self._state.add_to_bag(action.item_id):
                self._signals.error_occurred.emit("Your bag is full.")
                return
            self._state.remove_room_item(room_id, action.item_id)
            self._state.save()
            self._signals.inventory_updated.emit(self._equipment_payload())
            self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
            self._emit_map()
            self._trigger_pickup_narration(item["name"])

        elif item_type in ("weapon", "armor"):
            slot   = item.get("slot")
            old_id = self._state.equip_item(slot, action.item_id)
            self._state.remove_room_item(room_id, action.item_id)
            if old_id and old_id != "bare_hands":
                # Drop displaced item back into the room
                self._state.set_room_items(
                    room_id, self._state.get_room_items(room_id) + [old_id]
                )
            self._state.save()
            self._signals.inventory_updated.emit(self._equipment_payload())
            self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
            self._emit_map()
            if old_id and old_id in self._item_registry:
                self._trigger_swap_narration(item["name"], self._item_registry[old_id]["name"])
            else:
                self._trigger_pickup_narration(item["name"])

        elif item_type == "potion":
            heal_amount = item.get("heal", 0)
            gained      = self._state.heal(heal_amount)
            self._state.remove_room_item(room_id, action.item_id)
            self._state.save()
            self._emit_state()
            self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
            self._emit_map()
            self._trigger_potion_narration(item["name"], gained, self._state.hp, self._state.max_hp)

        else:
            self._signals.error_occurred.emit("You can't pick that up.")

    def _handle_attack(self, action: IntentAction) -> None:
        if not self._in_combat or self._current_enemy is None:
            self._signals.error_occurred.emit("You are not in combat.")
            return
        if action.item_id not in self._state.inventory:
            self._signals.error_occurred.emit("You don't have that.")
            return

        item   = self._item_registry[action.item_id]
        self._last_attack_item_id = action.item_id
        result = self._combat_manager.resolve(item, self._current_enemy)

        new_enemy_hp  = max(0, self._current_enemy["current_hp"] - result.player_damage)
        defense       = self._compute_total_defense()
        new_player_hp = max(0, self._state.hp - max(0, result.boss_damage - defense))

        self._current_enemy["current_hp"]  = new_enemy_hp
        self._state._data["player"]["hp"]  = new_player_hp

        if self._enemy_type == "boss":
            self._state.set_boss_hp(self._current_enemy["id"], new_enemy_hp)
            # Play pre-generated skill stinger (boss only)
            taunt_wav = BOSSES_AUDIO_DIR / self._current_enemy["id"] / f"{result.skill_id}.wav"
            if taunt_wav.exists():
                self._audio.play_sfx(str(taunt_wav))
        else:
            self._state.set_monster_hp(self._current_enemy["id"], new_enemy_hp)

        self._state.save()

        self._signals.combat_updated.emit({
            "player_hp":     new_player_hp,
            "player_max_hp": self._state.max_hp,
            "enemy_hp":      new_enemy_hp,
            "enemy_max_hp":  self._current_enemy["max_hp"],
        })

        if new_enemy_hp <= 0:
            if self._enemy_type == "boss":
                self._finish_boss_combat()
            else:
                self._finish_monster_combat()
            return

        if new_player_hp <= 0:
            self._trigger_death_narration(self._current_enemy["name"])
            return

        self._trigger_combat_round_narration(result, new_enemy_hp, new_player_hp)

    # ── Combat helpers ────────────────────────────────────────────────────────

    def _start_combat(self, boss_id: str, room_id: str) -> None:
        """Enter combat with the given boss."""
        boss_data  = dict(self._boss_registry[boss_id])
        current_hp = self._state.get_boss_hp(boss_id, boss_data["max_hp"])
        boss_data["current_hp"] = current_hp
        self._current_enemy = boss_data
        self._enemy_type    = "boss"
        self._in_combat     = True

        self._audio.play_bg("boss")
        self._trigger_boss_entry_narration(boss_id, room_id)

    def _start_monster_combat(self, monster_id: str, room_id: str) -> None:
        """Enter combat with the given roaming monster."""
        monster_data  = dict(self._monster_registry[monster_id])
        current_hp    = self._state.get_monster_hp(monster_id, monster_data["max_hp"])
        monster_data["current_hp"] = current_hp
        self._current_enemy = monster_data
        self._enemy_type    = "monster"
        self._in_combat     = True

        self._audio.play_bg("boss")
        self._trigger_monster_encounter_narration(room_id)

    def _finish_boss_combat(self) -> None:
        """Called when boss HP reaches 0."""
        boss_id = self._current_enemy["id"]
        self._state.mark_boss_cleared(boss_id)
        self._state.save()
        self._emit_map()
        self._trigger_boss_defeat_narration()
        # _in_combat and _current_enemy are cleared in _on_boss_defeat_narration_done

    def _finish_monster_combat(self) -> None:
        """Called when monster HP reaches 0."""
        monster_id = self._current_enemy["id"]
        self._state.remove_monster(monster_id)
        self._state.save()
        self._emit_map()
        self._trigger_monster_defeat_narration()
        # _in_combat and _current_enemy are cleared in _on_monster_defeat_narration_done

    def restart_after_death(self) -> None:
        """Called by MainWindow after the Game Over dialog is dismissed."""
        self._state.reset()
        self._in_combat      = False
        self._current_enemy  = None
        self._enemy_type     = None
        self._previous_room_name = None

        self._emit_state()
        self._emit_inventory()
        self._emit_room_items()
        self._signals.combat_ended.emit()

        self._scatter_items()
        self._scatter_monsters()

        self._trigger_narration()

    def _compute_total_defense(self) -> int:
        """Sum of defense values across all equipped armor slots."""
        total = 0
        for slot, item_id in self._state.equipped.items():
            if slot != "weapon" and item_id and item_id in self._item_registry:
                total += self._item_registry[item_id].get("defense", 0)
        return total

    def _trigger_potion_narration(
        self, item_name: str, hp_gained: int, new_hp: int, max_hp: int
    ) -> None:
        """Spawn narration for drinking a healing potion."""
        self._signals.narration_started.emit()
        room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

        def fn():
            return self._narrator.narrate_potion_use(item_name, hp_gained, new_hp, max_hp, room_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_swap_narration(self, new_name: str, old_name: str) -> None:
        """Spawn narration for swapping one equipment piece for another."""
        self._signals.narration_started.emit()
        room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

        def fn():
            return self._narrator.narrate_swap(new_name, old_name, room_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    # ── Phase 3 narration triggers ────────────────────────────────────────────

    def _trigger_monster_encounter_narration(self, room_id: str) -> None:
        self._signals.narration_started.emit()
        monster   = self._current_enemy
        room      = self._dungeon.get_room(room_id)
        prev      = self._previous_room_name

        def fn():
            return self._narrator.narrate_monster_encounter(monster["name"], room, prev)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_monster_encounter_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_monster_defeat_narration(self) -> None:
        self._signals.narration_started.emit()
        monster_name = self._current_enemy["name"]

        def fn():
            return self._narrator.narrate_monster_defeat(monster_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_monster_defeat_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_death_narration(self, killer_name: str) -> None:
        self._signals.narration_started.emit()
        room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

        def fn():
            return self._narrator.narrate_death(room_name, killer_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_death_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_locked_room_narration(self, room_name: str, key_name: str | None) -> None:
        self._signals.narration_started.emit()

        def fn():
            return self._narrator.narrate_locked_room(room_name, key_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    def _trigger_unlock_narration(self, room_id: str) -> None:
        self._signals.narration_started.emit()
        room_name = self._dungeon.get_room(room_id)["name"]

        def fn():
            return self._narrator.narrate_unlock(room_name)

        self._narration_worker = SimpleNarrationWorker(fn)
        self._narration_worker.finished.connect(self._on_unlock_narration_done)
        self._narration_worker.error.connect(self._on_narration_error)
        self._narration_worker.start()

    # ── Phase 3 narration slots ────────────────────────────────────────────────

    def _on_monster_encounter_narration_done(self, text: str, wav_path: str) -> None:
        """After monster encounter narration, emit combat_started to show HP in UI."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        enemy = self._current_enemy
        self._signals.combat_started.emit({
            "name":          enemy["name"],
            "player_hp":     self._state.hp,
            "player_max_hp": self._state.max_hp,
            "enemy_hp":      enemy["current_hp"],
            "enemy_max_hp":  enemy["max_hp"],
        })
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_monster_defeat_narration_done(self, text: str, wav_path: str) -> None:
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        self._signals.combat_ended.emit()
        self._in_combat      = False
        self._current_enemy  = None
        self._enemy_type     = None
        self._audio.play_bg("normal")
        self._trigger_narration()
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_death_narration_done(self, text: str, wav_path: str) -> None:
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.game_over.emit(text, wav_path)
        # State reset handled by MainWindow._on_game_over → controller.restart_after_death()
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    def _on_unlock_narration_done(self, text: str, wav_path: str) -> None:
        """After unlock narration, narrate the newly entered room."""
        self._signals.narration_text.emit(text)
        self._audio.play_clip(wav_path)
        self._signals.narration_finished.emit()
        self._trigger_narration()
        _path = wav_path
        QTimer.singleShot(30_000, lambda: self._cleanup_wav(_path))

    # ── Cleanup ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cleanup_wav(path: str) -> None:
        """Delete a temp WAV file. Called via QTimer.singleShot."""
        if os.path.exists(path):
            try:
                os.unlink(path)
                logging.debug(f"GameController: deleted temp wav {path}")
            except OSError as e:
                logging.warning(f"GameController: could not delete {path}: {e}")
