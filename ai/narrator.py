import logging

from ai.mistral_client import MistralClient
from ai.tts_client import TTSClient
from ai.prompts import (
    build_narration_system_prompt,
    build_narration_user_prompt,
    build_win_narration_user_prompt,
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
