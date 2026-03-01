# Phase 2 Implementation Plan — Items + Boss Combat

## Context
Builds on the Phase 1 foundation to add:
- Items scattered in rooms; player picks them up via voice
- Turn-based boss combat when entering a boss room (using weapons from inventory)
- Pre-generated boss TTS audio (distinct OpenAI voice per boss, `fable` for guardian) to eliminate runtime latency
- Exit gate: player must defeat all bosses before reaching the exit room
- Inventory + room-items display as text labels in the existing `GameView`

Key decisions:
- Boss voice lines are **pre-generated** and stored in `audio/bosses/` by running `scripts/pregenerate_boss_audio.py` before the game
- `GameController.__init__` validates boss audio and logs WARNING per missing file
- Missing audio during combat is silently skipped (game still playable)
- Inventory and room items displayed in `GameView` as small text labels (no new widget or stacked view)
- `IntentAction` extended to `Literal["move", "pickup", "attack", "unknown"]`; `item_id: Optional[str]` added

---

## Implementation Order

1. `config.py` — add DATA_DIR, ITEMS_FILE, BOSSES_FILE, BOSSES_AUDIO_DIR
2. `data/items.json` — item definitions
3. `data/bosses.json` — boss definitions with `openai_voice`
4. `maps/dungeon_map.json` — add `boss_id: "guardian"` to boss room
5. `state/game_state.json` — add `boss_hp: {}` to world schema
6. `game/game_state.py` — add boss HP + inventory mutation + room-item methods
7. `game/dungeon_map.py` — add `get_boss_id()`, `get_all_boss_room_ids()`
8. `game/combat.py` (new) — `CombatResult` dataclass + `CombatManager`
9. `ai/prompts.py` — add Phase 2 prompts
10. `ai/intent_parser.py` — extend `IntentAction`, add `parse_combat()` + `parse_pickup()`
11. `ai/narrator.py` — add Phase 2 narration methods
12. `ui/signals.py` — add Phase 2 signals
13. `ui/game_view.py` — add `lbl_room_items`, `lbl_inventory`, `lbl_combat` labels + slots
14. `game/game_controller.py` — item scattering, pickup, combat loop, exit gate
15. `scripts/pregenerate_boss_audio.py` (new) — standalone pre-generation script

---

## File Specifications

### `config.py` — add
```python
DATA_DIR         = ROOT_DIR / "data"
ITEMS_FILE       = DATA_DIR / "items.json"
BOSSES_FILE      = DATA_DIR / "bosses.json"
BOSSES_AUDIO_DIR = ROOT_DIR / "audio" / "bosses"
```

---

### `data/items.json`
```json
{
  "items": [
    {"id": "iron_sword",    "name": "Iron Sword",    "damage": 25, "type": "weapon", "description": "A battered iron sword, still sharp enough to draw blood",       "rarity": "common"},
    {"id": "battle_axe",    "name": "Battle Axe",    "damage": 40, "type": "weapon", "description": "A heavy double-headed axe, its edge still gleaming",            "rarity": "rare"},
    {"id": "cursed_dagger", "name": "Cursed Dagger", "damage": 35, "type": "weapon", "description": "A dagger with a dark aura, warm to the touch",                  "rarity": "uncommon"},
    {"id": "bone_club",     "name": "Bone Club",     "damage": 20, "type": "weapon", "description": "A crude club fashioned from a femur; primitive but effective",   "rarity": "common"}
  ]
}
```

---

### `data/bosses.json`
```json
{
  "bosses": [
    {
      "id": "guardian",
      "name": "The Dark Guardian",
      "hp": 120,
      "max_hp": 120,
      "openai_voice": "fable",
      "skills": [
        {"id": "stone_crush", "name": "Stone Crush", "damage": 20, "taunt_hint": "raises a massive stone fist and slams it down with thunderous force"},
        {"id": "shadow_bolt", "name": "Shadow Bolt", "damage": 30, "taunt_hint": "hurls a bolt of pure darkness, laughing at your feeble attempt to dodge"},
        {"id": "iron_grasp",  "name": "Iron Grasp",  "damage": 15, "taunt_hint": "reaches out with armored claws and crushes with grinding force"}
      ]
    }
  ]
}
```

---

### `maps/dungeon_map.json` — update boss room
Add `"boss_id": "guardian"` field to the existing `boss` room object.

---

### `state/game_state.json` — add `boss_hp`
Under `world`:
```json
"boss_hp": {}   ← populated on first combat entry: {"guardian": 120}
```

