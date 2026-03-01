# Phase 3 Implementation Plan — Equipment System, Bare Hands, Health Potion, Flee Fix

## Overview

Phase 3 adds a full equipment and item system on top of the existing voice-driven dungeon game:

| Sub-phase | Feature |
|-----------|---------|
| 3.1 | Equipment slots (weapon + 6 armor) + bag for keys |
| 3.2 | Bare Hands default weapon — always available |
| 3.3 | Health Potion — instant heal on pickup |
| Fix | Flee from combat — exits suppressed during combat bug |

---

## Phase 3.1 — Equipment System

### Goal
Replace the flat inventory list with a slot-based equipment system. The player can wear one item per slot (weapon, helmet, suit, legs, shoes, cloak, shield) and carry keys in a bag. Picking up a weapon or armor auto-equips it, displacing the old item back into the room. Defense from all armor slots is summed and applied as flat damage reduction.

### Key Design Decisions

- **`inventory_updated` signal changes type**: `pyqtSignal(list)` → `pyqtSignal(dict)` with shape `{"equipped": {slot: item_dict|None}, "bag": [item_dicts]}`
- **Swap mechanic**: Picking up equipment when the slot is already occupied drops the old item back in the room
- **Flat defense reduction**: `damage_taken = max(0, boss_damage - total_defense)` per combat round
- **`_inventory_as_dicts()` preserved**: Flat list kept for the intent parser's weapon context (combat only)
- **`_equipment_payload()`**: New method builds the dict payload from `game_state.equipped` + `game_state.bag`

### Files Changed

| File | Change |
|------|--------|
| `ui/signals.py` | `inventory_updated = pyqtSignal(dict)` |
| `ui/game_view.py` | Replace `lbl_inventory` with `lbl_weapon`, `lbl_armor`, `lbl_bag`; add `update_inventory(dict)` |
| `game/game_state.py` | Add `equipped`, `bag` properties; `equip_item()`, `add_to_bag()`, `remove_from_inventory()` |
| `game/game_controller.py` | Add `_equipment_payload()`, update `_emit_inventory()`, rewrite `_handle_pickup()`, add `_compute_total_defense()`, add `_trigger_swap_narration()` |
| `ai/prompts.py` | Add `build_swap_narration_user_prompt()` |
| `ai/narrator.py` | Add `narrate_swap()` |

### `game/game_controller.py` Key Additions

**`_equipment_payload()`**:
```python
def _equipment_payload(self) -> dict:
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
```

**`_compute_total_defense()`**:
```python
def _compute_total_defense(self) -> int:
    total = 0
    for slot, item_id in self._state.equipped.items():
        if slot != "weapon" and item_id and item_id in self._item_registry:
            total += self._item_registry[item_id].get("defense", 0)
    return total
```

**`_handle_pickup()` — weapon/armor branch**:
```python
elif item_type in ("weapon", "armor"):
    slot   = item.get("slot")
    old_id = self._state.equip_item(slot, action.item_id)
    self._state.remove_room_item(room_id, action.item_id)
    if old_id and old_id != "bare_hands":
        self._state.set_room_items(room_id, self._state.get_room_items(room_id) + [old_id])
    self._state.save()
    self._signals.inventory_updated.emit(self._equipment_payload())
    self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
    if old_id and old_id in self._item_registry:
        self._trigger_swap_narration(item["name"], self._item_registry[old_id]["name"])
    else:
        self._trigger_pickup_narration(item["name"])
```

**Defense reduction in `_handle_attack()`**:
```python
defense       = self._compute_total_defense()
new_player_hp = max(0, self._state.hp - max(0, result.boss_damage - defense))
```

---

## Phase 3.2 — Bare Hands Default Weapon

### Goal
Give the player a permanent "Bare Hands" weapon that is always equipped from game start. It cannot be dropped or displaced into a room — it is silently replaced when the player picks up a real weapon. Prevents "You have no weapons" errors before the player finds a weapon.

### Key Design Decisions

- **`scatter: false`** field on items: bare_hands never scatters into rooms
- **Equip default at new game**: `_EQUIPPED_DEFAULTS["weapon"] = "bare_hands"` in `game_state.py`
- **Migration for saved games**: `load()` converts `weapon: null` → `"bare_hands"` for old saves
- **No-drop guard**: pickup path guards `if old_id and old_id != "bare_hands"` before dropping to room
- **Scatter filter**: `items = [iid for iid, item in self._item_registry.items() if item.get("scatter", True)]`

### Files Changed

| File | Change |
|------|--------|
| `data/items.json` | Add `bare_hands` with `scatter: false`, `damage: 5`, `rarity: "default"` |
| `game/game_state.py` | `_EQUIPPED_DEFAULTS["weapon"] = "bare_hands"`; migration in `load()` |
| `game/game_controller.py` | Scatter filter; pickup drop guard; remove "no weapons" block |

### `data/items.json` entry
```json
{"id": "bare_hands", "name": "Bare Hands", "type": "weapon", "slot": "weapon",
 "damage": 5, "defense": 0, "scatter": false,
 "description": "Your fists — desperate, but never absent", "rarity": "default"}
```

