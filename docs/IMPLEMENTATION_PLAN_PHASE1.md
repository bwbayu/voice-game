# Phase 1 Implementation Plan — Blind Dungeon

## Context
Full rewrite of the existing PyQt6 prototype into the PRD architecture for Phase 1.
Key decisions: hold-to-talk Space hotkey, English language, OpenAI TTS, Mistral Realtime STT
(streaming via pyaudio + asyncio), Pydantic structured output for intent parsing.

Changes from initial design:
- `mic_recorder.py` eliminated — pyaudio runs inline inside `RealtimeSTTWorker`
- `STTWorker` replaced by `RealtimeSTTWorker` using async streaming + threading.Event stop signal
- `IntentParser` uses `client.chat.parse()` with a Pydantic model (no JSON stripping hacks)
- requirements: remove sounddevice/soundfile, add pyaudio

---

## Implementation Order

1. `requirements.txt` — updated package list
2. `config.py` — all constants
3. `maps/dungeon_map.json` — rewrite in English
4. `state/game_state.json` — new schema
5. `game/game_state.py` + `game/dungeon_map.py` — data models
6. `ui/signals.py` — signal bus (everyone depends on this)
7. `audio/audio_manager.py` — pygame.mixer wrapper
8. `ai/mistral_client.py` + `ai/tts_client.py` — API wrappers
9. `ai/prompts.py` — prompt functions
10. `ai/intent_parser.py` — Pydantic structured intent parsing
11. `ai/narrator.py` — LLM → TTS orchestration
12. `game/game_controller.py` — hub + QThread workers
13. `ui/game_view.py` + `ui/main_window.py` — UI
14. `main.py` — entry point

All `__init__.py` files created empty alongside each package's first file.

---

## Folder Structure

```
mistral-hackathon/
├── main.py                    REWRITE
├── config.py                  NEW
├── requirements.txt           UPDATE
├── game/
│   ├── __init__.py
│   ├── game_controller.py     hub + QThread workers
│   ├── game_state.py          data model + JSON save/load
│   └── dungeon_map.py         graph wrapper
├── ai/
│   ├── __init__.py
│   ├── prompts.py             all LLM prompt functions
│   ├── mistral_client.py      Mistral chat wrapper
│   ├── tts_client.py          OpenAI TTS wrapper
│   ├── intent_parser.py       Pydantic structured intent parsing
│   └── narrator.py            orchestrates LLM → TTS pipeline
├── audio/
│   ├── __init__.py
│   ├── audio_manager.py       pygame.mixer wrapper
│   └── bg/                    background audio assets (optional)
├── ui/
│   ├── __init__.py
│   ├── signals.py             AppSignals (QObject)
│   ├── game_view.py           room display widget
│   └── main_window.py         QMainWindow + key events
├── maps/
│   └── dungeon_map.json       REWRITE in English
└── state/
    └── game_state.json        NEW (replaces player_state.json)
```

Note: `audio/mic_recorder.py` is removed. PyAudio recording is inline in `RealtimeSTTWorker`.

---

## File Specifications

### `requirements.txt`
```
mistralai
python-dotenv
openai
PyQt6
pyaudio
numpy
pygame
```
Removed: `sounddevice`, `soundfile`. Added: `pyaudio`.

---

### `config.py`
```python
from pathlib import Path

ROOT_DIR        = Path(__file__).parent
MAPS_DIR        = ROOT_DIR / "maps"
STATE_DIR       = ROOT_DIR / "state"
AUDIO_DIR       = ROOT_DIR / "audio" / "bg"
MAP_FILE        = MAPS_DIR / "dungeon_map.json"
GAME_STATE_FILE = STATE_DIR / "game_state.json"

# Audio recording
SAMPLE_RATE          = 16000    # Hz — required by Mistral realtime
CHUNK_DURATION_MS    = 480      # ms per audio chunk
BG_VOLUME            = 0.4

# TTS (OpenAI)
TTS_MODEL   = "tts-1"
TTS_VOICE   = "onyx"
TTS_FORMAT  = "wav"

# LLM (Mistral)
LLM_MODEL      = "mistral-large-latest"
INTENT_MODEL   = "ministral-8b-latest"  # small model is sufficient for intent parsing
STT_MODEL      = "voxtral-mini-transcribe-realtime-2602"

INVENTORY_CAP = 8

# UI colors
BG_COLOR     = "#1a1a2e"
TEXT_COLOR   = "#e0e0e0"
ACCENT_COLOR = "#c0a060"
STATUS_COLOR = "#80c080"
```

