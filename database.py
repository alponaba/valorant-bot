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
        conn = sqlite3.connect(self.path, timeout=20)
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
                    profile_color INTEGER NOT NULL DEFAULT 3131076,
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

                CREATE TABLE IF NOT EXISTS pending_verifications (
                    discord_id TEXT PRIMARY KEY,
                    puuid TEXT NOT NULL UNIQUE,
                    game_name TEXT NOT NULL,
                    tag_line TEXT NOT NULL,
                    region TEXT NOT NULL DEFAULT 'eu',
                    dc_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    proof_note TEXT NOT NULL DEFAULT '',
                    requested_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    review_note TEXT NOT NULL DEFAULT ''
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

                CREATE TABLE IF NOT EXISTS admin_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL DEFAULT '',
                    actor_id TEXT NOT NULL,
                    target_id TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
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
                            region: str, dc_name: str, verification_level: str = "api_profile") -> tuple[bool, str, Optional[Dict[str, Any]]]:
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 500, 1)""",
                    (did, puuid, game_name, tag_line, region or "eu", dc_name, verification_level, now, now),
                )
                conn.execute(
                    "INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                    (did, puuid, "REGISTER", f"{game_name}#{tag_line}", now),
                )
                row = conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone()
                return True, "registered", dict(row)

    async def create_pending_verification(self, *, discord_id: int | str, puuid: str, game_name: str,
                                          tag_line: str, region: str, dc_name: str, proof_note: str = "") -> tuple[bool, str]:
        async with self._lock:
            did = str(discord_id)
            now = utc_now()
            with self._connect() as conn:
                if conn.execute("SELECT 1 FROM users WHERE discord_id=? AND active=1", (did,)).fetchone():
                    return False, "already_registered"
                if conn.execute("SELECT 1 FROM users WHERE puuid=? AND active=1", (puuid,)).fetchone():
                    return False, "riot_locked"
                other = conn.execute("SELECT discord_id FROM pending_verifications WHERE puuid=? AND status='pending'", (puuid,)).fetchone()
                if other and str(other["discord_id"]) != did:
                    return False, "riot_pending"
                conn.execute("""
                    INSERT INTO pending_verifications
                    (discord_id, puuid, game_name, tag_line, region, dc_name, status, proof_note, requested_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    ON CONFLICT(discord_id) DO UPDATE SET
                        puuid=excluded.puuid, game_name=excluded.game_name, tag_line=excluded.tag_line,
                        region=excluded.region, dc_name=excluded.dc_name, status='pending',
                        proof_note=excluded.proof_note, requested_at=excluded.requested_at,
                        reviewed_at=NULL, reviewed_by=NULL, review_note=''
                """, (did, puuid, game_name, tag_line, region or "eu", dc_name, proof_note[:1000], now))
                conn.execute("INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                             (did, puuid, "VERIFY_REQUEST", f"{game_name}#{tag_line}", now))
                return True, "pending"

    async def get_pending_verification(self, discord_id: int | str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM pending_verifications WHERE discord_id=?", (str(discord_id),)).fetchone())

    async def approve_pending_verification(self, discord_id: int | str, reviewer_id: int | str, note: str = "") -> tuple[bool, str, Optional[Dict[str, Any]]]:
        did = str(discord_id)
        async with self._lock:
            now = utc_now()
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM pending_verifications WHERE discord_id=? AND status='pending'", (did,)).fetchone()
                if not row:
                    return False, "no_pending", None
                data = dict(row)
                current = conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone()
                if current:
                    current_d = dict(current)
                    if current_d["puuid"] != data["puuid"]:
                        return False, "discord_locked", current_d
                    user = current_d
                else:
                    puuid_owner = conn.execute("SELECT * FROM users WHERE puuid=?", (data["puuid"],)).fetchone()
                    if puuid_owner:
                        return False, "riot_locked", dict(puuid_owner)
                    conn.execute(
                        """INSERT INTO users
                        (discord_id, puuid, game_name, tag_line, region, dc_name, verification_level,
                         locked_at, updated_at, v_coins, active)
                        VALUES (?, ?, ?, ?, ?, ?, 'manual_review', ?, ?, 500, 1)""",
                        (did, data["puuid"], data["game_name"], data["tag_line"], data["region"] or "eu", data["dc_name"], now, now),
                    )
                    user = dict(conn.execute("SELECT * FROM users WHERE discord_id=?", (did,)).fetchone())
                    conn.execute(
                        "INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                        (did, data["puuid"], "REGISTER", f"{data['game_name']}#{data['tag_line']} [manual_review]", now),
                    )
                conn.execute("UPDATE pending_verifications SET status='approved', reviewed_at=?, reviewed_by=?, review_note=? WHERE discord_id=?",
                             (now, str(reviewer_id), note[:1000], did))
                conn.execute("INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                             (did, data["puuid"], "VERIFY_APPROVE", note[:1000], now))
                return True, "approved", user

    async def reject_pending_verification(self, discord_id: int | str, reviewer_id: int | str, note: str = "") -> bool:
        did = str(discord_id)
        async with self._lock:
            now = utc_now()
            with self._connect() as conn:
                row = conn.execute("SELECT puuid FROM pending_verifications WHERE discord_id=? AND status='pending'", (did,)).fetchone()
                if not row:
                    return False
                conn.execute("UPDATE pending_verifications SET status='rejected', reviewed_at=?, reviewed_by=?, review_note=? WHERE discord_id=?",
                             (now, str(reviewer_id), note[:1000], did))
                conn.execute("INSERT INTO registration_audit(discord_id, puuid, action, detail, created_at) VALUES(?,?,?,?,?)",
                             (did, row["puuid"], "VERIFY_REJECT", note[:1000], now))
                return True

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

    async def claim_reward_atomic(self, discord_id: int | str, kind: str, amount: int, when: str) -> tuple[bool, str, Optional[int]]:
        column = "daily_claimed_at" if kind == "daily" else "weekly_claimed_at"
        did = str(discord_id)
        async with self._lock:
            with self._connect() as conn:
                row = conn.execute(f"SELECT v_coins FROM users WHERE discord_id=? AND active=1", (did,)).fetchone()
                if not row:
                    return False, "not_registered", None
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(f"UPDATE users SET {column}=?, v_coins=v_coins+?, updated_at=? WHERE discord_id=?", (when, amount, utc_now(), did))
                conn.execute("INSERT INTO economy_log(discord_id, amount, reason, created_at) VALUES(?,?,?,?)",
                             (did, int(amount), f"{kind}_claim", utc_now()))
                bal = conn.execute("SELECT v_coins FROM users WHERE discord_id=?", (did,)).fetchone()["v_coins"]
                return True, "ok", int(bal)

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
                conn.execute("BEGIN IMMEDIATE")
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

    async def purchase_item(self, discord_id: int | str, item: str, price: int) -> tuple[bool, str, Optional[int]]:
        did = str(discord_id)
        async with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT v_coins, unlocked_json FROM users WHERE discord_id=? AND active=1", (did,)).fetchone()
                if not row:
                    return False, "not_registered", None
                unlocked = set(json.loads(row["unlocked_json"] or "[]"))
                if item in unlocked:
                    return False, "already", int(row["v_coins"])
                if int(row["v_coins"]) < int(price):
                    return False, "insufficient", int(row["v_coins"])
                unlocked.add(item)
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE users SET v_coins=v_coins-?, unlocked_json=?, updated_at=? WHERE discord_id=?",
                             (int(price), json.dumps(sorted(unlocked)), utc_now(), did))
                conn.execute("INSERT INTO economy_log(discord_id, amount, reason, created_at) VALUES(?,?,?,?)",
                             (did, -int(price), f"shop:{item}", utc_now()))
                new_balance = conn.execute("SELECT v_coins FROM users WHERE discord_id=?", (did,)).fetchone()["v_coins"]
                return True, "ok", int(new_balance)

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

    async def log_admin_action(self, guild_id: int | str, actor_id: int | str, target_id: int | str, action: str, detail: str = "") -> None:
        async with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO admin_audit(guild_id, actor_id, target_id, action, detail, created_at) VALUES(?,?,?,?,?,?)",
                    (str(guild_id or ""), str(actor_id), str(target_id or ""), action[:64], detail[:1500], utc_now()),
                )

    async def list_admin_audit(self, guild_id: int | str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM admin_audit WHERE guild_id=? ORDER BY id DESC LIMIT ?",
                (str(guild_id), int(limit)),
            ).fetchall()
            return [dict(r) for r in rows]

    async def system_counts(self) -> Dict[str, int]:
        with self._connect() as conn:
            users = conn.execute("SELECT COUNT(*) c FROM users WHERE active=1").fetchone()["c"]
            pending = conn.execute("SELECT COUNT(*) c FROM pending_verifications WHERE status='pending'").fetchone()["c"]
            warnings = conn.execute("SELECT COUNT(*) c FROM warnings").fetchone()["c"]
            econ = conn.execute("SELECT COUNT(*) c FROM economy_log").fetchone()["c"]
            return {"users": int(users), "pending": int(pending), "warnings": int(warnings), "economy_events": int(econ)}


db = Database()
