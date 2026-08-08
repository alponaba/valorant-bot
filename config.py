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

# V4 automation / community / protection
TRACK_INTERVAL_SECONDS = int(os.getenv("TRACK_INTERVAL_SECONDS", "900"))
TRACK_BATCH_SIZE = int(os.getenv("TRACK_BATCH_SIZE", "40"))
TRACKER_CHANNEL_ID = int(os.getenv("TRACKER_CHANNEL_ID", "0") or 0)
LFG_CHANNEL_ID = int(os.getenv("LFG_CHANNEL_ID", "0") or 0)
QUARANTINE_ROLE_ID = int(os.getenv("QUARANTINE_ROLE_ID", "0") or 0)
AUTOMOD_LOG_CHANNEL_ID = int(os.getenv("AUTOMOD_LOG_CHANNEL_ID", "0") or 0)
ANTI_RAID_JOIN_COUNT = int(os.getenv("ANTI_RAID_JOIN_COUNT", "8"))
ANTI_RAID_WINDOW_SECONDS = int(os.getenv("ANTI_RAID_WINDOW_SECONDS", "30"))
NEW_ACCOUNT_RISK_DAYS = int(os.getenv("NEW_ACCOUNT_RISK_DAYS", "7"))
MASS_MENTION_LIMIT = int(os.getenv("MASS_MENTION_LIMIT", "5"))
MESSAGE_SPAM_COUNT = int(os.getenv("MESSAGE_SPAM_COUNT", "6"))
MESSAGE_SPAM_WINDOW = int(os.getenv("MESSAGE_SPAM_WINDOW", "8"))
BLOCK_INVITES = os.getenv("BLOCK_INVITES", "false").lower() in {"1","true","yes","on"}
AUTO_TRACK_ENABLED = os.getenv("AUTO_TRACK_ENABLED", "true").lower() in {"1","true","yes","on"}

# Public website / SEO
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "").strip().rstrip("/")
GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
DISCORD_BOT_INVITE_URL = os.getenv("DISCORD_BOT_INVITE_URL", "").strip()
SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL", "").strip()
SITE_DESCRIPTION = os.getenv(
    "SITE_DESCRIPTION",
    "V-Tracker; Valorant oyuncuları için Player DNA, V-Score, kişisel koçluk, rank ve maç takibi, LFG, raporlar ve gelişmiş Discord AutoMod sunan oyuncu platformudur.",
).strip()
