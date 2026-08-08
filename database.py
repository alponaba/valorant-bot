from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import DATABASE_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str = DATABASE_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    puuid TEXT NOT NULL UNIQUE,
                    game_name TEXT NOT NULL,
                    tag_line TEXT NOT NULL,
                    region TEXT NOT NULL DEFAULT 'eu',
                    dc_name TEXT NOT NULL DEFAULT '',
                    verification_level TEXT NOT NULL DEFAULT 'api_profile',
                    locked_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    v_coins INTEGER NOT NULL DEFAULT 0,
                    daily_claimed_at TEXT,
                    weekly_claimed_at TEXT,
                    profile_color INTEGER NOT NULL DEFAULT 16729685,
                    profile_emoji TEXT NOT NULL DEFAULT '',
                    profile_banner TEXT NOT NULL DEFAULT '',
                    unlocked_json TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS registration_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    puuid TEXT,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS economy_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    moderator_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        return dict(row) if row else None

    async def get_user(self, discord_id: int | str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM users WHERE discord_id=? AND active=1", (str(discord_id),)).fetchone())

    async def get_user_by_puuid(self, puuid: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM users WHERE puuid=? AND active=1", (puuid,)).fetchone())

    async def register_once(self, *, discord_id: int | str, puuid: str, game_name: str, tag_line: str,
                            region: str, dc_name: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        """Permanent one-account lock. Only bot owner reset can remove it."""
        async with self._lock:
            did = str(discord_id)
            now = utc_now()
            with self._connect() as conn:
                current = conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone()
                if current:
                    current_d = dict(current)
                    if current_d["puuid"] == puuid:
                        return False, "already_same", current_d
                    return False, "discord_locked", current_d

                puuid_owner = conn.execute("SELECT * FROM users WHERE puuid=?", (puuid,)).fetchone()
                if puuid_owner:
                    return False, "riot_locked", dict(puuid_owner)

                conn.execute(
                    """INSERT INTO users
                    (discord_id, puuid, game_name, tag_line, region, dc_name, verification_level,
                     locked_at, updated_at, v_coins, active)
                    VALUES (?, ?, ?, ?, ?, ?, 'api_profile', ?, ?, 500, 1)""",
                    (did, puuid, game_name, tag_line, region or "eu", dc_name, now, now),
                )
                conn.execute(
                    "INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                    (did, puuid, "REGISTER", f"{game_name}#{tag_line}", now),
                )
                row = conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone()
                return True, "registered", dict(row)

    async def sync_identity(self, discord_id: int | str, *, game_name: str, tag_line: str, region: str) -> bool:
        async with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE users SET game_name=?, tag_line=?, region=?, updated_at=? WHERE discord_id=? AND active=1",
                    (game_name, tag_line, region or "eu", utc_now(), str(discord_id)),
                )
                return cur.rowcount > 0

    async def owner_reset_registration(self, discord_id: int | str, reason: str = "owner reset") -> bool:
        async with self._lock:
            did = str(discord_id)
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone()
                if not row:
                    return False
                conn.execute(
                    "INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                    (did, row["puuid"], "OWNER_RESET", reason, utc_now()),
                )
                conn.execute("DELETE FROM users WHERE discord_id=?", (did,))
                return True

    async def set_manual_verified(self, discord_id: int | str, value: bool = True) -> bool:
        level = "manual_review" if value else "api_profile"
        async with self._lock:
            with self._connect() as conn:
                cur = conn.execute("UPDATE users SET verification_level=?, updated_at=? WHERE discord_id=?",
                                   (level, utc_now(), str(discord_id)))
                return cur.rowcount > 0

    async def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users WHERE active=1 ORDER BY v_coins DESC, locked_at ASC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    async def add_coins(self, discord_id: int | str, amount: int, reason: str) -> Optional[int]:
        async with self._lock:
            did = str(discord_id)
            with self._connect() as conn:
                row = conn.execute("SELECT v_coins FROM users WHERE discord_id=? AND active=1", (did,)).fetchone()
                if not row:
                    return None
                new_balance = max(0, int(row["v_coins"]) + int(amount))
                conn.execute("UPDATE users SET v_coins=?, updated_at=? WHERE discord_id=?", (new_balance, utc_now(), did))
                conn.execute("INSERT INTO economy_log(discord_id, amount, reason, created_at) VALUES(?,?,?,?)",
                             (did, int(amount), reason, utc_now()))
                return new_balance

    async def transfer_coins(self, sender: int | str, receiver: int | str, amount: int) -> tuple[bool, str]:
        if amount <= 0:
            return False, "invalid"
        if str(sender) == str(receiver):
            return False, "self"
        async with self._lock:
            with self._connect() as conn:
                s = conn.execute("SELECT v_coins FROM users WHERE discord_id=? AND active=1", (str(sender),)).fetchone()
                r = conn.execute("SELECT v_coins FROM users WHERE discord_id=? AND active=1", (str(receiver),)).fetchone()
                if not s or not r:
                    return False, "not_registered"
                if int(s["v_coins"]) < amount:
                    return False, "insufficient"
                now = utc_now()
                conn.execute("UPDATE users SET v_coins=v_coins-?, updated_at=? WHERE discord_id=?", (amount, now, str(sender)))
                conn.execute("UPDATE users SET v_coins=v_coins+?, updated_at=? WHERE discord_id=?", (amount, now, str(receiver)))
                conn.execute("INSERT INTO economy_log(discord_id, amount, reason, created_at) VALUES(?,?,?,?)",
                             (str(sender), -amount, f"transfer->{receiver}", now))
                conn.execute("INSERT INTO economy_log(discord_id, amount, reason, created_at) VALUES(?,?,?,?)",
                             (str(receiver), amount, f"transfer<-{sender}", now))
                return True, "ok"

    async def get_claim_time(self, discord_id: int | str, kind: str) -> Optional[str]:
        column = "daily_claimed_at" if kind == "daily" else "weekly_claimed_at"
        with self._connect() as conn:
            row = conn.execute(f"SELECT {column} FROM users WHERE discord_id=? AND active=1", (str(discord_id),)).fetchone()
            return row[column] if row else None

    async def set_claim_time(self, discord_id: int | str, kind: str, when: str) -> None:
        column = "daily_claimed_at" if kind == "daily" else "weekly_claimed_at"
        async with self._lock:
            with self._connect() as conn:
                conn.execute(f"UPDATE users SET {column}=?, updated_at=? WHERE discord_id=?", (when, utc_now(), str(discord_id)))

    async def set_profile(self, discord_id: int | str, *, color: Optional[int] = None,
                          emoji: Optional[str] = None, banner: Optional[str] = None) -> bool:
        fields, params = [], []
        if color is not None:
            fields.append("profile_color=?"); params.append(color)
        if emoji is not None:
            fields.append("profile_emoji=?"); params.append(emoji[:32])
        if banner is not None:
            fields.append("profile_banner=?"); params.append(banner[:500])
        if not fields:
            return False
        fields.append("updated_at=?"); params.append(utc_now()); params.append(str(discord_id))
        async with self._lock:
            with self._connect() as conn:
                cur = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE discord_id=? AND active=1", params)
                return cur.rowcount > 0

    async def add_warning(self, guild_id: int | str, user_id: int | str, moderator_id: int | str, reason: str) -> int:
        async with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)",
                    (str(guild_id), str(user_id), str(moderator_id), reason[:1000], utc_now()),
                )
                return int(cur.lastrowid)

    async def get_warnings(self, guild_id: int | str, user_id: int | str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 20",
                (str(guild_id), str(user_id)),
            ).fetchall()
            return [dict(r) for r in rows]


db = Database()
