"""
Pre-generate boss taunt voice lines before playing the game.

Usage:
    python scripts/pregenerate_boss_audio.py

Output:
    audio/bosses/{boss_id}/{skill_id}.wav

Idempotent — skips files that already exist.
Requires MISTRAL_API_KEY and OPENAI_API_KEY in .env (or environment).
"""
import json
import sys
from pathlib import Path

# Allow running as a script from the project root or from within scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import BOSSES_FILE, BOSSES_AUDIO_DIR
from ai.mistral_client import MistralClient
from ai.tts_client import TTSClient
from ai.prompts import build_narration_system_prompt, build_boss_taunt_user_prompt


def main() -> None:
    bosses = json.loads(BOSSES_FILE.read_text())["bosses"]
    mistral = MistralClient()
    tts     = TTSClient()

    total  = sum(len(b["skills"]) for b in bosses)
    done   = 0
    skipped = 0

    for boss in bosses:
        boss_dir = BOSSES_AUDIO_DIR / boss["id"]
        boss_dir.mkdir(parents=True, exist_ok=True)

        for skill in boss["skills"]:
            out = boss_dir / f"{skill['id']}.wav"
            if out.exists():
                print(f"  skip  {out.relative_to(BOSSES_AUDIO_DIR.parent.parent)}")
                skipped += 1
                continue

            print(
                f"  gen   audio/bosses/{boss['id']}/{skill['id']}.wav  ...",
                end=" ",
                flush=True,
            )
            text    = mistral.complete(
                build_narration_system_prompt(),
                build_boss_taunt_user_prompt(
                    boss["name"], skill["name"]
                ),
            )
            wav_tmp = tts.speak(text, voice=boss["openai_voice"])
            Path(wav_tmp).rename(out)
            print("done")
            done += 1

    print(
        f"\nAll boss audio ready. "
        f"Generated {done}, skipped {skipped} of {total} total."
    )


if __name__ == "__main__":
    main()