---

### `maps/dungeon_map.json` (full content)
```json
{
  "map_id": "default_dungeon",
  "theme": "dungeon",
  "rooms": {
    "home": {
      "id": "home", "type": "home",
      "name": "The Dungeon Gate",
      "description_hint": "rusted iron door, flickering torch sconces, ancient warning carved in stone, damp stone walls",
      "exits": { "left": "a", "right": "b" }
    },
    "a": {
      "id": "a", "type": "normal",
      "name": "Hall of Fallen Warriors",
      "description_hint": "skeletal soldiers in rusted armor leaning against walls, a stone table with a faded dungeon map, four doorways",
      "exits": { "back": "home", "north": "b", "south": "boss", "down": "t" }
    },
    "b": {
      "id": "b", "type": "normal",
      "name": "The Forbidden Library",
      "description_hint": "tall wooden shelves packed with black leather-bound books, some volumes trembling on their own, a nearly-spent candle on a reading desk",
      "exits": { "back": "home", "west": "a", "down": "boss" }
    },
    "boss": {
      "id": "boss", "type": "boss",
      "name": "The Guardian's Throne",
      "description_hint": "vaulted chamber with a ceiling lost in darkness, obsidian throne surrounded by massive claw marks, five passages leading outward",
      "exits": { "north": "a", "northeast": "b", "west": "c", "east": "d", "down": "t" }
    },
    "c": {
      "id": "c", "type": "normal",
      "name": "The Underground Prison",
      "description_hint": "rows of rusted iron cells along a narrow corridor, tally marks scratched into walls, smell of rot and dripping water",
      "exits": { "east": "boss", "down": "t" }
    },
    "d": {
      "id": "d", "type": "normal",
      "name": "The Forgotten Armory",
      "description_hint": "racks of broken swords and shattered shields, a small iron chest with a red wax seal untouched in the far corner",
      "exits": { "down": "t" }
    },
    "t": {
      "id": "t", "type": "exit",
      "name": "Chamber of the Dark Core",
      "description_hint": "deepest chamber, black crystal floor reflecting slightly wrong shadows, a stone altar at the centre with a pulsing red crystal beating like a heart",
      "exits": { "upper-west": "boss", "north": "c", "northeast": "d", "upper-east": "a" }
    }
  }
}
```

Room `t` → `type: "exit"` = Phase 1 win condition. Room `boss` → `type: "boss"` but Phase 1 does not gate entry (Phase 2 adds that).

---

### `state/game_state.json` (initial content)
```json
{
  "player": {
    "current_room": "home",
    "hp": 100, "max_hp": 100,
    "inventory": [],
    "last_action": "game started"
  },
  "world": {
    "cleared_bosses": [],
    "room_items": {},
    "monster_positions": {},
    "unlocked_rooms": []
  },
  "meta": { "theme": "dungeon", "difficulty": "medium", "session_start": null }
}
```
Create `state/` directory before writing.

---

### `game/game_state.py`
Class `GameState`:
- `load()` — reads JSON; sets `session_start` if null; creates file from defaults if absent (first run)
- `save()` — atomic write: write to `.tmp` then `os.replace()` (Windows-safe)
- Properties: `current_room_id`, `hp`, `inventory`
- Mutations: `move_player(target_id)`, `set_last_action(desc)`
- `to_dict()` → full snapshot for LLM prompt context

---

### `game/dungeon_map.py`
Class `DungeonMap`:
- `_load(map_file)` — validate ≥1 "home" and ≥1 "exit" room exist
- `get_room(room_id)` → dict
- `get_exits(room_id)` → `{direction: room_id}`
- `get_exit_names(room_id)` → `list[str]` (direction strings only, for IntentParser)
- `resolve_direction(from_id, direction)` → `str | None`
- `get_room_type(room_id)` → str

---