---

### `game/game_state.py` — new methods

```python
# Room items
def get_room_items(self, room_id: str) -> list[str]               # item_ids in room
def remove_room_item(self, room_id: str, item_id: str) -> None
def set_room_items(self, room_id: str, items: list[str]) -> None  # called by scatter

# Inventory
def add_to_inventory(self, item_id: str) -> bool    # False if at INVENTORY_CAP
def remove_from_inventory(self, item_id: str) -> None

# Boss HP
def get_boss_hp(self, boss_id: str, max_hp: int) -> int   # inits to max_hp if absent
def set_boss_hp(self, boss_id: str, hp: int) -> None
# mark_boss_cleared + is_boss_cleared already exist in Phase 1

# Scatter helper
def needs_item_scatter(self) -> bool   # True when room_items == {}
```

---

### `game/dungeon_map.py` — new methods

```python
def get_boss_id(self, room_id: str) -> str | None
def get_all_boss_room_ids(self) -> list[str]   # rooms where type == "boss"
```

---

### `game/combat.py` (new)

```python
from dataclasses import dataclass
import random

@dataclass
class CombatResult:
    player_damage: int   # damage dealt to boss (item.damage)
    boss_damage:   int   # damage dealt to player (skill.damage)
    skill_id:      str
    skill_name:    str
    taunt_hint:    str

class CombatManager:
    def resolve(self, item: dict, boss: dict) -> CombatResult:
        skill = random.choice(boss["skills"])
        return CombatResult(
            player_damage = item["damage"],
            boss_damage   = skill["damage"],
            skill_id      = skill["id"],
            skill_name    = skill["name"],
            taunt_hint    = skill["taunt_hint"],
        )
```

---

### `ai/prompts.py` — additions

```python
def build_boss_entry_user_prompt(boss_name, room_name, room_hint, previous_room_name) -> str:
    # 4-6 sentence ominous boss room intro; no exit mention

def build_combat_round_user_prompt(boss_name, item_name, player_damage,
                                    skill_name, boss_damage,
                                    player_hp, boss_hp) -> str:
    # 2 sentences: what just happened this round

def build_boss_defeat_user_prompt(boss_name) -> str:
    # 3-4 sentences: the boss falls

def build_exit_blocked_user_prompt() -> str:
    # 2-3 sentences: exit sealed by dark energy, sense undefeated guardian

def build_pickup_narration_user_prompt(item_name, room_name) -> str:
    # 1-2 sentences: player pockets the item

def build_combat_intent_system_prompt() -> str: ...
def build_combat_intent_user_prompt(transcript, inventory_items: list[dict]) -> str:
    # Include item names + ids; ask LLM to return item_id of chosen weapon

def build_pickup_intent_user_prompt(transcript, room_items: list[dict]) -> str:
    # Include item names + ids in room; ask LLM to return item_id to pick up
```

Also update `build_narration_user_prompt` to accept `room_items: list[str]` (item names) and include them in the prompt context when non-empty.

---

### `ai/intent_parser.py` — extensions

```python
class IntentAction(BaseModel):
    action:    Literal["move", "pickup", "attack", "unknown"]
    direction: Optional[str] = None   # for move
    item_id:   Optional[str] = None   # for pickup and attack
```

New methods:
```python
def parse_combat(self, transcript: str, inventory_items: list[dict]) -> IntentAction:
    """Attack intent only. Validates item_id is in inventory_items."""

def parse_pickup(self, transcript: str, room_items: list[dict]) -> IntentAction:
    """Pickup intent only. Validates item_id is in room_items."""
```

---

### `ai/narrator.py` — additions

```python
def narrate_boss_entry(self, boss_name, room, previous_room_name) -> tuple[str, str]
def narrate_combat_round(self, boss_name, item_name, player_damage,
                          skill_name, boss_damage, player_hp, boss_hp) -> tuple[str, str]
def narrate_boss_defeat(self, boss_name) -> tuple[str, str]
def narrate_exit_blocked(self) -> tuple[str, str]
def narrate_pickup(self, item_name, room_name) -> tuple[str, str]
```

---

### `ui/signals.py` — additions

```python
combat_started    = pyqtSignal(dict)   # {name, hp, max_hp}
combat_updated    = pyqtSignal(dict)   # {player_hp, player_max_hp, boss_hp, boss_max_hp}
combat_ended      = pyqtSignal()       # boss defeated, back to exploration
inventory_updated = pyqtSignal(list)   # list of item dicts
room_items_changed = pyqtSignal(list)  # list of item dicts in current room
```

