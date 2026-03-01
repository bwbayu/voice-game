# Phase 2.1 Implementation Plan — UI Polish + Deepgram STT + Intent Unification

## Context
Adjustments made after Phase 2 completion:
1. **Always-visible player HP bar** — player HP shown at all times, not just in combat
2. **Block weaponless attacks** — clear error if player tries to fight without weapons
3. **Shorter narration** — reduce all narration prompts to 1–2 sentences; brief exit/item mention
4. **Replace Mistral STT with Deepgram** — swap `RealtimeSTTWorker` for Deepgram live transcription (`DEEPGRAM_API_KEY` in env)
5. **Room background images** — use `bg_image` field from `dungeon_map.json`; all text labels get semi-transparent backgrounds for readability
6. **Unified intent parser** — replace three separate parsers (`parse`, `parse_combat`, `parse_pickup`) with a single `parse()` call that lets the LLM decide the action based on full game context
7. **Combat state restoration on load** — resume combat immediately if saved state has player inside an uncleared boss room

---

## Key Design Decisions

- **Single LLM intent call**: The LLM receives the full game context (exits, weapons, room items) in one call and returns the correct action + fields. No keyword matching; the LLM infers natural language intent. Three separate parsers replaced by one unified `parse()`.
- **Attack fallback**: If the LLM returns `action='attack'` but leaves `item_id=None`, the parser defaults to `weapons[0]` rather than rejecting the action as 'unknown'.
- **`DeepgramSTTWorker` in its own file**: `audio/deepgram_stt.py` is a clean module with no game logic. `RealtimeSTTWorker` remains in `game_controller.py` unchanged — only the instantiation line is commented out and replaced.
- **`transcript_delta` semantics**: Deepgram non-final results are full re-transcriptions (not incremental). `append_transcript_delta` uses **set** semantics (not append). A fresh `show_listening()` call clears the label on each new recording session.
- **Player HP always visible**: `lbl_player_hp` sits just below the title, always rendered. Updated from `state_updated` (room enter) and from `show_combat_status` (combat rounds). `lbl_combat` shows only boss HP.
- **Weapon check before LLM**: If no weapons in inventory when in combat, error is emitted immediately (no LLM call), reducing latency.
- **`max_hp` in state payload**: `_emit_state()` now includes `max_hp` so the HP label shows "HP: 80/100" from the first state emission.
- **Background images**: `GameView.paintEvent` draws the pixmap scaled to widget rect. Each label has `rgba(0,0,0,160)` background and padding ensuring readability on any image.
- **Combat restore on load**: `start_game()` checks if `current_room` is an uncleared boss room and calls `_start_combat()` instead of `_trigger_narration()`, restoring `_in_combat=True` and emitting proper combat signals.

---

## Implementation Order

1. `ai/prompts.py` — shorten narration prompts; add unified intent prompt pair
2. `config.py` — add `ASSETS_DIR`
3. `audio/deepgram_stt.py` (new file) — `DeepgramSTTWorker` class
4. `ui/game_view.py` — add `lbl_player_hp`, background image painting, label backgrounds; transcript set semantics
5. `game/game_controller.py` — add `max_hp` to state payload; weapon check; use `DeepgramSTTWorker`; unified intent parser call; combat restore on load
6. `ai/intent_parser.py` — replace three methods with single `parse()`; update imports
7. `requirements.txt` — add `deepgram-sdk`

---

## File Specifications

### 1. `ai/prompts.py`

**Narration system prompt** — changed to 1–2 sentences max:
```python
def build_narration_system_prompt() -> str:
    return (
        "You are a dungeon master narrating a blind dungeon game. "
        "The player cannot see anything — your words are their only perception. "
        "Be atmospheric and concise (1–2 sentences max). "
        "Mention each available exit direction and any visible items in one brief phrase each. "
        "Speak in second person: 'you see...', 'you hear...', 'you smell...'. "
        "Do not use markdown, lists, or formatting. Do not mention game mechanics or rules."
    )
```