### `ui/signals.py`
```python
class AppSignals(QObject):
    narration_started    = pyqtSignal()
    narration_finished   = pyqtSignal()
    state_updated        = pyqtSignal(dict)    # {room, exits, player}
    listening_started    = pyqtSignal()
    transcript_delta     = pyqtSignal(str)     # live partial transcription text
    processing_started   = pyqtSignal()
    processing_finished  = pyqtSignal()
    error_occurred       = pyqtSignal(str)
    game_won             = pyqtSignal(str, str) # (room_name, wav_path)
```
`transcript_delta` allows GameView to show live transcription while the user speaks.
Must be instantiated on the main thread before any workers start.

---

### `audio/audio_manager.py`
Class `AudioManager`:
- `__init__()` — `pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)`
- `play_bg(track_name)` — load `audio/bg/{track_name}.mp3`; graceful skip with log warning if absent
- `play_clip(file_path)` — load as `pygame.mixer.Sound`, play on Channel 1; stop previous clip first
- `stop_all()` — stop music + channel 1
- `is_clip_playing()` → bool

---

### `ai/mistral_client.py`
Class `MistralClient`:
- `__init__()` — `Mistral(api_key=os.getenv("MISTRAL_API_KEY"))`
- `complete(system, user)` → str — chat completion only
- Note: No `transcribe()` method. Realtime STT is handled inline in `RealtimeSTTWorker`
  with its own Mistral client instance.

---

### `ai/tts_client.py`
Class `TTSClient`:
- `__init__()` — `OpenAI(api_key=os.getenv("OPENAI_API_KEY"))`
- `speak(text)` → str (wav path)
  ```python
  response = self._client.audio.speech.create(
      model=TTS_MODEL, voice=TTS_VOICE, input=text, response_format="wav"
  )
  response.stream_to_file(tmp.name)
  return tmp.name
  ```

---

### `ai/prompts.py`
All prompt functions (no LLM calls here):
- `build_narration_system_prompt()` → str
- `build_narration_user_prompt(room_name, description_hint, exits: {dir→room_name}, previous_room_name)` → str
- `build_intent_system_prompt()` → str — instructs LLM to extract direction matching provided options
- `build_intent_user_prompt(transcript, available_directions: list[str])` → str
- `build_win_narration_user_prompt(room_name)` → str

---

### `ai/intent_parser.py`
Uses Pydantic + `client.chat.parse()` — clean, no markdown stripping needed.

```python
from pydantic import BaseModel
from typing import Literal, Optional

class IntentAction(BaseModel):
    action: Literal["move", "unknown"]
    direction: Optional[str] = None   # only when action == "move"

class IntentParser:
    def parse(self, transcript: str, available_directions: list[str]) -> IntentAction:
        if not transcript.strip():
            return IntentAction(action="unknown")
        try:
            response = self._mistral_client.chat.parse(
                model=INTENT_MODEL,
                messages=[
                    {"role": "system", "content": build_intent_system_prompt()},
                    {"role": "user",   "content": build_intent_user_prompt(transcript, available_directions)}
                ],
                response_format=IntentAction,
                max_tokens=64,
                temperature=0
            )
            result = response.choices[0].message.parsed
        except Exception as e:
            logging.warning(f"IntentParser: {e}")
            return IntentAction(action="unknown")

        # Validate direction matches a real exit
        if result.action == "move" and result.direction not in available_directions:
            return IntentAction(action="unknown")
        return result
```

Note: Verify `client.chat.parse` exists:
`python -c "from mistralai import Mistral; print(hasattr(Mistral(api_key='x').chat, 'parse'))"`

---

### `ai/narrator.py`
Class `Narrator`:
- `narrate_room(room, exits: {dir→room_name}, previous_room_name)` → `(text, wav_path)` — blocking, must run in thread
- `narrate_win(room_name)` → `(text, wav_path)`

---

### `game/game_controller.py`

#### `NarrationWorker(QThread)`
```
Signals: finished(str, str) = (text, wav_path), error(str)
run(): narrator.narrate_room() or narrate_win() → emit
```

#### `WinNarrationWorker(QThread)`
```
Same as NarrationWorker but calls narrator.narrate_win()
```

#### `RealtimeSTTWorker(QThread)`
Core new class — streams mic audio to Mistral realtime API:

