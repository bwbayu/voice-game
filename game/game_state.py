import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import STATE_DIR

_EQUIPPED_DEFAULTS = {
    "weapon": "bare_hands",
    "helmet": None,
    "suit":   None,
    "legs":   None,
    "shoes":  None,
    "cloak":  None,
    "shield": None,
}

_DEFAULT_STATE = {
    "player": {
        "current_room": "home",
        "hp": 100,
        "max_hp": 100,
        "equipped": dict(_EQUIPPED_DEFAULTS),
        "bag": [],       # key items only
        "last_action": "game started",
    },
    "world": {
        "cleared_bosses": [],
        "room_items": {},
        "boss_hp": {},
        "monster_hp": {},
        "monster_positions": {},
        "unlocked_rooms": [],
    },
    "meta": {
        "theme": "dungeon",
        "difficulty": "medium",
        "session_start": None,
    },
}


class GameState:
    """
    Owns all mutable game state: player position, HP, equipment, world state.
    Persists to / loads from state/game_state.json.
    All mutations are explicit methods; call save() after any mutation.
    """

    def __init__(self, state_file: Path):
        self._path = state_file
        self._data: dict = {}
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Read state file from disk. Creates default state if file is absent."""
        if not self._path.exists():
            logging.info("GameState: no state file found — writing defaults.")
            self._data = json.loads(json.dumps(_DEFAULT_STATE))  # deep copy
            self._touch_session_start()
            self._write()
            return

        with open(self._path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        # ── Migration: old flat inventory → equipped + bag ───────────────────
        player = self._data["player"]
        if "inventory" in player and "equipped" not in player:
            player["bag"] = player.pop("inventory", [])
            player["equipped"] = dict(_EQUIPPED_DEFAULTS)
            self._write()
            logging.info("GameState: migrated inventory → equipped + bag")
        player.setdefault("bag", [])
        player.setdefault("equipped", dict(_EQUIPPED_DEFAULTS))

        # Migrate: ensure bare_hands fallback for saves that had weapon: null
        if player["equipped"].get("weapon") is None:
            player["equipped"]["weapon"] = "bare_hands"
            self._write()

        if self._data["meta"]["session_start"] is None:
            self._touch_session_start()
            self._write()

    def save(self) -> None:
        """Atomic write: write to .tmp then os.replace() — safe on Windows."""
        self._write()

    def _write(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)

    def _touch_session_start(self) -> None:
        self._data["meta"]["session_start"] = (
            datetime.now(timezone.utc).isoformat()
        )

    # ── Player read helpers ───────────────────────────────────────────────────

    @property
    def current_room_id(self) -> str:
        return self._data["player"]["current_room"]

    @property
    def hp(self) -> int:
        return self._data["player"]["hp"]

    @property
    def max_hp(self) -> int:
        return self._data["player"]["max_hp"]

    @property
    def inventory(self) -> list[str]:
        """Union of all equipped item_ids + bag — backward compat for 'item in state.inventory'."""
        eq  = self._data["player"].get("equipped", {})
        bag = self._data["player"].get("bag", [])
        return [v for v in eq.values() if v] + list(bag)

    @property
    def equipped(self) -> dict[str, str | None]:
        """Return {slot: item_id | None} for all equipment slots."""
        return dict(self._data["player"]["equipped"])

    @property
    def bag(self) -> list[str]:
        """Return key items in the bag."""
        return list(self._data["player"].get("bag", []))

    @property
    def last_action(self) -> str:
        return self._data["player"]["last_action"]

    # ── World read helpers ────────────────────────────────────────────────────

    def is_boss_cleared(self, boss_id: str) -> bool:
        return boss_id in self._data["world"]["cleared_bosses"]

    # ── Room items ────────────────────────────────────────────────────────────

    def get_room_items(self, room_id: str) -> list[str]:
        """Return list of item_ids currently in the given room."""
        return list(self._data["world"]["room_items"].get(room_id, []))

    def set_room_items(self, room_id: str, items: list[str]) -> None:
        self._data["world"]["room_items"][room_id] = items

    def remove_room_item(self, room_id: str, item_id: str) -> None:
        items = self._data["world"]["room_items"].get(room_id, [])
        if item_id in items:
            items.remove(item_id)
        self._data["world"]["room_items"][room_id] = items

    def needs_item_scatter(self) -> bool:
        """True when room_items has never been populated (first run)."""
        return not bool(self._data["world"].get("room_items"))

    # ── Equipment ─────────────────────────────────────────────────────────────

    def get_equipped_in_slot(self, slot: str) -> str | None:
        return self._data["player"]["equipped"].get(slot)

    def equip_item(self, slot: str, item_id: str) -> str | None:
        """Put item_id in slot. Returns displaced item_id or None."""
        old = self._data["player"]["equipped"].get(slot)
        self._data["player"]["equipped"][slot] = item_id
        return old

    # ── Bag (keys) ────────────────────────────────────────────────────────────

    def add_to_bag(self, item_id: str) -> bool:
        """Add key item to bag. Returns False if at INVENTORY_CAP."""
        from config import INVENTORY_CAP
        bag = self._data["player"].setdefault("bag", [])
        if len(bag) >= INVENTORY_CAP:
            return False
        bag.append(item_id)
        return True

    def remove_from_bag(self, item_id: str) -> None:
        bag = self._data["player"].get("bag", [])
        if item_id in bag:
            bag.remove(item_id)

    def heal(self, amount: int) -> int:
        """Increase HP by amount, capped at max_hp. Returns actual HP gained."""
        old_hp = self._data["player"]["hp"]
        new_hp = min(old_hp + amount, self._data["player"]["max_hp"])
        self._data["player"]["hp"] = new_hp
        return new_hp - old_hp

    def remove_from_inventory(self, item_id: str) -> None:
        """Remove from bag or any equipped slot (used for key consumption on unlock)."""
        bag = self._data["player"].get("bag", [])
        if item_id in bag:
            bag.remove(item_id)
            return
        eq = self._data["player"].get("equipped", {})
        for slot, eid in eq.items():
            if eid == item_id:
                eq[slot] = None
                return

    # ── Boss HP ───────────────────────────────────────────────────────────────

    def get_boss_hp(self, boss_id: str, max_hp: int) -> int:
        """Return current HP for boss_id, initialising to max_hp if absent."""
        boss_hp_map = self._data["world"].setdefault("boss_hp", {})
        if boss_id not in boss_hp_map:
            boss_hp_map[boss_id] = max_hp
        return boss_hp_map[boss_id]

    def set_boss_hp(self, boss_id: str, hp: int) -> None:
        self._data["world"].setdefault("boss_hp", {})[boss_id] = hp

    # ── Monster positions ─────────────────────────────────────────────────────

    def get_monster_positions(self) -> dict[str, str]:
        """Return {monster_id: room_id} for all living monsters."""
        return dict(self._data["world"].get("monster_positions", {}))

    def set_monster_position(self, monster_id: str, room_id: str) -> None:
        self._data["world"].setdefault("monster_positions", {})[monster_id] = room_id

    def remove_monster(self, monster_id: str) -> None:
        """Remove a monster from the world on death."""
        self._data["world"].get("monster_positions", {}).pop(monster_id, None)
        self._data["world"].get("monster_hp", {}).pop(monster_id, None)

    def get_monsters_in_room(self, room_id: str) -> list[str]:
        """Return list of monster_ids currently in room_id."""
        return [mid for mid, rid in self.get_monster_positions().items() if rid == room_id]

    def needs_monster_scatter(self) -> bool:
        """True when monster_positions is empty (first run or after reset)."""
        return not bool(self._data["world"].get("monster_positions"))

    # ── Monster HP ────────────────────────────────────────────────────────────

    def get_monster_hp(self, monster_id: str, max_hp: int) -> int:
        """Return current HP for monster_id, initialising to max_hp if absent."""
        hp_map = self._data["world"].setdefault("monster_hp", {})
        if monster_id not in hp_map:
            hp_map[monster_id] = max_hp
        return hp_map[monster_id]

    def set_monster_hp(self, monster_id: str, hp: int) -> None:
        self._data["world"].setdefault("monster_hp", {})[monster_id] = hp

    # ── Locked rooms ──────────────────────────────────────────────────────────

    @property
    def unlocked_rooms(self) -> list[str]:
        return list(self._data["world"].get("unlocked_rooms", []))

    def unlock_room(self, room_id: str) -> None:
        unlocked = self._data["world"].setdefault("unlocked_rooms", [])
        if room_id not in unlocked:
            unlocked.append(room_id)

    # ── Player mutations ──────────────────────────────────────────────────────

    def move_player(self, target_room_id: str) -> None:
        """Update current room. Does NOT validate the move — that is GameController's job."""
        self._data["player"]["current_room"] = target_room_id

    def set_last_action(self, description: str) -> None:
        self._data["player"]["last_action"] = description

    def mark_boss_cleared(self, boss_id: str) -> None:
        cleared = self._data["world"]["cleared_bosses"]
        if boss_id not in cleared:
            cleared.append(boss_id)

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a full deep-copy snapshot for use in LLM prompt context."""
        return json.loads(json.dumps(self._data))

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Overwrite state with defaults and save. Used for Game Over / new game."""
        self._data = json.loads(json.dumps(_DEFAULT_STATE))
        self._touch_session_start()
        self._write()
