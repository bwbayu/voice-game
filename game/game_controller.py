import asyncio
import logging
import os
import threading

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from ai.intent_parser import IntentAction, IntentParser
from ai.mistral_client import MistralClient
from ai.narrator import Narrator
from ai.tts_client import TTSClient
from audio.audio_manager import AudioManager
from config import GAME_STATE_FILE, MAP_FILE, SAMPLE_RATE, CHUNK_DURATION_MS, STT_MODEL
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
                 named_exits: dict[str, str], previous_room_name: str | None):
        super().__init__()
        self._narrator           = narrator
        self._room               = room
        self._named_exits        = named_exits
        self._previous_room_name = previous_room_name

    def run(self) -> None:
        try:
            text, wav_path = self._narrator.narrate_room(
                self._room, self._named_exits, self._previous_room_name
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

        # ── AI layer ────────────────────────────────────────────────────
        self._mistral       = MistralClient()
        self._tts           = TTSClient()
        self._narrator      = Narrator(self._mistral, self._tts)
        self._intent_parser = IntentParser(self._mistral)

        # ── Audio layer ─────────────────────────────────────────────────
        self._audio = AudioManager()

        # ── Worker thread references ─────────────────────────────────────
        # Stored as attrs to prevent Python GC-ing threads while they run.
        self._narration_worker: NarrationWorker | WinNarrationWorker | None = None
        self._stt_worker: RealtimeSTTWorker | None = None
        self._stt_stop_event: threading.Event | None = None

        # ── Narration context ─────────────────────────────────────────────
        self._previous_room_name: str | None = None

        # ── Recording guard ───────────────────────────────────────────────
        # Prevents starting a new recording while one is in progress.
        self._is_recording = False

        # Start background audio (gracefully skips if file is absent)
        self._audio.play_bg("normal")

    # ── Public API ────────────────────────────────────────────────────────────

    def start_game(self) -> None:
        """
        Called once from main.py via QTimer after the event loop starts.
        Emits initial state and triggers narration for the starting room.
        """
        self._emit_state()
        self._trigger_narration()

    def on_recording_started(self) -> None:
        """Called from MainWindow.keyPressEvent when Space is pressed."""
        if self._is_recording:
            return
        self._is_recording = True
        self._stt_stop_event = threading.Event()
        self._stt_worker = RealtimeSTTWorker(
            self._mistral.api_key, self._stt_stop_event
        )
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
        exits   = self._dungeon.get_exits(room_id)
        payload = {
            "room": room,
            "exits": exits,
            "player": {
                "current_room": room_id,
                "hp":           self._state.hp,
                "inventory":    self._state.inventory,
            },
        }
        self._signals.state_updated.emit(payload)

    # ── Narration trigger ─────────────────────────────────────────────────────

    def _trigger_narration(self) -> None:
        """Spawn a NarrationWorker for the current room."""
        self._signals.narration_started.emit()
        room_id     = self._state.current_room_id
        room        = self._dungeon.get_room(room_id)
        named_exits = self._dungeon.get_named_exits(room_id)

        self._narration_worker = NarrationWorker(
            self._narrator, room, named_exits, self._previous_room_name
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

    def _on_narration_error(self, msg: str) -> None:
        self._signals.narration_finished.emit()
        self._signals.error_occurred.emit(f"Narration failed: {msg}")
        logging.error(f"GameController: narration error — {msg}")

    # ── STT / intent slots ────────────────────────────────────────────────────

    def _on_transcript_delta(self, text: str) -> None:
        self._signals.transcript_delta.emit(text)

    def _on_transcript_ready(self, transcript: str) -> None:
        logging.debug(f"GameController: transcript='{transcript}'")
        directions = self._dungeon.get_exit_names(self._state.current_room_id)
        action     = self._intent_parser.parse(transcript, directions)
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

            self._state.move_player(target_id)
            self._state.set_last_action(f"moved {direction}")
            self._state.save()
            self._emit_state()

            new_room = self._dungeon.get_room(target_id)

            # Check win condition
            if new_room["type"] == "exit":
                self._trigger_win_narration(new_room["name"])
                return

            # Switch background track by room type
            bg_track = new_room.get("type", "normal")
            if bg_track in ("home", "exit"):
                bg_track = "normal"
            self._audio.play_bg(bg_track)

            self._trigger_narration()

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
