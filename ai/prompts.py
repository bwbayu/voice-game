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
    room_items: list[str] | None = None,   # item names present in room
) -> str:
    exits_text = ", ".join(
        f"'{direction}' leading to {room_name}"
        for direction, room_name in exits.items()
    )
    if previous_room_name:
        origin_text = f"The player just came from: {previous_room_name}."
    else:
        origin_text = "This is the player's starting location."

    items_text = ""
    if room_items:
        items_text = (
            " Items visible in this room: "
            + ", ".join(room_items)
            + ". Mention one or two of these items naturally."
        )

    return (
        f"Room: {room_name}. "
        f"Atmosphere hints: {description_hint}. "
        f"Available exits: {exits_text}. "
        f"{origin_text}"
        f"{items_text}"
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


# ── Phase 2 narration ─────────────────────────────────────────────────────────

def build_boss_entry_user_prompt(
    boss_name: str,
    room_name: str,
    room_hint: str,
    previous_room_name: str | None,
) -> str:
    origin = f"came from {previous_room_name}" if previous_room_name else "entered"
    return (
        f"The player {origin} and now stands in {room_name}. "
        f"Atmosphere: {room_hint}. "
        f"{boss_name} is here, blocking the way. "
        "Write 4–6 sentences of ominous atmosphere. "
        "Describe the boss's presence dramatically. "
        "Do NOT mention exits or how to leave. "
        "Do NOT mention game mechanics, items, or combat rules. "
        "Speak in second person."
    )


def build_combat_round_user_prompt(
    boss_name: str,
    item_name: str,
    player_damage: int,
    skill_name: str,
    boss_damage: int,
    player_hp: int,
    boss_hp: int,
) -> str:
    return (
        f"The player struck {boss_name} with the {item_name} for {player_damage} damage. "
        f"{boss_name} retaliated with {skill_name} for {boss_damage} damage. "
        f"Player HP is now {player_hp}. {boss_name} HP is now {boss_hp}. "
        "Write exactly 2 atmospheric sentences describing this exchange. "
        "Second person. No game mechanics. No markdown."
    )


def build_boss_defeat_user_prompt(boss_name: str) -> str:
    return (
        f"{boss_name} has been defeated — their HP has reached zero. "
        "Write 3–4 sentences describing the boss falling. "
        "The tone is triumphant but with an undercurrent of dread — "
        "the dungeon feels the loss. Second person. No markdown."
    )


def build_exit_blocked_user_prompt() -> str:
    return (
        "The player tried to enter the final chamber but cannot — "
        "a guardian still lives somewhere in the dungeon. "
        "Write 2–3 sentences: the exit is sealed by dark energy, "
        "and the player senses an undefeated presence. "
        "Second person. No markdown. No game mechanics."
    )


def build_pickup_narration_user_prompt(item_name: str, room_name: str) -> str:
    return (
        f"The player picked up the {item_name} in {room_name}. "
        "Write 1–2 sentences describing them pocketing it. "
        "Brief and atmospheric. Second person. No markdown."
    )


def build_boss_taunt_user_prompt(
    boss_name: str,
    skill_name: str,
) -> str:
    return (
        f"{boss_name} uses {skill_name}"
        "Write ONLY the skill name as a short battle cry — 2 to 4 words maximum, "
        "spoken by the boss (e.g. 'Stone Crush!' or 'Taste the shadows!'). "
        "No sentences, no explanation, no markdown. Just the short cry itself."
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


# ── Phase 2 intent parsing ────────────────────────────────────────────────────

def build_combat_intent_system_prompt() -> str:
    return (
        "You are an intent parser for a voice-controlled dungeon combat game. "
        "The player is in combat and spoke a command. "
        "Determine which weapon they want to attack with. "
        "Set action to 'attack' and item_id to the exact id of the chosen weapon. "
        "If no weapon is mentioned or the intent is unclear, set action to 'unknown'. "
        "Output a structured JSON response only."
    )


def build_combat_intent_user_prompt(
    transcript: str,
    inventory_items: list[dict],
) -> str:
    items_text = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in inventory_items
    )
    return (
        f"Player said: \"{transcript}\". "
        f"Weapons in inventory: [{items_text}]. "
        "Which weapon does the player want to attack with?"
    )


def build_pickup_intent_system_prompt() -> str:
    return (
        "You are an intent parser for a voice-controlled dungeon game. "
        "The player spoke a command. Determine which item they want to pick up. "
        "Set action to 'pickup' and item_id to the exact id of the chosen item. "
        "If no item matches or the intent is unclear, set action to 'unknown'. "
        "Output a structured JSON response only."
    )


def build_pickup_intent_user_prompt(
    transcript: str,
    room_items: list[dict],
) -> str:
    items_text = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in room_items
    )
    return (
        f"Player said: \"{transcript}\". "
        f"Items in this room: [{items_text}]. "
        "Which item does the player want to pick up?"
    )