**Narration user prompt** — appends brevity instruction:
```
"Keep the entire narration to 1–2 sentences. Each exit and item gets one brief phrase."
```

**Boss entry** — reduced to 2–3 sentences (was 4–6).
**Boss defeat** — reduced to 2 sentences (was 3–4).
**Exit blocked** — reduced to 1–2 sentences (was 2–3).
**Win narration** — reduced to 2 sentences (was 3–4).

**Unified intent prompts** (new):
```python
def build_unified_intent_system_prompt() -> str:
    return (
        "You are an intent parser for a voice-controlled dungeon game. "
        "Given a player's spoken command and the current game context, "
        "determine what the player wants to do. "
        "Possible actions: "
        "'move' — player wants to go somewhere, set direction to the exact exit string; "
        "'attack' — player wants to fight, set item_id to the weapon id to use "
        "(if no specific weapon is named, pick the most appropriate one or the first); "
        "'pickup' — player wants to take an item from the room, set item_id to the item id "
        "(use semantic matching — 'grab the glowing thing' might match 'Torch'); "
        "'unknown' — intent is completely unclear or unrelated to any available action. "
        "Infer intent from natural language — the player will not use exact keywords. "
        "'go for it', 'let's fight', 'hit it' are attack. "
        "'head north', 'try the left door' are move. "
        "'grab that', 'take the sword' are pickup. "
        "Only return 'unknown' if the speech has no plausible connection to any listed action. "
        "Output a structured JSON response only."
    )

def build_unified_intent_user_prompt(
    transcript: str,
    exits: list[str],
    weapons: list[dict],
    room_items: list[dict],
) -> str:
    exits_text   = ", ".join(f'"{d}"' for d in exits)         or "none"
    weapons_text = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in weapons
    ) or "none"
    items_text   = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in room_items
    ) or "none"
    return (
        f"Player said: \"{transcript}\". "
        f"Available exits: [{exits_text}]. "
        f"Weapons in inventory: [{weapons_text}]. "
        f"Items on the floor: [{items_text}]. "
        "What does the player want to do?"
    )
```

---

### 2. `config.py`

```python
ASSETS_DIR = ROOT_DIR / "assets"
```

---

### 3. `audio/deepgram_stt.py` (new file)

```python
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from config import CHUNK_DURATION_MS, SAMPLE_RATE

class DeepgramSTTWorker(QThread):
    """
    Streams microphone audio to Deepgram live transcription (SDK v6).
    Hold-to-talk: mic streams while Space held; stop_event set on release.
    Accumulates is_final=True transcripts; emits transcript_ready on close.
    transcript_delta carries the latest non-final partial (set semantics, not append).
    """
    transcript_delta = pyqtSignal(str)   # latest partial text for live display
    transcript_ready = pyqtSignal(str)   # final complete transcript on done
    error            = pyqtSignal(str)

    def __init__(self, stop_event: threading.Event):
        super().__init__()
        self._stop_event = stop_event
        self._final_text = ""

    def run(self) -> None:
        import pyaudio
        from deepgram import DeepgramClient
        from deepgram.core.events import EventType

        dg = DeepgramClient()   # reads DEEPGRAM_API_KEY from env
        p  = None

        try:
            with dg.listen.v1.connect(
                model="nova-3",
                language="en-US",
                encoding="linear16",
                sample_rate=SAMPLE_RATE,
                channels=1,
                interim_results="true",   # lowercase string — Deepgram rejects Python True
                endpointing=300,
            ) as conn:

                def on_message(message) -> None:
                    if getattr(message, "type", "") != "Results":
                        return
                    channel = getattr(message, "channel", None)
                    alts    = getattr(channel, "alternatives", []) if channel else []
                    text    = (alts[0].transcript if alts else "") or ""
                    if not text:
                        return
                    if getattr(message, "is_final", False):
                        self._final_text += text + " "
                    else:
                        self.transcript_delta.emit(text)

                conn.on(EventType.MESSAGE, on_message)
                conn.on(EventType.ERROR,   lambda error: self.error.emit(str(error)))

                listen_thread = threading.Thread(
                    target=conn.start_listening, daemon=True
                )
                listen_thread.start()

                chunk = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=chunk,
                )
                while not self._stop_event.is_set():
                    data = stream.read(chunk, exception_on_overflow=False)
                    conn.send_media(data)

                stream.stop_stream()
                stream.close()

                conn.send_finalize()
                listen_thread.join(timeout=3.0)
                conn.send_close_stream()

        except Exception as e:
            self.error.emit(str(e))
            return
        finally:
            if p:
                p.terminate()

        self.transcript_ready.emit(self._final_text.strip())
```

