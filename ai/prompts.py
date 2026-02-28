"""
All LLM prompt strings live here.
Functions — not constants — because they need runtime data interpolated in.
No LLM calls anywhere in this file: pure string construction only.
"""


# ── Narration ─────────────────────────────────────────────────────────────────

def build_narration_system_prompt() -> str:
    return (
        "You are a dungeon master narrating a blind dungeon game. "
        "The player cannot see anything — your words are their only perception. "
        "Be atmospheric and concise (2–4 sentences). "
        "Always mention the available exit directions naturally within your description. "
        "Speak in second person: 'you see...', 'you hear...', 'you smell...'. "
        "Do not use markdown, lists, or formatting. Do not mention game mechanics or rules."
    )


def build_narration_user_prompt(
    room_name: str,
    description_hint: str,
    exits: dict[str, str],          # {direction: target_room_name}
    previous_room_name: str | None,
) -> str:
    exits_text = ", ".join(
        f"'{direction}' leading to {room_name}"
        for direction, room_name in exits.items()
    )
    if previous_room_name:
        origin_text = f"The player just came from: {previous_room_name}."
    else:
        origin_text = "This is the player's starting location."

    return (
        f"Room: {room_name}. "
        f"Atmosphere hints: {description_hint}. "
        f"Available exits: {exits_text}. "
        f"{origin_text}"
    )


# ── Win narration ─────────────────────────────────────────────────────────────

def build_win_narration_user_prompt(room_name: str) -> str:
    return (
        f"The player has finally reached {room_name}, the heart of the dungeon. "
        "This is the end of their journey. "
        "Narrate their triumph in 3–4 atmospheric sentences. "
        "The tone should be both ominous and victorious — they survived, "
        "but the dungeon will always remember them."
    )


# ── Intent parsing ────────────────────────────────────────────────────────────

def build_intent_system_prompt() -> str:
    return (
        "You are an intent parser for a voice-controlled dungeon game. "
        "The player spoke a command. Extract their movement intent. "
        "If the player wants to move in a direction that matches one of the available exits, "
        "set action to 'move' and direction to the exact matching direction string. "
        "If the intent is unclear or does not match any exit, set action to 'unknown'. "
        "Output a structured JSON response only."
    )


def build_intent_user_prompt(
    transcript: str,
    available_directions: list[str],
) -> str:
    dirs = ", ".join(f'"{d}"' for d in available_directions)
    return (
        f"Player said: \"{transcript}\". "
        f"Available exit directions: [{dirs}]. "
        "What direction does the player want to go?"
    )