---

### `ui/game_view.py` — additions

Insert after `lbl_narration`, before `addStretch()`:
```
spacing 12
lbl_room_items   ← "Items here:  Iron Sword  |  Battle Axe"    (dim color #707088, 12px)
spacing 4
lbl_inventory    ← "Inventory:  [empty]"                        (dim color #707088, 12px)
```

Insert above `lbl_status` (in bottom section):
```
lbl_combat       ← "You: 80/100  ❖  Guardian: 75/120"          (accent color, 13px, hidden by default)
spacing 6
```

New slots:
```python
def update_room_items(self, items: list[dict]) -> None
def update_inventory(self, items: list[dict]) -> None
def show_combat_status(self, player_hp, player_max, boss_hp, boss_max, boss_name) -> None
def hide_combat_status(self) -> None
```

---

### `game/game_controller.py` — Phase 2 additions

#### New instance state
```python
self._in_combat:      bool = False
self._current_boss:   dict | None = None   # boss dict + current_hp
self._combat_manager  = CombatManager()
self._item_registry:  dict[str, dict]      # loaded from items.json, keyed by id
self._boss_registry:  dict[str, dict]      # loaded from bosses.json, keyed by id
```

#### `__init__` additions
```python
self._item_registry = {i["id"]: i for i in json.loads(ITEMS_FILE.read_text())["items"]}
self._boss_registry = {b["id"]: b for b in json.loads(BOSSES_FILE.read_text())["bosses"]}
self._combat_manager = CombatManager()
self._validate_boss_audio()
if self._state.needs_item_scatter():
    self._scatter_items()
```

#### Item scatter
```python
def _scatter_items(self) -> None:
    eligible = [r for r in self._dungeon.all_room_ids
                if self._dungeon.get_room(r)["type"] not in ("home", "boss", "exit")]
    items = list(self._item_registry.keys())
    random.shuffle(items)
    for i, item_id in enumerate(items):
        room = eligible[i % len(eligible)]
        current = self._state.get_room_items(room)
        self._state.set_room_items(room, current + [item_id])
    self._state.save()
```

#### Boss audio validation
```python
def _validate_boss_audio(self) -> None:
    for boss in self._boss_registry.values():
        for skill in boss["skills"]:
            path = BOSSES_AUDIO_DIR / boss["id"] / f"{skill['id']}.wav"
            if not path.exists():
                logging.warning(f"Boss audio missing: {path}  →  run scripts/pregenerate_boss_audio.py")
```

#### Move action — updated
After resolving `target_id`, before triggering narration:
```python
# Exit gate
if self._dungeon.get_room(target_id)["type"] == "exit":
    boss_ids = [self._dungeon.get_boss_id(r) for r in self._dungeon.get_all_boss_room_ids()]
    if not all(self._state.is_boss_cleared(b) for b in boss_ids if b):
        self._trigger_exit_blocked_narration()
        return

# Boss room entry
boss_id = self._dungeon.get_boss_id(target_id)
if boss_id and not self._state.is_boss_cleared(boss_id):
    self._start_combat(boss_id, target_id)
    return
```

#### Pickup action handler
```python
def _handle_pickup(self, action: IntentAction) -> None:
    room_id   = self._state.current_room_id
    room_items = self._state.get_room_items(room_id)
    if action.item_id not in room_items:
        self._signals.error_occurred.emit("That item is not here.")
        return
    if not self._state.add_to_inventory(action.item_id):
        self._signals.error_occurred.emit("Your inventory is full (8 items max).")
        return
    self._state.remove_room_item(room_id, action.item_id)
    self._state.save()
    self._signals.inventory_updated.emit(self._inventory_as_dicts())
    self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
    self._trigger_pickup_narration(self._item_registry[action.item_id]["name"])
```