---

### 4. `ui/game_view.py`

**New imports**: `QPixmap`, `QPainter` from `PyQt6.QtGui`

**New instance var**: `self._bg_pixmap: QPixmap | None = None`

**New `lbl_player_hp` label** — inserted after title, always visible, styled with `STATUS_COLOR`.

**Semi-transparent background** on all labels: `background-color: rgba(0, 0, 0, 160); padding: 4px 8px; border-radius: 4px;`

**`paintEvent` override**:
```python
def paintEvent(self, event) -> None:
    if self._bg_pixmap:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._bg_pixmap)
    super().paintEvent(event)
```

**`update_bg_image(path)`**: loads `QPixmap`, sets `_bg_pixmap`, calls `self.update()`.

**`update_state(payload)`** — also updates player HP and background image from state.

**`update_player_hp(hp, max_hp)`** — direct HP update for combat rounds.

**`show_combat_status()`** — `lbl_combat` shows only boss HP; `lbl_player_hp` updated separately.

**`append_transcript_delta(text)`** — changed from append to set: `self.lbl_transcript.setText(text)`.

---

### 5. `ai/intent_parser.py`

Replaced three methods with a single `parse()`:

```python
class IntentAction(BaseModel):
    action:    Literal["move", "pickup", "get", "collect", "attack", "unknown"]
    direction: Optional[str] = None   # only set when action == "move"
    item_id:   Optional[str] = None   # only set when action == "pickup" or "attack"

class IntentParser:
    def parse(
        self,
        transcript: str,
        exits: list[str],
        weapons: list[dict],
        room_items: list[dict],
    ) -> IntentAction:
        if not transcript.strip():
            return IntentAction(action="unknown")

        system = build_unified_intent_system_prompt()
        user   = build_unified_intent_user_prompt(transcript, exits, weapons, room_items)

        try:
            result: IntentAction = self._client.parse(
                system_prompt=system,
                user_prompt=user,
                response_format=IntentAction,
                model=INTENT_MODEL,
                max_tokens=64,
                temperature=0,
            )
        except Exception as e:
            logging.warning(f"IntentParser: API call failed — {e}")
            return IntentAction(action="unknown")

        # Validate direction is a real exit
        if result.action == "move" and result.direction not in exits:
            return IntentAction(action="unknown")

        # Validate item_id is in the expected set
        valid_weapon_ids = {i["id"] for i in weapons}
        valid_item_ids   = {i["id"] for i in room_items}
        if result.action == "attack" and result.item_id not in valid_weapon_ids:
            # LLM recognized attack intent but didn't fill item_id — default to first weapon
            if weapons:
                result = IntentAction(action="attack", item_id=weapons[0]["id"])
            else:
                return IntentAction(action="unknown")
        if result.action == "pickup" and result.item_id not in valid_item_ids:
            return IntentAction(action="unknown")

        logging.debug(f"IntentParser: '{transcript}' → {result}")
        return result
```

---

### 6. `game/game_controller.py`

**Import**: `from audio.deepgram_stt import DeepgramSTTWorker`

