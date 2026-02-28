import logging
from typing import Literal, Optional

from pydantic import BaseModel

from ai.mistral_client import MistralClient
from ai.prompts import (
    build_unified_intent_system_prompt,
    build_unified_intent_user_prompt,
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
    A single parse() call receives the full game context and lets the LLM
    decide the action (move / attack / pickup / unknown) in one shot.
    """

    def __init__(self, mistral_client: MistralClient):
        self._client = mistral_client

    def parse(
        self,
        transcript: str,
        exits: list[str],
        weapons: list[dict],
        room_items: list[dict],
    ) -> IntentAction:
        """
        Parse a transcript into an IntentAction given full game context.

        exits      — available exit direction strings (empty list if in combat)
        weapons    — weapon dicts from inventory (empty list if not in combat)
        room_items — item dicts on the floor (always pass current room items)

        Validates that returned direction / item_id are actually available.
        Returns IntentAction(action="unknown") on any failure or bad data.
        """
        if not transcript.strip():
            return IntentAction(action="unknown")

        system = build_unified_intent_system_prompt()
        user   = build_unified_intent_user_prompt(transcript, exits, weapons, room_items)

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

        # Validate direction is a real exit
        if result.action == "move" and result.direction not in exits:
            logging.info(
                f"IntentParser: direction '{result.direction}' not in {exits} — unknown."
            )
            return IntentAction(action="unknown")

        # Validate item_id is in the expected set
        valid_weapon_ids = {i["id"] for i in weapons}
        valid_item_ids   = {i["id"] for i in room_items}
        if result.action == "attack" and result.item_id not in valid_weapon_ids:
            # LLM recognized attack intent but didn't fill in item_id — default to first weapon
            if weapons:
                result = IntentAction(action="attack", item_id=weapons[0]["id"])
                logging.debug(
                    f"IntentParser: attack with no weapon id — defaulting to '{weapons[0]['name']}'"
                )
            else:
                return IntentAction(action="unknown")
        if result.action == "pickup" and result.item_id not in valid_item_ids:
            logging.info(
                f"IntentParser: item id '{result.item_id}' not in room — unknown."
            )
            return IntentAction(action="unknown")

        logging.debug(f"IntentParser: '{transcript}' → {result}")
        return result
