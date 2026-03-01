import json
import logging
from pathlib import Path


class DungeonMap:
    """
    Loads maps/dungeon_map.json and exposes read-only graph query methods.
    Rooms are stored as a dict keyed by room ID.
    Does not mutate any state.
    """

    def __init__(self, map_file: Path):
        self._data: dict  = {}
        self._rooms: dict = {}   # {room_id: room_dict}
        self._load(map_file)

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self, map_file: Path) -> None:
        with open(map_file, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        self._rooms = self._data["rooms"]

        # Basic validation
        home_rooms = [r for r in self._rooms.values() if r.get("type") == "home"]
        exit_rooms = [r for r in self._rooms.values() if r.get("type") == "exit"]

        if not home_rooms:
            raise ValueError("DungeonMap: no room with type='home' found.")
        if not exit_rooms:
            raise ValueError("DungeonMap: no room with type='exit' found.")

        # Validate all exit targets exist
        for room in self._rooms.values():
            for direction, target_id in room.get("exits", {}).items():
                if target_id not in self._rooms:
                    logging.warning(
                        f"DungeonMap: room '{room['id']}' exit '{direction}' "
                        f"points to unknown room '{target_id}'."
                    )

        logging.info(
            f"DungeonMap loaded: {len(self._rooms)} rooms, "
            f"theme='{self._data.get('theme', 'unknown')}'"
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_room(self, room_id: str) -> dict:
        """Return the room dict for room_id. Raises KeyError if not found."""
        if room_id not in self._rooms:
            raise KeyError(f"DungeonMap: unknown room id '{room_id}'.")
        return self._rooms[room_id]

    def get_exits(self, room_id: str) -> dict[str, str]:
        """Return {direction: target_room_id} for the given room."""
        return dict(self._rooms[room_id].get("exits", {}))

    def get_exit_names(self, room_id: str) -> list[str]:
        """Return the list of available direction strings from room_id."""
        return list(self._rooms[room_id].get("exits", {}).keys())

    def get_room_type(self, room_id: str) -> str:
        """Return the type string ('normal', 'boss', 'home', 'exit')."""
        return self._rooms[room_id].get("type", "normal")

    def get_home_room_id(self) -> str:
        """Return the ID of the room with type='home'."""
        for room_id, room in self._rooms.items():
            if room.get("type") == "home":
                return room_id
        raise ValueError("DungeonMap: no home room found.")

    def is_valid_exit(self, from_room_id: str, direction: str) -> bool:
        """True if direction is a valid exit from from_room_id."""
        return direction in self._rooms.get(from_room_id, {}).get("exits", {})

    def resolve_direction(self, from_room_id: str, direction: str) -> str | None:
        """Return target room_id for the given direction, or None if invalid."""
        return self._rooms.get(from_room_id, {}).get("exits", {}).get(direction)

    def get_named_exits(self, room_id: str) -> dict[str, str]:
        """
        Return {direction: target_room_name} for use in LLM narration prompts.
        """
        exits = self.get_exits(room_id)
        return {
            direction: self._rooms[target_id]["name"]
            for direction, target_id in exits.items()
            if target_id in self._rooms
        }

    def get_boss_id(self, room_id: str) -> str | None:
        """Return the boss_id for a room, or None if the room has no boss."""
        return self._rooms.get(room_id, {}).get("boss_id")

    def get_all_boss_room_ids(self) -> list[str]:
        """Return IDs of all rooms with type == 'boss'."""
        return [rid for rid, r in self._rooms.items() if r.get("type") == "boss"]

    def is_locked(self, room_id: str) -> bool:
        """True if the room has locked: true in map data."""
        return bool(self._rooms.get(room_id, {}).get("locked", False))

    def get_required_key(self, room_id: str) -> str | None:
        """Return the key_id required to enter room_id, or None."""
        return self._rooms.get(room_id, {}).get("key_id")

    @property
    def theme(self) -> str:
        return self._data.get("theme", "dungeon")

    @property
    def all_room_ids(self) -> list[str]:
        return list(self._rooms.keys())
