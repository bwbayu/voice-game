from pathlib import Path

# ── Directory roots ───────────────────────────────────
ROOT_DIR  = Path(__file__).parent
MAPS_DIR  = ROOT_DIR / "maps"
STATE_DIR = ROOT_DIR / "state"
AUDIO_DIR = ROOT_DIR / "audio" / "bg"
DATA_DIR   = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"

# ── File paths ────────────────────────────────────────
MAP_FILE        = MAPS_DIR / "dungeon_map.json"
GAME_STATE_FILE = STATE_DIR / "game_state.json"
ITEMS_FILE       = DATA_DIR / "items.json"
BOSSES_FILE      = DATA_DIR / "bosses.json"
MONSTERS_FILE    = DATA_DIR / "monsters.json"
BOSSES_AUDIO_DIR = ROOT_DIR / "audio" / "bosses"

# ── Audio recording (Mistral realtime requires pcm_s16le @ 16kHz) ──
SAMPLE_RATE       = 16000   # Hz
CHUNK_DURATION_MS = 480     # ms per audio chunk sent to Mistral
BG_VOLUME         = 0.05     # 0.0 – 1.0

# ── LLM / STT (Mistral) ───────────────────────────────
LLM_MODEL    = "mistral-large-latest"
INTENT_MODEL = "ministral-8b-latest"   # small model is fine for command extraction
STT_MODEL    = "voxtral-mini-transcribe-realtime-2602"

# ── Game settings ─────────────────────────────────────
INVENTORY_CAP = 8

# ── UI colours & Typography ───────────────────────────
BG_COLOR         = "#0B0C10"  # Obsidian Black / Dark Slate
TEXT_COLOR       = "#E0E6ED"  # Bone white
ACCENT_COLOR     = "#D4AF37"  # Faded Gold
STATUS_COLOR     = "#D4AF37"  # Kita samakan dengan emas agar elegan
DIM_COLOR        = "#505060"  # Abu-abu redup
CRIMSON_RED      = "#8B0000"  # Untuk HP bar / Boss
BOSS_ALIVE_COLOR = "#FF4500"  # Merah terang untuk boss yang hidup
MONSTER_COLOR    = "#CC8833"
ITEM_COLOR       = "#7799AA"

FONT_TITLE       = "Georgia"  # Font serif untuk kesan Dark Fantasy
FONT_BODY        = "Georgia"