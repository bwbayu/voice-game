# Blind Dungeon — Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft — Hackathon Edition

---

## Table of Contents

1. [Overview](#overview)
2. [Vision & Goals](#vision--goals)
3. [Tech Stack](#tech-stack)
4. [Architecture Principles](#architecture-principles)
5. [Feature Specifications by Phase](#feature-specifications-by-phase)
6. [File & Folder Structure](#file--folder-structure)
7. [Team Task Division](#team-task-division)
8. [Dependencies & Integration Points](#dependencies--integration-points)
9. [Data Schemas](#data-schemas)
10. [Out of Scope](#out-of-scope)

---

## 1. Overview

**Blind Dungeon** is a voice-driven, AI-narrated dungeon exploration game built in Python. The player navigates a graph-based dungeon map entirely through voice commands, with every room described by a live Mistral LLM call and narrated aloud via ElevenLabs TTS. The UI is intentionally minimal — the experience is almost entirely audio. There are no visual assets, sprites, or animations; the UI exists only to display discrete state information (inventory, health bars, map debug view).

This PRD covers all five development phases from core navigation through AI-generated maps, and is structured for a four-person hackathon team.

---

## 2. Vision & Goals

### Vision Statement
A blind dungeon crawler where the world exists only in sound — the LLM is the dungeon master, the player's voice is the controller, and silence is the atmosphere.

### Primary Goals
- Deliver a playable Phase 1 loop within the first hackathon session
- Keep all AI calls (STT, LLM, TTS) non-blocking so the UI never freezes
- Maintain a clean, beginner-friendly OOP codebase that any team member can pick up
- Use local JSON files as the single source of truth for all game state

### Success Criteria per Phase

| Phase | Success Criteria |
|---|---|
| 1 | Player can navigate rooms entirely by voice; LLM narrates every room; background audio plays |
| 2 | Player can pick up items; boss combat resolves correctly using items; health bars update live |
| 3 | Monsters move between rooms each turn; locked rooms block entry until key is found; death resets state |
| 4 | Every room entry triggers a thematic narration clip; boss attacks produce unique voice lines |
| 5 | Player inputs theme + difficulty; AI outputs a valid, playable dungeon graph within 10 seconds |

---

## 3. Tech Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Type hints throughout |
| UI Framework | PyQt6 | Minimal windows; QMainWindow + QWidgets only |
| LLM | Mistral API (`mistral-large-latest`) | Chat completion endpoint |
| STT | Mistral Audio Transcription | Record mic → send audio → get transcript |
| TTS | ElevenLabs Python SDK | Streaming audio preferred to reduce latency |
| Audio Playback | `pygame.mixer` or `sounddevice` | Background loops + TTS clip playback |
| Mic Recording | `sounddevice` + `scipy.io.wavfile` | Capture to temp WAV before STT |
| Game State | Local JSON files | `state/` directory, one file per concern |
| Dependency Mgmt | `pip` + `requirements.txt` | No exotic build tools |
| Config | `.env` file via `python-dotenv` | API keys never hardcoded |

### External API References
- Mistral Chat Completion: https://docs.mistral.ai/capabilities/completion/usage
- Mistral Audio Transcription: https://docs.mistral.ai/capabilities/audio_transcription
- ElevenLabs TTS: via official `elevenlabs` Python package

---

## 4. Architecture Principles

### 4.1 OOP Structure
Every major concern is a class. Classes communicate through a central `GameController` that owns the game loop. No global variables — state lives in `GameState` and is serialized to JSON after every mutation.

### 4.2 Non-Blocking AI Calls
All Mistral and ElevenLabs calls run in Python `threading.Thread` workers. The UI never waits on a network call. A `signals` module (PyQt6 `QObject` with custom signals) bridges worker threads back to the main Qt thread.

### 4.3 Single Source of Truth
`state/game_state.json` is written to disk after every state change. On startup, the game reads this file to resume or initializes from `maps/dungeon_map.json`. This means the game is always recoverable from disk.

### 4.4 Prompt Engineering Discipline
All LLM prompts live in `ai/prompts.py` as named string constants or functions. No prompt strings are scattered through game logic files. This makes tuning prompts a single-file task.

---

## 5. Feature Specifications by Phase

---

### Phase 1 — Core Blind Dungeon + Voice

**Goal:** A complete, playable voice-navigation loop.

#### Map System
- The dungeon is a directed graph stored in `maps/dungeon_map.json`
- Each node is a room with a unique `id`, a `type` (`normal`, `boss`, `home`, `exit`), and a list of `exits` (neighboring node IDs)
- Edges are directional — room A may connect to B without B connecting back to A
- The player spawns at the node where `type == "home"` on game start

**Room Node Schema (JSON):**
```json
{
  "id": "room_01",
  "type": "normal",
  "name": "The Whispering Corridor",
  "exits": ["room_02", "room_05"],
  "description_hint": "long stone hallway, torches flickering"
}
```

#### LLM Room Narration
- On room entry, the game sends a prompt to Mistral containing: room metadata, available exits (by name/hint), and current game state context
- Mistral returns 2–4 sentences of atmospheric prose describing the room and its exits
- The raw text is passed to ElevenLabs TTS and played back to the user
- While TTS audio is playing, the UI shows a "Narrating..." status

**Narration Prompt Contract:**
```
System: You are a dungeon master narrating a blind dungeon game. Be atmospheric, concise (2-4 sentences), and always mention the available exits naturally.
User: Room: {room_name}. Hints: {description_hint}. Available exits lead to: {exit_names}. Player just came from: {previous_room}.
```

#### Voice Command Input
- A "Speak" button (or hotkey `Space`) triggers mic recording via `sounddevice`
- Recording stops after silence detection or a fixed 5-second timeout
- Audio is sent to Mistral STT → transcript string returned
- Transcript + current room exits are sent to Mistral LLM for intent extraction
- LLM outputs a structured JSON response: `{"action": "move", "target": "room_02"}`
- `GameController` validates the target is a real exit of the current room, then calls `GameState.move_player(target_id)`

**Intent Extraction Prompt Contract:**
```
System: You are an intent parser for a dungeon game. The player spoke a command. Extract their intent as JSON only. Valid actions: "move". Output format: {"action": "move", "target": "<room_id>"} or {"action": "unknown"}.
User: Player said: "{transcript}". Current room exits: {exit_map}.
```

#### Background Audio
- `audio/bg/` contains looping ambient tracks (e.g. `dungeon_ambient.mp3`)
- On game start, a background track begins looping at low volume via `pygame.mixer`
- Background audio is independent of TTS playback (two audio channels)

#### Win Condition
- Game ends when the player enters the node with `type == "exit"` AND all boss nodes have been cleared
- Win screen: UI shows a brief text message; ElevenLabs plays a victory narration
- `state/game_state.json` is reset to initial values

#### Minimal UI (Phase 1)
The PyQt6 window contains only:
- Game title label
- Current room name label
- Available exits list (read-only)
- "Speak" button
- Status bar: "Narrating...", "Listening...", "Processing...", "Ready"

---

### Phase 2 — Items + Boss Combat

**Goal:** Add items, inventory, and turn-based boss combat.

#### Items
- Items are defined in `data/items.json` — each has `id`, `name`, `damage`, `type`, `description`, `rarity`
- On map load, items are randomly distributed to non-boss, non-home rooms and stored in `game_state.json` under `room_items`
- When a player enters a room with items, the LLM narration mentions them
- Voice command `"pick up [item]"` → intent `{"action": "pickup", "target": "<item_id>"}` → item moves to inventory
- Inventory is displayed as a scrollable list widget in the UI
- Inventory cap: 8 items (configurable in `config.py`)

**Item Schema:**
```json
{
  "id": "sword_of_echoes",
  "name": "Sword of Echoes",
  "damage": 35,
  "type": "weapon",
  "description": "A blade that hums with forgotten voices",
  "rarity": "rare"
}
```

#### Boss Rooms
- Nodes with `type == "boss"` contain a boss defined in `data/bosses.json`
- Boss has: `id`, `name`, `hp`, `max_hp`, `skills` (list of skill objects), `voice_id` (ElevenLabs voice)
- Entering a boss room triggers combat mode; the player cannot leave until the boss is defeated or the player dies

#### Combat System
- Combat is turn-based: player attacks first, then boss
- Player selects an item from inventory via voice command: `{"action": "attack", "item_id": "<item_id>"}`
- Item's `damage` value is subtracted from boss HP
- Boss selects a random skill from its `skills` list; skill `damage` is subtracted from player HP
- Boss skill activation: Mistral generates a taunting voice line, ElevenLabs speaks it in the boss's assigned voice
- After each exchange, the LLM narrates the round result (2 sentences max)
- UI displays: player HP bar, boss HP bar, boss name, last action text

**Boss Skill Schema:**
```json
{
  "id": "shadow_cleave",
  "name": "Shadow Cleave",
  "damage": 25,
  "taunt_hint": "slashes with a shadow tendril, mocking the player's weakness"
}
```

**Boss Taunt Prompt Contract:**
```
System: You are voicing a dungeon boss. Generate a single menacing sentence (the boss's spoken taunt) for the following attack. Stay in character.
User: Boss: {boss_name}. Attack used: {skill_name}. Hint: {taunt_hint}.
```

#### Boss Defeat
- Boss HP reaches 0 → boss node marked `cleared: true` in `game_state.json`
- LLM generates a victory narration; ElevenLabs plays it
- Player returns to exploration mode; the room is now traversable
- If all bosses cleared → exit door unlocks

---

### Phase 3 — Roaming Monsters + Locked Rooms

**Goal:** Dynamic threats and environmental puzzles.

#### Roaming Monsters
- Monsters are defined in `data/monsters.json`, similar schema to bosses but lighter
- On each player move, every living monster moves to a random adjacent room (graph traversal)
- Monster positions are stored in `game_state.json` under `monster_positions`
- If after a player move the player's current room matches any monster's position → combat triggers
- Monster combat follows the same turn-based loop as boss combat but with simpler skills

#### Locked Rooms
- A room node may have `"locked": true` and `"key_id": "key_iron"` in its map definition
- The corresponding key item exists somewhere in the dungeon as a regular item pickup
- If player attempts to enter a locked room without the key → LLM narrates a "door is locked" description, movement is blocked
- If player has the key in inventory → room unlocks, key is consumed, `game_state.json` updated

#### Player Death
- Player HP reaches 0 → Game Over state
- LLM generates a death narration; ElevenLabs plays it
- UI shows "GAME OVER" overlay
- Full state reset: `game_state.json` overwritten with initial values derived from `dungeon_map.json`
- Player returns to home room with empty inventory and full HP

---

### Phase 4 — Cutscenes + Enhanced Audio

**Goal:** Elevated atmosphere through contextual narration and varied audio.

#### Room Entry Cutscenes
Each room `type` has a dedicated narration prompt style:
- `normal` — atmospheric exploration prose (2–4 sentences)
- `boss` — ominous, tension-building intro (4–6 sentences)
- `monster` — urgent, threatening description
- `item`/`treasure` — discovery-focused, enticing

A cutscene lock prevents player input while the narration plays. Configurable skip via `Escape` key.

#### Combat Voice Lines
- Every enemy attack (boss or monster) generates a unique voice line via Mistral + ElevenLabs
- Voice lines are non-repetitive because the LLM generates them on the fly from the skill hint
- Player attacks may also trigger short environmental reactions

#### Per-Room-Type Background Audio
- `audio/bg/` contains separate looping tracks per room type: `normal.mp3`, `boss.mp3`, `monster.mp3`, `treasure.mp3`
- On room entry, the current background track crossfades to the appropriate track over 2 seconds
- Crossfade is implemented in the `AudioManager` class

---

### Phase 5 — AI-Generated Maps

**Goal:** Infinite, thematic, difficulty-tuned dungeon generation.

#### Map Generation UI
A "New Game" dialog in PyQt6 presents:
- **Theme selector** (dropdown): `dungeon`, `forest`, `abandoned_city`, `cursed_temple`, `cosmic_void`
- **Difficulty selector** (radio buttons): `Easy`, `Medium`, `Hard`
- "Generate Map" button; UI shows a loading indicator during generation

#### Generation Constraints by Difficulty

| Parameter | Easy | Medium | Hard |
|---|---|---|---|
| Total rooms | 8–12 | 13–20 | 21–35 |
| Boss rooms | 1 | 2 | 3–4 |
| Locked rooms | 0 | 1–2 | 3–5 |
| Items in dungeon | 10–15 | 8–12 | 5–8 |
| Monster count | 1–2 | 3–5 | 6–10 |

#### Theme Influence
- Theme is injected into every subsequent LLM prompt as a system-level context modifier
- Theme affects: room `description_hint` values (generated by AI), background audio track selection, ElevenLabs voice character selection
- A `ThemeConfig` dataclass in `config.py` maps each theme to its audio assets and voice profile

**Map Generation Prompt Contract:**
```
System: You are a dungeon map generator. Output ONLY valid JSON matching the dungeon_map schema. No explanation.
User: Generate a {difficulty} {theme} dungeon. Constraints: {constraints_json}. Schema: {schema_json}.
```

#### Map Validation
`MapValidator.validate(map_dict)` checks:
- Exactly one `home` node and one `exit` node
- All exit references point to existing node IDs
- Graph is fully connected (BFS from home reaches all nodes)
- Boss and monster counts within difficulty bounds
- Max 3 retries before surfacing an error to the user

---

## 6. File & Folder Structure

```
blind_dungeon/
│
├── main.py                          # Entry point — instantiates App and GameController
├── requirements.txt                 # All pip dependencies
├── .env                             # API keys (MISTRAL_API_KEY, ELEVENLABS_API_KEY) — never committed
├── .env.example                     # Template showing required env vars
├── config.py                        # Global constants, ThemeConfig dataclass, difficulty params
│
├── game/                            # Core game logic (no UI, no AI calls)
│   ├── __init__.py
│   ├── game_controller.py           # Central orchestrator — owns game loop, connects all subsystems
│   ├── game_state.py                # GameState class — player HP, position, inventory, monster positions
│   ├── dungeon_map.py               # DungeonMap class — loads graph, pathfinding, adjacency queries
│   ├── combat.py                    # CombatManager — turn logic, damage calc, death/win detection
│   ├── inventory.py                 # Inventory class — item add/remove, cap enforcement, key logic
│   └── monster_ai.py                # MonsterAI — roaming logic, move-per-turn random walk
│
├── ai/                              # All external AI integrations
│   ├── __init__.py
│   ├── prompts.py                   # ALL prompt strings/functions — single file, no prompt duplication
│   ├── mistral_client.py            # MistralClient — chat completion and STT wrappers
│   ├── tts_client.py                # TTSClient (ElevenLabs) — text-to-speech, voice selection
│   ├── intent_parser.py             # IntentParser — takes transcript, returns structured action dict
│   ├── narrator.py                  # Narrator — builds narration prompts, calls Mistral + TTS pipeline
│   └── map_generator.py             # MapGenerator + MapValidator — Phase 5 AI map generation
│
├── audio/                           # Audio management
│   ├── __init__.py
│   ├── audio_manager.py             # AudioManager — background loops, crossfade, TTS clip playback
│   ├── mic_recorder.py              # MicRecorder — sounddevice capture, silence detection, WAV output
│   └── bg/                          # Background audio assets
│       ├── normal.mp3
│       ├── boss.mp3
│       ├── monster.mp3
│       └── treasure.mp3
│
├── ui/                              # PyQt6 UI layer — only presentation, zero game logic
│   ├── __init__.py
│   ├── main_window.py               # MainWindow (QMainWindow) — root window, layout, widget hosting
│   ├── game_view.py                 # GameView — room label, exits list, status bar, Speak button
│   ├── combat_view.py               # CombatView — HP bars, item selector, combat log
│   ├── inventory_widget.py          # InventoryWidget — scrollable item list, pickup/use actions
│   ├── new_game_dialog.py           # NewGameDialog — theme/difficulty selectors (Phase 5)
│   └── signals.py                   # AppSignals (QObject) — custom Qt signals bridging threads to UI
│
├── maps/                            # Dungeon map definitions
│   ├── dungeon_map.json             # Default hand-crafted map
│   └── generated_map.json           # AI-generated map (overwritten each new game in Phase 5)
│
├── data/                            # Static game data definitions
│   ├── items.json                   # All item definitions
│   ├── bosses.json                  # All boss definitions (skills, HP, voice_id)
│   └── monsters.json                # All monster definitions
│
├── state/                           # Runtime game state (read/written during play)
│   └── game_state.json              # Live game state — position, HP, inventory, cleared rooms, etc.
│
└── tests/                           # Unit tests
    ├── test_dungeon_map.py
    ├── test_combat.py
    ├── test_intent_parser.py
    └── test_map_validator.py
```

### Key File Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | Initializes `QApplication`, creates `MainWindow` and `GameController`, wires signals, starts event loop |
| `config.py` | `INVENTORY_CAP`, `RECORDING_TIMEOUT`, `ThemeConfig` dataclass, difficulty constraint tables, voice ID mappings |
| `game/game_controller.py` | The hub: receives player actions from UI signals, calls `GameState`, triggers AI narration, updates UI via signals |
| `game/game_state.py` | Pure data model: current room, player HP/max, inventory list, monster positions dict, cleared bosses set. Serializes/deserializes JSON |
| `game/dungeon_map.py` | Wraps the JSON graph: `get_room(id)`, `get_exits(id)`, `are_connected(a, b)`, BFS reachability |
| `game/combat.py` | `CombatManager.player_attack(item)`, `CombatManager.enemy_attack()`, returns combat result objects |
| `game/monster_ai.py` | `MonsterAI.move_all(game_state, dungeon_map)` — advances each monster one step randomly each turn |
| `ai/prompts.py` | `build_narration_prompt()`, `build_intent_prompt()`, `build_boss_taunt_prompt()`, `build_map_generation_prompt()` |
| `ai/mistral_client.py` | `MistralClient.complete(messages)` (chat), `MistralClient.transcribe(audio_path)` (STT) |
| `ai/tts_client.py` | `TTSClient.speak(text, voice_id)` — calls ElevenLabs, returns audio bytes or temp file path |
| `ai/intent_parser.py` | `IntentParser.parse(transcript, current_room)` — calls Mistral, validates JSON, returns action dict |
| `ai/narrator.py` | `Narrator.narrate_room(room, game_state)` — orchestrates: prompt → Mistral → ElevenLabs → AudioManager |
| `ai/map_generator.py` | `MapGenerator.generate(theme, difficulty)`, `MapValidator.validate(map_dict)` |
| `audio/audio_manager.py` | `play_bg(track)`, `crossfade(new_track)`, `play_clip(audio_path)`, `stop_all()` |
| `audio/mic_recorder.py` | `MicRecorder.record()` — blocks until silence or timeout, returns path to temp WAV |
| `ui/signals.py` | `AppSignals`: `narration_ready`, `audio_ready`, `state_updated`, `combat_event`, `game_over`, `game_won` |
| `ui/main_window.py` | Creates `GameView`, `CombatView`, stacks them; connects `AppSignals` to slot methods |
| `ui/game_view.py` | Displays room name, exits, status. Speak button click emits signal to `GameController` |
| `ui/combat_view.py` | Shows HP bars (QProgressBar), item list, "Use Item" button |

---

## 7. Team Task Division

---

### Member A — Game Engine & State

**Role:** Owns the core game loop, data model, map system, and combat logic. The foundation everything else depends on.

**Primary Files:** `game/game_controller.py`, `game/game_state.py`, `game/dungeon_map.py`, `game/combat.py`, `game/inventory.py`, `game/monster_ai.py`, `maps/dungeon_map.json`, `data/items.json`, `data/bosses.json`, `data/monsters.json`, `config.py`

| Phase | Tasks |
|---|---|
| 1 | Design and implement `DungeonMap` (load JSON, graph queries). Implement `GameState` (player position, serialization). Implement `GameController` skeleton with move logic. Hand-craft `dungeon_map.json` with ~12 rooms including home, exit, 2 boss rooms. |
| 2 | Add inventory system to `GameState`. Implement `CombatManager` (player attack, enemy attack, turn resolution). Define `items.json`, `bosses.json`. Scatter items on map load. Implement win condition check. |
| 3 | Implement `MonsterAI.move_all()`. Add locked room check to move logic in `GameController`. Implement player death → state reset. Define `monsters.json`. |
| 4 | Expose room type context to `Narrator` for cutscene differentiation. |
| 5 | Define difficulty constraint tables in `config.py`. Integrate `MapGenerator` output into game startup flow. |

**Key Interfaces to Publish:**
- `GameState.to_dict()` / `GameState.from_dict()`
- `DungeonMap.get_room(id)` → `RoomDict`
- `DungeonMap.get_exits(id)` → `list[RoomDict]`
- `CombatManager.resolve_player_attack(item_id)` → `CombatResult`
- `CombatManager.resolve_enemy_attack()` → `CombatResult`

---

### Member B — AI & Voice Pipeline

**Role:** Owns all LLM integrations (narration, intent parsing, combat voice), STT, and the TTS pipeline. The "voice" of the game.

**Primary Files:** `ai/prompts.py`, `ai/mistral_client.py`, `ai/tts_client.py`, `ai/intent_parser.py`, `ai/narrator.py`, `ai/map_generator.py`, `.env.example`

| Phase | Tasks |
|---|---|
| 1 | Implement `MistralClient` (chat completion + STT wrappers). Implement `TTSClient` (ElevenLabs). Write `build_narration_prompt()` and `build_intent_prompt()` in `prompts.py`. Implement `Narrator.narrate_room()`. Implement `IntentParser.parse()`. Test full voice loop end-to-end. |
| 2 | Write `build_boss_taunt_prompt()`. Extend `Narrator` to handle boss entry narration (longer format). Hook into `CombatManager` events to trigger taunt TTS calls. |
| 3 | Add "locked room", "monster encounter", and "player death" narration prompt variants. |
| 4 | Write per-room-type prompt variants in `prompts.py`. Implement combat attack voice line generation (each enemy attack = unique LLM + TTS call, non-blocking). |
| 5 | Implement `MapGenerator.generate(theme, difficulty)`. Implement `MapValidator.validate()`. Write `build_map_generation_prompt()`. Handle retry logic on invalid map JSON. |

**Key Interfaces to Publish:**
- `Narrator.narrate_room(room, game_state)` — called by `GameController` on room entry
- `IntentParser.parse(transcript, exits)` → `{"action": str, "target": str | None}`
- `Narrator.narrate_combat_event(event_type, context)` — called on each combat turn
- `MapGenerator.generate(theme, difficulty)` → `map_dict`

**Dependency Note:** Needs Member A's `GameState.to_dict()` early for prompt context. Needs Member C's `AudioManager.play_clip()` for TTS output.

---

### Member C — Audio Engine

**Role:** Owns mic recording, background audio management, TTS audio playback, and crossfading. The "ears and speakers" of the game.

**Primary Files:** `audio/audio_manager.py`, `audio/mic_recorder.py`, `audio/bg/`

| Phase | Tasks |
|---|---|
| 1 | Implement `MicRecorder.record()` with configurable timeout and silence detection. Implement `AudioManager.play_bg(track)` with looping. Implement `AudioManager.play_clip(audio_path)` for TTS playback. Source a base `normal.mp3`. Ensure background and TTS play on separate audio channels simultaneously. |
| 2 | Integrate `play_clip()` into boss taunt flow. Test that boss TTS voice lines layer correctly over background audio. |
| 3 | Support Member A's death/reset flow: stop all audio on Game Over, restart bg on new game. |
| 4 | Implement `AudioManager.crossfade(new_track, duration_ms=2000)`. Source per-room-type tracks: `boss.mp3`, `monster.mp3`, `treasure.mp3`. Implement TTS playback queue so clips don't overlap. |
| 5 | Map `ThemeConfig` audio entries (from `config.py`) to audio file paths. Ensure `AudioManager` can switch audio profile on new map generation. |

**Key Interfaces to Publish:**
- `MicRecorder.record()` → `str` (path to WAV file)
- `AudioManager.play_bg(track_name: str)`
- `AudioManager.play_clip(audio_path: str)`
- `AudioManager.crossfade(new_track: str)`
- `AudioManager.stop_all()`

**Dependency Note:** Member C is depended on by both Member A (`GameController` triggers audio) and Member B (TTS playback). Deliver `play_clip()` and `play_bg()` as early stubs on Day 1.

---

### Member D — UI & Integration

**Role:** Owns the PyQt6 UI layer, the signals/slots architecture, and the final wiring of all subsystems. Also owns end-to-end integration testing.

**Primary Files:** `ui/main_window.py`, `ui/game_view.py`, `ui/combat_view.py`, `ui/inventory_widget.py`, `ui/new_game_dialog.py`, `ui/signals.py`, `main.py`, `tests/`

| Phase | Tasks |
|---|---|
| 1 | Build `AppSignals` class with initial signals. Build `MainWindow` skeleton. Build `GameView` (room label, exits list, status bar, Speak button). Wire Speak button → `GameController.on_speak_pressed()`. Wire `state_updated` signal → refresh `GameView`. Write `main.py` entry point. |
| 2 | Build `CombatView` (player HP bar, boss HP bar, item list, "Use Item" button). Build `InventoryWidget`. Wire `MainWindow` to switch between `GameView` and `CombatView` on combat start/end signals. |
| 3 | Add "GAME OVER" overlay widget shown on `game_over` signal. Wire reset flow: `game_over` signal → show overlay → confirm → reset state → return to `GameView`. |
| 4 | Add input lock mechanism (disable Speak button during narration; `Escape` skips cutscene). Ensure UI status bar reflects all states. |
| 5 | Build `NewGameDialog` (theme dropdown, difficulty radio buttons, Generate button). Wire generation: button → loading spinner → `MapGenerator.generate()` in thread → reload game with new map → close dialog. |

**Key Interfaces to Publish:**
- `AppSignals` instance — shared across the entire application
- `MainWindow.show_game_view()` / `MainWindow.show_combat_view()`
- Signal definitions in `ui/signals.py` — must be finalized early

**Dependency Note:** Member D depends on all other members. Should deliver `AppSignals` and `MainWindow` skeleton on Day 1 — this is the shared integration interface.

---

## 8. Dependencies & Integration Points

```
Member A (Game Engine)
    ├── publishes: GameState, GameController events, DungeonMap queries
    ├── depends on: Member D's AppSignals (to emit state_updated)
    └── depends on: Member C's AudioManager stubs (to trigger bg audio)

Member B (AI & Voice)
    ├── publishes: Narrator, IntentParser, MapGenerator
    ├── depends on: Member A's GameState.to_dict() (for prompt context)
    └── depends on: Member C's AudioManager.play_clip() (for TTS output)

Member C (Audio Engine)
    ├── publishes: MicRecorder, AudioManager
    ├── depends on: Member D's AppSignals (to signal recording complete)
    └── no hard dependencies on A or B (pure I/O layer)

Member D (UI & Integration)
    ├── publishes: AppSignals, MainWindow, all UI widgets
    ├── depends on: all members' published interfaces
    └── integration testing validates all cross-member interfaces
```

### Critical Path for Day 1
These three artifacts must exist before others are blocked:

1. **Member A** → `GameState` schema + `DungeonMap` loader + `dungeon_map.json`
2. **Member C** → `AudioManager.play_bg()` stub + `MicRecorder.record()` stub (returns a test WAV file)
3. **Member D** → `AppSignals` class + `MainWindow` skeleton + `GameView` layout

---

## 9. Data Schemas

### `state/game_state.json`
```json
{
  "player": {
    "current_room": "home",
    "hp": 100,
    "max_hp": 100,
    "inventory": ["sword_of_echoes"]
  },
  "world": {
    "cleared_bosses": ["boss_shadow_lord"],
    "room_items": {
      "room_03": ["iron_key"],
      "room_07": ["shield_of_mist"]
    },
    "monster_positions": {
      "wraith_01": "room_04",
      "troll_02": "room_09"
    },
    "unlocked_rooms": ["room_08"]
  },
  "meta": {
    "theme": "dungeon",
    "difficulty": "medium",
    "session_start": "2026-02-28T10:00:00Z"
  }
}
```

### `maps/dungeon_map.json`
```json
{
  "map_id": "default_dungeon",
  "theme": "dungeon",
  "rooms": [
    {
      "id": "home",
      "type": "home",
      "name": "The Lantern Room",
      "exits": ["room_01", "room_02"],
      "description_hint": "warm light, stone walls, a single lantern",
      "locked": false,
      "key_id": null
    },
    {
      "id": "boss_01",
      "type": "boss",
      "name": "The Throne of Ash",
      "exits": ["room_05"],
      "description_hint": "scorched throne, ash everywhere, oppressive silence",
      "locked": false,
      "key_id": null,
      "boss_id": "shadow_lord"
    }
  ]
}
```

### `data/items.json`
```json
{
  "items": [
    {
      "id": "sword_of_echoes",
      "name": "Sword of Echoes",
      "damage": 35,
      "type": "weapon",
      "description": "A blade that hums with forgotten voices",
      "rarity": "rare"
    },
    {
      "id": "iron_key",
      "name": "Iron Key",
      "damage": 0,
      "type": "key",
      "description": "A heavy iron key, worn smooth with age",
      "rarity": "common"
    }
  ]
}
```

### `data/bosses.json`
```json
{
  "bosses": [
    {
      "id": "shadow_lord",
      "name": "The Shadow Lord",
      "hp": 150,
      "max_hp": 150,
      "voice_id": "elevenlabs_voice_id_here",
      "skills": [
        {
          "id": "shadow_cleave",
          "name": "Shadow Cleave",
          "damage": 25,
          "taunt_hint": "slashes with a tendril of darkness, mocking your frailty"
        },
        {
          "id": "void_gaze",
          "name": "Void Gaze",
          "damage": 40,
          "taunt_hint": "stares into your soul, whispering your deepest fear"
        }
      ]
    }
  ]
}
```

### `data/monsters.json`
```json
{
  "monsters": [
    {
      "id": "wraith_01",
      "name": "The Wandering Wraith",
      "hp": 60,
      "max_hp": 60,
      "voice_id": "elevenlabs_voice_id_here",
      "skills": [
        {
          "id": "chill_touch",
          "name": "Chill Touch",
          "damage": 15,
          "taunt_hint": "reaches through you with cold spectral fingers"
        }
      ]
    }
  ]
}
```

---

## 10. Out of Scope

The following are explicitly excluded from all five phases to keep the hackathon scope realistic:

- Multiplayer or networked gameplay
- Procedural audio generation (all background tracks are pre-sourced MP3 files)
- Save slots or multiple save files (one active game state at a time)
- Visual sprites, tile maps, or any 2D/3D rendering
- Mobile or web deployment (desktop Python only)
- Persistent cloud state (all state is local)
- Difficulty balancing post-generation (no adaptive difficulty mid-run)
- Localization or multi-language support
- Accessibility features beyond voice-first design
- A game editor or map authoring GUI (maps are hand-edited JSON or AI-generated)

---

*This PRD is a living reference for the hackathon duration. Team leads should update phase status as features ship.*