#### Combat attack handler
```python
def _handle_attack(self, action: IntentAction) -> None:
    if action.item_id not in self._state.inventory:
        self._signals.error_occurred.emit("You don't have that.")
        return
    item   = self._item_registry[action.item_id]
    result = self._combat_manager.resolve(item, self._current_boss)
    new_boss_hp   = max(0, self._current_boss["current_hp"] - result.player_damage)
    new_player_hp = max(0, self._state.hp - result.boss_damage)
    self._current_boss["current_hp"] = new_boss_hp
    self._state.set_boss_hp(self._current_boss["id"], new_boss_hp)
    self._state._data["player"]["hp"] = new_player_hp
    self._state.save()
    # Pre-generated boss taunt
    taunt_wav = BOSSES_AUDIO_DIR / self._current_boss["id"] / f"{result.skill_id}.wav"
    if taunt_wav.exists():
        self._audio.play_clip(str(taunt_wav))
    self._signals.combat_updated.emit({
        "player_hp": new_player_hp, "player_max_hp": self._state.max_hp,
        "boss_hp": new_boss_hp, "boss_max_hp": self._current_boss["max_hp"],
    })
    if new_boss_hp <= 0:
        self._finish_boss_combat()
        return
    if new_player_hp <= 0:
        self._signals.error_occurred.emit(
            "You have been defeated. Hold [SPACE] to play again."
        )
        self._state.reset()
        self._in_combat = False
        return
    self._trigger_combat_round_narration(result, new_boss_hp, new_player_hp)
```

#### `_on_transcript_ready` — combat routing
```python
def _on_transcript_ready(self, transcript: str) -> None:
    if self._in_combat:
        action = self._intent_parser.parse_combat(transcript, self._inventory_as_dicts())
    else:
        directions = self._dungeon.get_exit_names(self._state.current_room_id)
        action = self._intent_parser.parse(transcript, directions)
        if action.action == "unknown":
            room_items = self._room_items_as_dicts(self._state.current_room_id)
            if room_items:
                action = self._intent_parser.parse_pickup(transcript, room_items)
    self._handle_action(action)
```

#### `_handle_action` — route new actions
```python
if action.action == "pickup":
    self._handle_pickup(action)
elif action.action == "attack":
    self._handle_attack(action)
```

---

### `scripts/pregenerate_boss_audio.py` (new, standalone)

```python
"""
Pre-generate boss taunt voice lines before playing the game.
Usage:  python scripts/pregenerate_boss_audio.py
Output: audio/bosses/{boss_id}/{skill_id}.wav

Idempotent — skips files that already exist.
Requires: MISTRAL_API_KEY and OPENAI_API_KEY in .env
"""
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import BOSSES_FILE, BOSSES_AUDIO_DIR
from ai.mistral_client import MistralClient
from ai.tts_client import TTSClient
from ai.prompts import build_narration_system_prompt, build_boss_taunt_user_prompt

# TTSClient needs a way to pass voice — extend speak() to accept optional voice param
# MistralClient.complete() used for taunt text generation

bosses = json.loads(BOSSES_FILE.read_text())["bosses"]
mistral = MistralClient()
tts = TTSClient()

for boss in bosses:
    boss_dir = BOSSES_AUDIO_DIR / boss["id"]
    boss_dir.mkdir(parents=True, exist_ok=True)
    for skill in boss["skills"]:
        out = boss_dir / f"{skill['id']}.wav"
        if out.exists():
            print(f"  skip  {out}")
            continue
        print(f"  gen   {out} ...", end=" ", flush=True)
        text = mistral.complete(
            build_narration_system_prompt(),
            build_boss_taunt_user_prompt(boss["name"], skill["name"])
        )
        wav_tmp = tts.speak(text, voice=boss["openai_voice"])
        Path(wav_tmp).rename(out)
        print("done")

print("All boss audio ready.")
```

This requires `TTSClient.speak()` to accept an optional `voice` parameter (override default `TTS_VOICE`).

---

## Workers — Phase 2

All new narration types reuse `NarrationWorker` by passing different prompt pairs.
One new worker for combat round (same shape, connects to a different slot):

| Worker | New? | Purpose |
|--------|------|---------|
| `NarrationWorker` | reused | Boss entry, boss defeat, exit blocked, pickup |
| `CombatNarrationWorker` | new (thin) | Combat round — same shape, different slot |

`CombatNarrationWorker` slot `_on_combat_narration_done` plays audio then emits nothing extra (HP already emitted from attack handler).

---

## Verification

1. `python scripts/pregenerate_boss_audio.py` → 3 WAV files in `audio/bosses/guardian/`
2. `python main.py` → no boss audio warnings in console
3. Rooms a/b/c/d show items in `lbl_room_items`
4. Say "pick up the iron sword" → inventory label updates, room items label updates
5. Enter boss room → boss entry narration plays; `lbl_combat` shows HP (boss + player)
6. Say "attack with the iron sword" → boss taunt WAV plays, round narration plays, HP updates
7. Keep attacking until boss HP = 0 → defeat narration, `combat_ended`, can leave room
8. Try to enter exit room before boss defeated → exit blocked narration
9. Enter exit after boss defeated → normal win
