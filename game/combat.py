import random
from dataclasses import dataclass


@dataclass
class CombatResult:
    player_damage: int   # damage dealt to boss (item.damage)
    boss_damage:   int   # damage dealt to player (skill.damage)
    skill_id:      str
    skill_name:    str
    taunt_hint:    str


class CombatManager:
    """
    Pure combat resolver — no side effects.
    Picks a random boss skill and returns the damage exchange.
    """

    def resolve(self, item: dict, boss: dict) -> CombatResult:
        skill = random.choice(boss["skills"])
        return CombatResult(
            player_damage=item["damage"],
            boss_damage=skill["damage"],
            skill_id=skill["id"],
            skill_name=skill["name"],
            taunt_hint=skill["taunt_hint"],
        )
