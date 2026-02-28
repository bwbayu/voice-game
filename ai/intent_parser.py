import logging
from typing import Literal, Optional

from pydantic import BaseModel

from ai.mistral_client import MistralClient
from ai.prompts import (
    build_intent_system_prompt,
    build_intent_user_prompt,
    build_combat_intent_system_prompt,
    build_combat_intent_user_prompt,
    build_pickup_intent_system_prompt,
    build_pickup_intent_user_prompt,
)
from config import INTENT_MODEL


class IntentAction(BaseModel):
    """Structured output schema for player intent parsing."""
    action:    Literal["move", "pickup", "get", "collect", "attack", "unknown"]
    direction: Optional[str] = None   # only set when action == "move"
    item_id:   Optional[str] = None   # only set when action == "pickup" or "attack"


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
        Parse a transcript into a movement IntentAction.

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

    def parse_combat(
        self, transcript: str, inventory_items: list[dict]
    ) -> IntentAction:
        """
        Parse a transcript for attack intent during combat.
        Validates item_id is in inventory_items.
        Returns IntentAction(action="unknown") if no valid weapon found.
        """
        if not transcript.strip():
            return IntentAction(action="unknown")

        system = build_combat_intent_system_prompt()
        user   = build_combat_intent_user_prompt(transcript, inventory_items)
        valid_ids = {i["id"] for i in inventory_items}

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
            logging.warning(f"IntentParser.parse_combat: API call failed — {e}")
            return IntentAction(action="unknown")

        if result.action == "attack" and result.item_id not in valid_ids:
            logging.info(
                f"IntentParser.parse_combat: item_id '{result.item_id}' "
                f"not in inventory — returning unknown."
            )
            return IntentAction(action="unknown")

        logging.debug(f"IntentParser.parse_combat: '{transcript}' → {result}")
        return result

    def parse_pickup(
        self, transcript: str, room_items: list[dict]
    ) -> IntentAction:
        """
        Parse a transcript for pickup intent.
        Validates item_id is in room_items.
        Returns IntentAction(action="unknown") if no valid item found.
        """
        if not transcript.strip():
            return IntentAction(action="unknown")

        system = build_pickup_intent_system_prompt()
        user   = build_pickup_intent_user_prompt(transcript, room_items)
        valid_ids = {i["id"] for i in room_items}

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
            logging.warning(f"IntentParser.parse_pickup: API call failed — {e}")
            return IntentAction(action="unknown")

        if result.action == "pickup" and result.item_id not in valid_ids:
            logging.info(
                f"IntentParser.parse_pickup: item_id '{result.item_id}' "
                f"not in room — returning unknown."
            )
            return IntentAction(action="unknown")

        logging.debug(f"IntentParser.parse_pickup: '{transcript}' → {result}")
        return result
