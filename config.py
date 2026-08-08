import os

BOT_PREFIX = os.getenv("BOT_PREFIX", "v!")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
HENRIK_API_KEY = os.getenv("HENRIK_API_KEY", "").strip()
PORT = int(os.getenv("PORT", "8080"))
AUTO_SYNC_COMMANDS = os.getenv("AUTO_SYNC_COMMANDS", "true").lower() in {"1", "true", "yes", "on"}
VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID", "0") or 0)
SUGGESTION_CHANNEL_ID = int(os.getenv("SUGGESTION_CHANNEL_ID", "0") or 0)

BRAND_NAME = "V-Tracker"
BRAND_COLOR = 0xFF4655
ACCENT_COLOR = 0x00F0FF
SUCCESS_COLOR = 0x2ECC71
WARNING_COLOR = 0xF1C40F
ERROR_COLOR = 0xE74C3C

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join("data", "vtracker.sqlite3"))