**`_emit_state()`** — add `max_hp` to player payload:
```python
"player": {
    "current_room": room_id,
    "hp":           self._state.hp,
    "max_hp":       self._state.max_hp,
    "inventory":    self._state.inventory,
},
```

**`on_recording_started()`** — swap STT worker:
```python
# self._stt_worker = RealtimeSTTWorker(...)  # Mistral STT (kept for reference)
self._stt_worker = DeepgramSTTWorker(self._stt_stop_event)
```

**`start_game()`** — resume combat if loaded inside uncleared boss room:
```python
def start_game(self) -> None:
    self._emit_state()
    self._emit_room_items()
    self._emit_inventory()

    room_id = self._state.current_room_id
    boss_id = self._dungeon.get_boss_id(room_id)
    if boss_id and not self._state.is_boss_cleared(boss_id):
        self._start_combat(boss_id, room_id)
    else:
        self._trigger_narration()
```

**`_on_transcript_ready()`** — single unified parser call:
```python
def _on_transcript_ready(self, transcript: str) -> None:
    room_id    = self._state.current_room_id
    exits      = self._dungeon.get_exit_names(room_id) if not self._in_combat else []
    weapons    = [i for i in self._inventory_as_dicts() if i.get("type") == "weapon"] if self._in_combat else []
    room_items = self._room_items_as_dicts(room_id) if not self._in_combat else []

    if self._in_combat and not weapons:
        self._signals.processing_finished.emit()
        self._signals.error_occurred.emit("You have no weapons! Find a weapon before you can fight.")
        return

    action = self._intent_parser.parse(transcript, exits, weapons, room_items)
    self._handle_action(action)
```

---

### 7. `requirements.txt`

Added:
```
deepgram-sdk
```

---

## Bugs Fixed

### Intent parser returning 'unknown' for clear attack commands
- **Symptom**: `IntentParser.parse_combat: 'attack the boss' → action='unknown'`
- **Root cause**: Old `build_combat_intent_system_prompt` said "if no weapon is mentioned or the intent is unclear, set action to 'unknown'." LLM returned 'unknown' when no specific weapon was named.
- **Fix**: Unified prompt instructs LLM to pick the first weapon if attack intent is clear but no weapon is specified.

### `item_id=None` on attack despite weapons in inventory
- **Symptom**: `IntentParser: weapon id 'None' not in inventory — unknown`
- **Root cause**: LLM correctly identified `action='attack'` but left `item_id=None` in structured output.
- **Fix**: Validation layer defaults to `weapons[0]["id"]` when attack intent is confirmed but `item_id` is missing/invalid.

### `weapons=[]` despite having weapons in inventory when loading saved game
- **Symptom**: Empty weapons list printed; game treated player as not-in-combat.
- **Root cause**: `_in_combat` initializes to `False`. When game loads from saved state with `current_room: "boss"`, `start_game()` called `_trigger_narration()` only — `_start_combat()` was never called, so `_in_combat` stayed `False`.
- **Fix**: `start_game()` checks if current room is an uncleared boss room and calls `_start_combat()` to restore full combat state.

---

## Verification

1. Launch game → `lbl_player_hp` shows "HP: 100/100" immediately
2. Room bg image renders; text labels are readable over the image
3. Move to another room → bg image updates; player HP persists
4. Room narration is 1–2 sentences, mentions exits and items briefly
5. Enter boss room with no weapons → speak → "You have no weapons!" error, no LLM call
6. Pick up weapon, enter boss room → `lbl_combat` shows boss HP only; `lbl_player_hp` shows player HP
7. Say "attack", "go for it", "hit it" → attack triggers (LLM infers intent)
8. Say "head north", "let's go left" → move triggers
9. Say "grab that", "take the dagger" → pickup triggers
10. Load saved game with `current_room: "boss"` → combat resumes immediately
11. Deepgram live transcript updates during recording; final transcript emitted on Space release