### `game/game_state.py` migration
```python
# In load(), after loading player data:
if player["equipped"].get("weapon") is None:
    player["equipped"]["weapon"] = "bare_hands"
```

---

## Phase 3.3 — Health Potion

### Goal
Add a consumable potion item that heals the player instantly on pickup. The potion is never stored in inventory or bag — it is consumed immediately and removed from the room. Fits the voice-only model (no "use item" command needed).

### Key Design Decisions

- **`type: "potion"`**: New item type alongside weapon/armor/key
- **Instant consumption**: Removed from room, never enters bag/equipped; `_state.heal()` called immediately
- **`heal` field on item**: Amount of HP recovered; capped at `max_hp` by `heal()` method
- **Returns actual HP gained**: `heal()` returns `new_hp - old_hp`, passed to narration for accuracy
- **`state_updated` signal**: `_emit_state()` called after heal so `lbl_player_hp` updates immediately

### Files Changed

| File | Change |
|------|--------|
| `data/items.json` | Add `health_potion` with `heal: 30`, `type: "potion"` |
| `game/game_state.py` | Add `heal(amount) -> int` method |
| `ai/prompts.py` | Add `build_potion_use_user_prompt()` |
| `ai/narrator.py` | Add `narrate_potion_use()` |
| `game/game_controller.py` | Add `"potion"` branch in `_handle_pickup()`; add `_trigger_potion_narration()` |

### `data/items.json` entry
```json
{"id": "health_potion", "name": "Health Potion", "type": "potion", "slot": null,
 "damage": 0, "defense": 0, "heal": 30,
 "description": "A vial of crimson liquid that smells of iron and herbs", "rarity": "uncommon"}
```

### `game/game_state.py` — `heal()` method
```python
def heal(self, amount: int) -> int:
    """Increase HP by amount, capped at max_hp. Returns actual HP gained."""
    old_hp = self._data["player"]["hp"]
    new_hp = min(old_hp + amount, self._data["player"]["max_hp"])
    self._data["player"]["hp"] = new_hp
    return new_hp - old_hp
```

### `game/game_controller.py` — potion branch in `_handle_pickup()`
```python
elif item_type == "potion":
    heal_amount = item.get("heal", 0)
    gained      = self._state.heal(heal_amount)
    self._state.remove_room_item(room_id, action.item_id)
    self._state.save()
    self._emit_state()
    self._signals.room_items_changed.emit(self._room_items_as_dicts(room_id))
    self._trigger_potion_narration(item["name"], gained, self._state.hp, self._state.max_hp)
```

### `game/game_controller.py` — `_trigger_potion_narration()`
```python
def _trigger_potion_narration(
    self, item_name: str, hp_gained: int, new_hp: int, max_hp: int
) -> None:
    self._signals.narration_started.emit()
    room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

    def fn():
        return self._narrator.narrate_potion_use(item_name, hp_gained, new_hp, max_hp, room_name)

    self._narration_worker = SimpleNarrationWorker(fn)
    self._narration_worker.finished.connect(self._on_narration_done)
    self._narration_worker.error.connect(self._on_narration_error)
    self._narration_worker.start()
```

### `ai/prompts.py` — `build_potion_use_user_prompt()`
```python
def build_potion_use_user_prompt(
    item_name: str, hp_gained: int, new_hp: int, max_hp: int, room_name: str
) -> str:
    return (
        f"The player drank the {item_name} in {room_name} and recovered {hp_gained} HP "
        f"(now {new_hp}/{max_hp}). "
        "Write 1 sentence describing them drinking it and feeling restored. "
        "Brief and atmospheric. Second person. No markdown."
    )
```

---

## Bug Fix — Flee from Combat

### Symptom
When inside a boss/monster room and in combat, attempting to move to another room returned `action='unknown'` from the intent parser. The player was effectively trapped.

### Root Cause
`_on_transcript_ready()` passed `exits = self._dungeon.get_exit_names(room_id) if not self._in_combat else []`. During combat, exits were hidden from the intent parser, so "go west" had no valid exits to match against → `unknown`.

### Fix

**`_on_transcript_ready()`** — always pass exits:
```python
exits = self._dungeon.get_exit_names(room_id)
# removed: "if not self._in_combat else []"
```

**`_handle_move()` step 4** — reset combat state on flee:
```python
# 4. Normal movement — cancel any active combat if the player flees
if self._in_combat:
    self._in_combat     = False
    self._current_enemy = None
    self._enemy_type    = None
    self._signals.combat_ended.emit()
```

---

## Verification

1. New game → weapon slot shows "Bare Hands (ATK 5)"; no "no weapons" error on attack
2. Pick up Iron Sword → weapon slot updates; Bare Hands silently removed (not in room)
3. Pick up armor → armor label updates; old armor drops to room floor
4. Armor defense reduces combat damage
5. Health potion appears scattered in a non-boss/non-home room
6. Say "grab the potion" → potion removed; HP label updates; narration plays with exact HP gained
7. Potion at full HP → gained=0; narration still plays
8. In boss room, say "go west" → player flees; boss HP bar hides; combat state reset
9. Flee then return to boss room → combat resumes (boss not cleared)
