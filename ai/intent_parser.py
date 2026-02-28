import logging
from typing import Literal, Optional

from pydantic import BaseModel

from ai.mistral_client import MistralClient
from ai.prompts import build_intent_system_prompt, build_intent_user_prompt
from config import INTENT_MODEL


class IntentAction(BaseModel):
    """Structured output schema for player intent parsing."""
    action: Literal["move", "unknown"]
    direction: Optional[str] = None   # only set when action == "move"


class IntentParser:
    """
    Converts a speech transcript into a validated IntentAction.
    Uses Mistral client.chat.parse() with a Pydantic response_format
    so no JSON stripping or manual validation is needed.
    """

    def __init__(self, mistral_client: MistralClient):
        self._client = mistral_client

    def parse(self, transcript: str, available_directions: list[str]) -> IntentAction:
        """
        Parse a transcript into an IntentAction.

        Steps:
          1. Guard against empty transcript.
          2. Call client.chat.parse() with IntentAction schema.
          3. Validate the returned direction is in available_directions.
          4. Return IntentAction(action="unknown") on any failure.
        """
        if not transcript.strip():
            logging.debug("IntentParser: empty transcript — returning unknown.")
            return IntentAction(action="unknown")

        system = build_intent_system_prompt()
        user   = build_intent_user_prompt(transcript, available_directions)

        try:
            result: IntentAction = self._client.parse(
                system_prompt=system,
                user_prompt=user,
                response_format=IntentAction,
                model=INTENT_MODEL,
                max_tokens=64,
                temperature=0,
            )
        except Exception as e:
            logging.warning(f"IntentParser: API call failed — {e}")
            return IntentAction(action="unknown")

        # Validate: direction must be a real exit
        if result.action == "move":
            if result.direction not in available_directions:
                logging.info(
                    f"IntentParser: direction '{result.direction}' not in "
                    f"{available_directions} — returning unknown."
                )
                return IntentAction(action="unknown")

        logging.debug(f"IntentParser: '{transcript}' → {result}")
        return result
