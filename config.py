import os

BOT_PREFIX = os.getenv("BOT_PREFIX", "v!")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
HENRIK_API_KEY = os.getenv("HENRIK_API_KEY", "").strip()
PORT = int(os.getenv("PORT", "8080"))
AUTO_SYNC_COMMANDS = os.getenv("AUTO_SYNC_COMMANDS", "true").lower() in {"1", "true", "yes", "on"}
VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID", "0") or 0)
SUGGESTION_CHANNEL_ID = int(os.getenv("SUGGESTION_CHANNEL_ID", "0") or 0)
VERIFIER_ROLE_ID = int(os.getenv("VERIFIER_ROLE_ID", "0") or 0)
ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID", "0") or 0)

BRAND_NAME = "V-Tracker"
BRAND_COLOR = 0x2FD6C4
ACCENT_COLOR = 0x7DE8FF
SUCCESS_COLOR = 0x44D39A
WARNING_COLOR = 0xF7D774
ERROR_COLOR = 0xF26C6C
PANEL_COLOR = 0x12222B

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join("data", "vtracker.sqlite3"))
TRUSTED_IMAGE_HOSTS = tuple(
    h.strip().lower() for h in os.getenv(
        "TRUSTED_IMAGE_HOSTS",
        "cdn.discordapp.com,media.discordapp.net,images-ext-1.discordapp.net,tracker.gg,media.valorant-api.com,imgur.com,i.imgur.com"
    ).split(",") if h.strip()
)

GLOBAL_USER_RATE = int(os.getenv("GLOBAL_USER_RATE", "6"))
GLOBAL_USER_WINDOW = int(os.getenv("GLOBAL_USER_WINDOW", "10"))
GLOBAL_GUILD_RATE = int(os.getenv("GLOBAL_GUILD_RATE", "40"))
GLOBAL_GUILD_WINDOW = int(os.getenv("GLOBAL_GUILD_WINDOW", "10"))
API_FAIL_OPEN_COUNT = int(os.getenv("API_FAIL_OPEN_COUNT", "5"))
API_COOLDOWN_SECONDS = int(os.getenv("API_COOLDOWN_SECONDS", "30"))
