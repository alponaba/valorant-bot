from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

print("V-Tracker 4.0 Preflight")
print("Python:", sys.version.split()[0])

required_modules = ["discord", "aiohttp", "flask"]
missing = [m for m in required_modules if importlib.util.find_spec(m) is None]
print("Dependencies:", "OK" if not missing else "MISSING: " + ", ".join(missing))

required_env = ["DISCORD_TOKEN"]
for key in required_env:
    print(f"{key}:", "SET" if os.getenv(key, "").strip() else "MISSING")
print("HENRIK_API_KEY:", "SET" if os.getenv("HENRIK_API_KEY", "").strip() else "NOT SET / plan dependent")

path = Path(os.getenv("DATABASE_PATH", "data/vtracker.sqlite3"))
try:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS preflight_check(id INTEGER PRIMARY KEY, checked_at TEXT)")
    conn.commit(); conn.close()
    print("Database:", f"OK ({path})")
except Exception as exc:
    print("Database: ERROR", repr(exc))

for key in ("VERIFICATION_CHANNEL_ID", "VERIFIER_ROLE_ID", "TRACKER_CHANNEL_ID", "AUTOMOD_LOG_CHANNEL_ID", "QUARANTINE_ROLE_ID"):
    print(f"{key}:", os.getenv(key, "not configured"))

if missing or not os.getenv("DISCORD_TOKEN", "").strip():
    raise SystemExit(1)
print("Preflight result: READY")
