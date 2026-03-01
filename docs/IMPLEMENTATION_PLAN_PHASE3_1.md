# Phase 3.1 Implementation Plan — Equipment Slot System

## Context
Replaces the flat inventory list with a structured equipment system. The player now has named slots for gear (weapon + 6 armor pieces) and a bag for keys. The UI renders each slot individually with stat labels. Picking up gear auto-equips it, dropping the displaced item back in the room.

---

## Design

- **Slots**: `weapon`, `helmet`, `suit`, `legs`, `shoes`, `cloak`, `shield`
- **Bag**: holds keys only (no equip slot); max capacity enforced by `game_state`
- **Auto-equip**: Picking up a weapon or armor immediately equips it to the appropriate slot
- **Swap**: Displaced item drops to the current room floor (exception: `bare_hands` is silently discarded)
- **Defense**: Sum of defense values from all non-weapon equipped slots; applied as flat damage reduction per combat round
- **Signal type change**: `inventory_updated` → `pyqtSignal(dict)` with shape `{"equipped": {slot: item_dict|None}, "bag": [item_dicts]}`

---

## Files Changed

| File | Change |
|------|--------|
| `ui/signals.py` | `inventory_updated = pyqtSignal(dict)` |
| `ui/game_view.py` | `update_inventory(payload: dict)` renders weapon/armor/bag sections with ATK/DEF stats |
| `game/game_state.py` | Add `equipped`, `bag` properties; `equip_item()`, `add_to_bag()`, `remove_from_inventory()` |
| `game/game_controller.py` | (see detailed changes below) |
| `ai/prompts.py` | Add `build_swap_narration_user_prompt()` |
| `ai/narrator.py` | Add `narrate_swap()` |

---

## Detailed Changes

### `ui/signals.py`

```python
inventory_updated = pyqtSignal(dict)   # was: pyqtSignal(list)
```

---

### `ui/game_view.py`

**`update_inventory(payload: dict)`**:
- `payload["equipped"]` is `{slot: item_dict | None}`
- `payload["bag"]` is `[item_dict, ...]`
- Renders weapon slot as `"Weapon: Iron Sword (ATK 25)"`
- Renders armor slots grouped as `"Armor: Iron Helm (DEF 3), Chain Mail (DEF 5), ..."`
- Renders bag as `"Bag: Prison Key"`

**`update_room_items(items: list[dict])`** — shows `(ATK N)` or `(DEF N)` inline per item.

---

### `game/game_state.py`

**`_EQUIPPED_DEFAULTS`**:
```python
_EQUIPPED_DEFAULTS = {
    "weapon":  "bare_hands",
    "helmet":  None,
    "suit":    None,
    "legs":    None,
    "shoes":   None,
    "cloak":   None,
    "shield":  None,
}
```

**Properties**:
```python
@property
def equipped(self) -> dict[str, str | None]:
    return self._data["player"]["equipped"]

@property
def bag(self) -> list[str]:
    return self._data["player"]["bag"]
```

**`equip_item(slot, item_id) -> str | None`**:
- Sets `equipped[slot] = item_id`
- Returns the previously equipped item id (or `None`)

**`add_to_bag(item_id) -> bool`**:
- Returns `False` if bag is full (max enforced per config)
- Appends to `player.bag`

**`remove_from_inventory(item_id)`**:
- Checks both `equipped` values and `bag`; removes the first match

**`inventory` property** (read-only computed):
```python
@property
def inventory(self) -> list[str]:
    """Flat list of all carried item ids — equipped + bag."""
    items = [v for v in self._data["player"]["equipped"].values() if v]
    items += self._data["player"]["bag"]
    return items
```

---

### `game/game_controller.py`

#### `_emit_inventory()`
```python
def _emit_inventory(self) -> None:
    self._signals.inventory_updated.emit(self._equipment_payload())
```

#### `_equipment_payload()`
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

#### `_inventory_as_dicts()` (preserved — intent parser only)
```python
def _inventory_as_dicts(self) -> list[dict]:
    """Flat list of all carried items — used for intent parser context only."""
    return [self._item_registry[iid] for iid in self._state.inventory
            if iid in self._item_registry]
```

#### `_handle_pickup()` (full rewrite)
```python
def _handle_pickup(self, action: IntentAction) -> None:
    room_id    = self._state.current_room_id
    room_items = self._state.get_room_items(room_id)

    if action.item_id not in room_items:
        self._signals.error_occurred.emit("That item is not here.")
        return

    item = self._item_registry.get(action.item_id)
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
        self._trigger_potion_narration(item["name"], gained, self._state.hp, self._state.max_hp)

    else:
        self._signals.error_occurred.emit("You can't pick that up.")
```

#### Defense reduction in `_handle_attack()`
```python
defense       = self._compute_total_defense()
new_player_hp = max(0, self._state.hp - max(0, result.boss_damage - defense))
```

#### `_compute_total_defense()`
```python
def _compute_total_defense(self) -> int:
    """Sum of defense values across all equipped armor slots."""
    total = 0
    for slot, item_id in self._state.equipped.items():
        if slot != "weapon" and item_id and item_id in self._item_registry:
            total += self._item_registry[item_id].get("defense", 0)
    return total
```

#### `_trigger_swap_narration()`
```python
def _trigger_swap_narration(self, new_name: str, old_name: str) -> None:
    self._signals.narration_started.emit()
    room_name = self._dungeon.get_room(self._state.current_room_id)["name"]

    def fn():
        return self._narrator.narrate_swap(new_name, old_name, room_name)

    self._narration_worker = SimpleNarrationWorker(fn)
    self._narration_worker.finished.connect(self._on_narration_done)
    self._narration_worker.error.connect(self._on_narration_error)
    self._narration_worker.start()
```

#### Unlock path — emit inventory as dict
In `_handle_move()` when consuming a key to unlock a door:
```python
self._signals.inventory_updated.emit(self._equipment_payload())
```

---

### `ai/prompts.py`

```python
def build_swap_narration_user_prompt(
    new_name: str, old_name: str, room_name: str
) -> str:
    return (
        f"The player picked up {new_name} in {room_name}, "
        f"dropping their {old_name} to the floor. "
        "Write 1 sentence describing the swap — brief and atmospheric. "
        "Second person. No markdown."
    )
```

---

### `ai/narrator.py`

```python
def narrate_swap(self, new_name: str, old_name: str, room_name: str) -> tuple[str, str]:
    system   = build_narration_system_prompt()
    user     = build_swap_narration_user_prompt(new_name, old_name, room_name)
    text     = self._mistral.complete(system, user)
    wav_path = self._tts.speak(text)
    return text, wav_path
```

---

## Verification

1. Start new game → weapon slot shows "Bare Hands (ATK 5)"
2. Pick up Iron Sword → weapon slot updates; no Bare Hands in room
3. Pick up Battle Axe (already have sword) → axe equipped; sword appears on floor
4. Pick up armor → armor section updates; DEF stat shown
5. Pick up Prison Key → appears in bag section; error if bag full
6. Boss attack with Chain Mail equipped (DEF 5) → player takes `boss_damage - 5` damage
7. `inventory_updated` signal carries dict to `update_inventory()` in `game_view.py`
8. Room items list shows `(ATK N)` / `(DEF N)` for weapons/armor
