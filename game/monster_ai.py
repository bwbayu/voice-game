"""
MonsterManager — roaming monster logic for Phase 3.

Responsibilities:
  - scatter(): initial placement of monsters into eligible rooms
  - move_all(): advance each living monster one random step after each player move
  - Encounter detection is done in GameController, not here.
"""
import logging
import random


class MonsterManager:

    def scatter(
        self,
        monster_ids: list[str],
        dungeon_map,    # DungeonMap instance
        game_state,     # GameState instance
    ) -> None:
        """
        Place each monster_id into a random eligible room.
        Eligible: type == "normal". Avoids home, boss, and exit rooms.
        Caller must call game_state.save() after this.
        """
        eligible_rooms = [
            room_id for room_id, room in dungeon_map._rooms.items()
            if room.get("type") == "normal"
        ]
        if not eligible_rooms:
            logging.warning("MonsterManager.scatter: no eligible rooms found")
            return

        shuffled = eligible_rooms[:]
        random.shuffle(shuffled)
        for monster_id, room_id in zip(monster_ids, shuffled):
            game_state.set_monster_position(monster_id, room_id)
            logging.debug(f"MonsterManager.scatter: {monster_id} → {room_id}")

    def move_all(self, dungeon_map, game_state) -> None:
        """
        Move each living monster one step to a random adjacent normal room.
        Monsters cannot enter boss, home, or exit rooms.
        Caller must call game_state.save() after this.
        """
        positions = game_state.get_monster_positions()
        for monster_id, current_room_id in positions.items():
            exits = dungeon_map.get_exits(current_room_id)   # {direction: target_id}
            eligible = [
                target_id for target_id in exits.values()
                if dungeon_map.get_room(target_id).get("type") == "normal"
            ]
            if not eligible:
                continue   # monster is trapped, stays put
            new_room_id = random.choice(eligible)
            game_state.set_monster_position(monster_id, new_room_id)
            logging.debug(
                f"MonsterManager.move_all: {monster_id} {current_room_id} → {new_room_id}"
            )
