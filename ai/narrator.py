import logging

from ai.mistral_client import MistralClient
from ai.tts_client import TTSClient
from ai.prompts import (
    build_narration_system_prompt,
    build_narration_user_prompt,
    build_win_narration_user_prompt,
    build_boss_entry_user_prompt,
    build_combat_round_user_prompt,
    build_boss_defeat_user_prompt,
    build_exit_blocked_user_prompt,
    build_pickup_narration_user_prompt,
    build_potion_use_user_prompt,
    build_death_narration_user_prompt,
    build_monster_encounter_user_prompt,
    build_monster_defeat_user_prompt,
    build_locked_room_user_prompt,
    build_unlock_room_user_prompt,
    build_swap_narration_user_prompt,
)


class Narrator:
    """
    Orchestrates the full narration pipeline:
      1. Build a prompt from room data.
      2. Call Mistral LLM → narration text.
      3. Call OpenAI TTS → WAV file.
      4. Return (text, wav_path) tuple.

    All methods are blocking and MUST be called from a worker thread,
    never from the main Qt thread.
    """

    def __init__(self, mistral_client: MistralClient, tts_client: TTSClient):
        self._mistral = mistral_client
        self._tts     = tts_client

    def narrate_room(
        self,
        room: dict,
        named_exits: dict[str, str],        # {direction: target_room_name}
        previous_room_name: str | None,
        room_items: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Generate narration for a room entry.
        Returns (narration_text, wav_file_path).
        Raises on unrecoverable API error.
        """
        system = build_narration_system_prompt()
        user   = build_narration_user_prompt(
            room_name=room["name"],
            description_hint=room.get("description_hint", ""),
            exits=named_exits,
            previous_room_name=previous_room_name,
            room_items=room_items,
        )
        logging.debug(f"Narrator: generating narration for '{room['name']}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_win(self, room_name: str) -> tuple[str, str]:
        """
        Generate victory narration for reaching the exit room.
        Returns (narration_text, wav_file_path).
        """
        system   = build_narration_system_prompt()
        user     = build_win_narration_user_prompt(room_name)
        logging.debug("Narrator: generating win narration.")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_boss_entry(
        self,
        boss_name: str,
        room: dict,
        previous_room_name: str | None,
    ) -> tuple[str, str]:
        """Generate boss room entry narration."""
        system = build_narration_system_prompt()
        user   = build_boss_entry_user_prompt(
            boss_name=boss_name,
            room_name=room["name"],
            room_hint=room.get("description_hint", ""),
            previous_room_name=previous_room_name,
        )
        logging.debug(f"Narrator: generating boss entry narration for '{boss_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_combat_round(
        self,
        boss_name: str,
        item_name: str,
        player_damage: int,
        skill_name: str,
        boss_damage: int,
        player_hp: int,
        boss_hp: int,
    ) -> tuple[str, str]:
        """Generate narration for one combat exchange."""
        system = build_narration_system_prompt()
        user   = build_combat_round_user_prompt(
            boss_name=boss_name,
            item_name=item_name,
            player_damage=player_damage,
            skill_name=skill_name,
            boss_damage=boss_damage,
            player_hp=player_hp,
            boss_hp=boss_hp,
        )
        logging.debug("Narrator: generating combat round narration.")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_boss_defeat(self, boss_name: str) -> tuple[str, str]:
        """Generate narration for boss death."""
        system   = build_narration_system_prompt()
        user     = build_boss_defeat_user_prompt(boss_name)
        logging.debug(f"Narrator: generating boss defeat narration for '{boss_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_exit_blocked(self) -> tuple[str, str]:
        """Generate narration when player tries to enter exit with living bosses."""
        system   = build_narration_system_prompt()
        user     = build_exit_blocked_user_prompt()
        logging.debug("Narrator: generating exit blocked narration.")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_pickup(self, item_name: str, room_name: str) -> tuple[str, str]:
        """Generate narration for picking up an item."""
        system   = build_narration_system_prompt()
        user     = build_pickup_narration_user_prompt(item_name, room_name)
        logging.debug(f"Narrator: generating pickup narration for '{item_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    # ── Phase 3 narration ──────────────────────────────────────────────────────

    def narrate_death(self, room_name: str, killer_name: str) -> tuple[str, str]:
        """Generate player death narration."""
        system   = build_narration_system_prompt()
        user     = build_death_narration_user_prompt(room_name, killer_name)
        logging.debug(f"Narrator: generating death narration — killed by '{killer_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_monster_encounter(
        self,
        monster_name: str,
        room: dict,
        previous_room_name: str | None,
    ) -> tuple[str, str]:
        """Generate narration for encountering a roaming monster."""
        system   = build_narration_system_prompt()
        user     = build_monster_encounter_user_prompt(
            monster_name, room["name"], previous_room_name
        )
        logging.debug(f"Narrator: generating monster encounter narration for '{monster_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_monster_defeat(self, monster_name: str) -> tuple[str, str]:
        """Generate narration for defeating a roaming monster."""
        system   = build_narration_system_prompt()
        user     = build_monster_defeat_user_prompt(monster_name)
        logging.debug(f"Narrator: generating monster defeat narration for '{monster_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_locked_room(self, room_name: str, key_name: str | None) -> tuple[str, str]:
        """Generate narration when player hits a locked door."""
        system   = build_narration_system_prompt()
        user     = build_locked_room_user_prompt(room_name, key_name)
        logging.debug(f"Narrator: generating locked room narration for '{room_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_unlock(self, room_name: str) -> tuple[str, str]:
        """Generate narration when player unlocks a door with a key."""
        system   = build_narration_system_prompt()
        user     = build_unlock_room_user_prompt(room_name)
        logging.debug(f"Narrator: generating unlock narration for '{room_name}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_potion_use(
        self, item_name: str, hp_gained: int, new_hp: int, max_hp: int, room_name: str
    ) -> tuple[str, str]:
        """Generate narration when player drinks a healing potion."""
        system   = build_narration_system_prompt()
        user     = build_potion_use_user_prompt(item_name, hp_gained, new_hp, max_hp, room_name)
        logging.debug(f"Narrator: generating potion use narration (+{hp_gained} HP)")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path

    def narrate_swap(self, new_item: str, old_item: str, room_name: str) -> tuple[str, str]:
        """Generate narration when player swaps one equipment piece for another."""
        system   = build_narration_system_prompt()
        user     = build_swap_narration_user_prompt(new_item, old_item, room_name)
        logging.debug(f"Narrator: generating swap narration '{old_item}' → '{new_item}'")
        text     = self._mistral.complete(system, user)
        wav_path = self._tts.speak(text)
        return text, wav_path
