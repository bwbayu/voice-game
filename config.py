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
BOSSES_AUDIO_DIR = ROOT_DIR / "audio" / "bosses"

# ── Audio recording (Mistral realtime requires pcm_s16le @ 16kHz) ──
SAMPLE_RATE       = 16000   # Hz
CHUNK_DURATION_MS = 480     # ms per audio chunk sent to Mistral
BG_VOLUME         = 0.4     # 0.0 – 1.0

# ── TTS (OpenAI) ──────────────────────────────────────
TTS_MODEL  = "tts-1"
TTS_VOICE  = "onyx"
TTS_FORMAT = "wav"

# ── LLM / STT (Mistral) ───────────────────────────────
LLM_MODEL    = "mistral-large-latest"
INTENT_MODEL = "ministral-8b-latest"   # small model is fine for command extraction
STT_MODEL    = "voxtral-mini-transcribe-realtime-2602"

# ── Game settings ─────────────────────────────────────
INVENTORY_CAP = 8

# ── UI colours ────────────────────────────────────────
BG_COLOR     = "#1a1a2e"
TEXT_COLOR   = "#e0e0e0"
ACCENT_COLOR = "#c0a060"
STATUS_COLOR = "#80c080"
DIM_COLOR    = "#505060"