```python
class RealtimeSTTWorker(QThread):
    transcript_delta = pyqtSignal(str)   # live partial text
    transcript_ready = pyqtSignal(str)   # final complete transcript
    error            = pyqtSignal(str)

    def __init__(self, api_key: str, stop_event: threading.Event):
        super().__init__()
        self._api_key    = api_key
        self._stop_event = stop_event   # set by main thread on Space release

    def run(self):
        asyncio.run(self._stream())

    async def _stream(self):
        client = Mistral(api_key=self._api_key)
        audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE)
        full_text = ""
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
                self.error.emit(str(event)); return
        self.transcript_ready.emit(full_text)

    async def _iter_microphone(self):
        import pyaudio
        p = pyaudio.PyAudio()
        chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                        input=True, frames_per_buffer=chunk_samples)
        loop = asyncio.get_running_loop()
        try:
            while not self._stop_event.is_set():
                data = await loop.run_in_executor(None, stream.read, chunk_samples, False)
                yield data
        finally:
            stream.stop_stream(); stream.close(); p.terminate()
```

`threading.Event` (not `asyncio.Event`) because it is set from the main Qt thread.
`is_set()` is thread-safe under Python's GIL.

#### `GameController(QObject)`
Key methods:
```python
def on_recording_started(self):
    self._stt_stop_event = threading.Event()
    self._stt_worker = RealtimeSTTWorker(MISTRAL_API_KEY, self._stt_stop_event)
    self._stt_worker.transcript_delta.connect(lambda t: self._signals.transcript_delta.emit(t))
    self._stt_worker.transcript_ready.connect(self._on_transcript_ready)
    self._stt_worker.error.connect(self._on_stt_error)
    self._stt_worker.start()
    self._signals.listening_started.emit()

def on_recording_stopped(self):
    if self._stt_stop_event:
        self._stt_stop_event.set()     # generator stops → Mistral finalises → transcript_ready
    self._signals.processing_started.emit()

def _on_transcript_ready(self, transcript):
    directions = self._dungeon.get_exit_names(self._state.current_room_id)
    action = self._intent_parser.parse(transcript, directions)
    self._handle_action(action)

def _handle_action(self, action: IntentAction):
    self._signals.processing_finished.emit()
    if action.action == "unknown":
        self._signals.error_occurred.emit("Command not understood. Try again."); return
    if action.action == "move":
        target_id = self._dungeon.resolve_direction(
            self._state.current_room_id, action.direction
        )
        if not target_id:
            self._signals.error_occurred.emit(f"Can't go {action.direction}."); return
        self._previous_room_name = self._dungeon.get_room(self._state.current_room_id)["name"]
        self._state.move_player(target_id); self._state.save()
        self._signals.state_updated.emit(self._build_state_payload())
        new_room = self._dungeon.get_room(target_id)
        if new_room["type"] == "exit":
            self._trigger_win_narration(new_room["name"]); return
        bg_track = new_room.get("type", "normal")
        if bg_track in ("home", "exit"): bg_track = "normal"
        self._audio.play_bg(bg_track)
        self._trigger_narration()
```

---

### `ui/game_view.py`
Dark-themed minimal widget (labels only, no buttons):
- `lbl_title` — "BLIND DUNGEON" (accent color, large)
- `lbl_room` — current room name
- `lbl_exits` — `[LEFT]  |  [RIGHT]`
- `lbl_live_transcript` — live partial transcription (shown while listening)
- `lbl_status` — current state text
- `lbl_hint` — "Hold [SPACE] to speak"

Methods: `update_state(payload)`, `set_status(text)`, `append_transcript_delta(text)`, `clear_transcript()`

---

### `ui/main_window.py`
Class `MainWindow(QMainWindow)`:
- Signal wiring in `_connect_signals()`
- `keyPressEvent`: Space + `not isAutoRepeat()` + `not self._recording` → `_recording=True`, clear transcript, `controller.on_recording_started()`
- `keyReleaseEvent`: Space + `not isAutoRepeat()` + `self._recording` → `_recording=False`, `controller.on_recording_stopped()`
- `_on_game_won(room_name, wav_path)`: `audio.play_clip(wav_path)`, QMessageBox victory
- `self.setFocus()` at end of `__init__`

---

