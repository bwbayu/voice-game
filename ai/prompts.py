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
        "Be atmospheric and concise (1–2 sentences max). "
        "Mention each available exit direction and any visible items in one brief phrase each. "
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
        f"{items_text} "
        "Keep the entire narration to 1–2 sentences. Each exit and item gets one brief phrase."
    )


# ── Win narration ─────────────────────────────────────────────────────────────

def build_win_narration_user_prompt(room_name: str) -> str:
    return (
        f"The player has finally reached {room_name}, the heart of the dungeon. "
        "This is the end of their journey. "
        "Narrate their triumph in 2 atmospheric sentences. "
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
        "Write 2–3 sentences of ominous atmosphere. "
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
        "Write 2 sentences describing the boss falling. "
        "The tone is triumphant but with an undercurrent of dread — "
        "the dungeon feels the loss. Second person. No markdown."
    )


def build_exit_blocked_user_prompt() -> str:
    return (
        "The player tried to enter the final chamber but cannot — "
        "a guardian still lives somewhere in the dungeon. "
        "Write 1–2 sentences: the exit is sealed by dark energy, "
        "and the player senses an undefeated presence. "
        "Second person. No markdown. No game mechanics."
    )


def build_pickup_narration_user_prompt(item_name: str, room_name: str) -> str:
    return (
        f"The player picked up the {item_name} in {room_name}. "
        "Write 1–2 sentences describing them pocketing it. "
        "Brief and atmospheric. Second person. No markdown."
    )


def build_potion_use_user_prompt(
    item_name: str, hp_gained: int, new_hp: int, max_hp: int, room_name: str
) -> str:
    return (
        f"The player drank the {item_name} in {room_name} and recovered {hp_gained} HP "
        f"(now {new_hp}/{max_hp}). "
        "Write 1 sentence describing them drinking it and feeling restored. "
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


# ── Phase 3 narration ─────────────────────────────────────────────────────────

def build_death_narration_user_prompt(room_name: str, killer_name: str) -> str:
    return (
        f"The player was killed by {killer_name} in {room_name}. "
        "Write 2 atmospheric sentences describing their death. "
        "The tone is grim and final — the dungeon claims another soul. "
        "Second person. No markdown. No game mechanics."
    )


def build_monster_encounter_user_prompt(
    monster_name: str,
    room_name: str,
    previous_room_name: str | None,
) -> str:
    origin = f"came from {previous_room_name}" if previous_room_name else "entered"
    return (
        f"The player {origin} and encountered {monster_name} in {room_name}. "
        "Write 2 sentences of tense atmosphere. "
        "Describe the monster's sudden presence — threatening and immediate. "
        "Do NOT mention game mechanics or how to fight. Second person."
    )


def build_monster_defeat_user_prompt(monster_name: str) -> str:
    return (
        f"{monster_name} has been defeated. "
        "Write 1–2 sentences describing it falling. "
        "The tone is relieved but uneasy — more dangers lurk ahead. "
        "Second person. No markdown."
    )


def build_locked_room_user_prompt(room_name: str, key_name: str | None) -> str:
    key_hint = f"A {key_name} might open it." if key_name else "You need a key."
    return (
        f"The player tried to enter {room_name} but the door is locked. "
        f"{key_hint} "
        "Write 1 sentence describing the locked entrance — heavy, foreboding. "
        "Second person. No markdown."
    )


def build_unlock_room_user_prompt(room_name: str) -> str:
    return (
        f"The player used a key to unlock {room_name}. "
        "Write 1 sentence: the lock clicks open, the door creaks. "
        "Second person. No markdown."
    )


def build_swap_narration_user_prompt(new_item: str, old_item: str, room_name: str) -> str:
    return (
        f"The player dropped the {old_item} and picked up the {new_item} in {room_name}. "
        "Write 1 sentence describing them swapping the items. "
        "Brief and atmospheric. Second person. No markdown."
    )


# ── Intent parsing (unified) ──────────────────────────────────────────────────

def build_unified_intent_system_prompt() -> str:
    return (
        "You are an intent parser for a voice-controlled dungeon game. "
        "Given a player's spoken command and the current game context, "
        "determine what the player wants to do. "
        "Possible actions: "
        "'move' — player wants to go somewhere, set direction to the exact exit string; "
        "'attack' — player wants to fight, set item_id to the weapon id to use "
        "(if no specific weapon is named, pick the most appropriate one or the first); "
        "'pickup' — player wants to take an item from the room, set item_id to the item id "
        "(use semantic matching — 'grab the glowing thing' might match 'Torch'); "
        "'unknown' — intent is completely unclear or unrelated to any available action. "
        "Infer intent from natural language — the player will not use exact keywords. "
        "'go for it', 'let's fight', 'hit it' are attack. "
        "'head north', 'try the left door' are move. "
        "'grab that', 'take the sword' are pickup. "
        "Only return 'unknown' if the speech has no plausible connection to any listed action. "
        "Output a structured JSON response only."
    )


def build_unified_intent_user_prompt(
    transcript: str,
    exits: list[str],
    weapons: list[dict],
    room_items: list[dict],
) -> str:
    exits_text   = ", ".join(f'"{d}"' for d in exits)         or "none"
    weapons_text = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in weapons
    ) or "none"
    items_text   = ", ".join(
        f'"{i["name"]}" (id: "{i["id"]}")' for i in room_items
    ) or "none"
    return (
        f"Player said: \"{transcript}\". "
        f"Available exits: [{exits_text}]. "
        f"Weapons in inventory: [{weapons_text}]. "
        f"Items on the floor: [{items_text}]. "
        "What does the player want to do?"
    )
