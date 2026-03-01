import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import STATE_DIR

_DEFAULT_STATE = {
    "player": {
        "current_room": "home",
        "hp": 100,
        "max_hp": 100,
        "inventory": [],
        "last_action": "game started",
    },
    "world": {
        "cleared_bosses": [],
        "room_items": {},
        "boss_hp": {},
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
    Owns all mutable game state: player position, HP, inventory, world state.
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
        return list(self._data["player"]["inventory"])

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

    # ── Inventory ─────────────────────────────────────────────────────────────

    def add_to_inventory(self, item_id: str) -> bool:
        """Add item_id to inventory. Returns False if at INVENTORY_CAP."""
        from config import INVENTORY_CAP
        inv = self._data["player"]["inventory"]
        if len(inv) >= INVENTORY_CAP:
            return False
        inv.append(item_id)
        return True

    def remove_from_inventory(self, item_id: str) -> None:
        inv = self._data["player"]["inventory"]
        if item_id in inv:
            inv.remove(item_id)

    # ── Boss HP ───────────────────────────────────────────────────────────────

    def get_boss_hp(self, boss_id: str, max_hp: int) -> int:
        """Return current HP for boss_id, initialising to max_hp if absent."""
        boss_hp_map = self._data["world"].setdefault("boss_hp", {})
        if boss_id not in boss_hp_map:
            boss_hp_map[boss_id] = max_hp
        return boss_hp_map[boss_id]

    def set_boss_hp(self, boss_id: str, hp: int) -> None:
        self._data["world"].setdefault("boss_hp", {})[boss_id] = hp

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