### `main.py`
```python
app        = QApplication(sys.argv)
signals    = AppSignals()           # must be main thread
controller = GameController(signals)
window     = MainWindow(signals, controller)
window.show()
QTimer.singleShot(100, controller.start_game)  # after event loop starts
sys.exit(app.exec())
```

---

## Complete Data Flow

```
STARTUP
  GameController.__init__: loads map + state, audio.play_bg("normal")
  QTimer(100ms) → start_game()
    signals.state_updated → GameView updates room + exits
    NarrationWorker: Mistral LLM → OpenAI TTS → (text, wav_path)
    audio.play_clip(wav_path); signals.narration_finished → status "Ready"

HOLD-TO-TALK
  Space pressed → on_recording_started()
    threading.Event created; RealtimeSTTWorker.start()
      asyncio.run(_stream()):
        open pyaudio stream
        while not stop_event: read chunk → yield to Mistral realtime
        Mistral returns TranscriptionStreamTextDelta → transcript_delta emitted → live UI
        When stop_event set → generator exits → Mistral finalises
        TranscriptionStreamDone → transcript_ready emitted
    signals.listening_started → status "Listening..."

  Space released → on_recording_stopped()
    stop_event.set()
    signals.processing_started → status "Processing..."

  transcript_ready → _on_transcript_ready(transcript)
    IntentParser.parse() via client.chat.parse() → IntentAction(Pydantic)
    _handle_action(action):
      if move + valid direction:
        GameState.move_player() + save()
        signals.state_updated → GameView updates
        if type=="exit" → WinNarrationWorker → signals.game_won → QMessageBox
        else → NarrationWorker for new room
      if unknown → error_occurred → status shows message

WIN
  WinNarrationWorker: narrator.narrate_win() → (text, wav_path)
  signals.game_won(room_name, wav_path)
  MainWindow: audio.play_clip(wav_path); show QMessageBox with victory text
```

---

## Critical Gotchas

| # | Issue | Fix |
|---|---|---|
| 1 | key-repeat events on Windows | `event.isAutoRepeat()` guard in both keyPress/Release |
| 2 | Worker GC while running | Store as `self._stt_worker`, `self._narration_worker` on controller |
| 3 | Qt widget access from worker thread | Only emit pyqtSignals; slots run on main thread automatically |
| 4 | asyncio in QThread | `asyncio.run()` creates fresh event loop per call — valid in non-main threads |
| 5 | threading.Event cross-thread | Set from main Qt thread; `is_set()` check in async generator is GIL-safe |
| 6 | bg audio file missing | `play_bg()` checks `path.exists()` → log warning, return, no crash |
| 7 | `client.chat.parse()` availability | Verify: `python -c "from mistralai import Mistral; print(hasattr(Mistral(api_key='x').chat, 'parse'))"` |
| 8 | Realtime STT model name | Verify `voxtral-mini-transcribe-realtime-2602` against Mistral docs |
| 9 | `state/` directory creation | `STATE_DIR.mkdir(parents=True, exist_ok=True)` in GameState.__init__ |
| 10 | Atomic save on Windows | `os.replace()` not `os.rename()` |
| 11 | TTS wav cleanup | `QTimer.singleShot(30_000, lambda: os.unlink(wav_path))` after play_clip() |
| 12 | Window focus for key events | `window.setFocus()` + `window.activateWindow()` after show |
| 13 | Intent parsing during narration | Block Space key while narration is playing (add `_is_narrating` guard in controller) |

---

## Verification Steps

1. `pip install -r requirements.txt`
2. `python -c "from mistralai import Mistral; m=Mistral(api_key='x'); print(dir(m.audio.realtime))"` — verify realtime API path
3. `python -c "from mistralai import Mistral; print(hasattr(Mistral(api_key='x').chat, 'parse'))"` — verify structured output
4. `python main.py` — dark window opens, status "Narrating...", TTS audio plays for home room
5. Hold Space → "Listening..." + live transcript text appears; release → "Processing..."
6. Say "go left" or "move north" → room changes, new narration plays
7. Navigate to room `t` (Chamber of the Dark Core) → victory dialog appears
8. Say something gibberish → error message, player stays in current room
9. Verify `state/game_state.json` updates on disk after each successful move
