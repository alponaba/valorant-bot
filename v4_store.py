from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import DATABASE_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class V4Store:
    def __init__(self, path: str = DATABASE_PATH):
        self.path = path
        self.lock = asyncio.Lock()
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS player_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    rank TEXT NOT NULL DEFAULT 'Derecesiz',
                    rr INTEGER NOT NULL DEFAULT 0,
                    vscore INTEGER NOT NULL DEFAULT 0,
                    kd REAL NOT NULL DEFAULT 0,
                    hs_rate REAL NOT NULL DEFAULT 0,
                    adr REAL NOT NULL DEFAULT 0,
                    acs REAL NOT NULL DEFAULT 0,
                    winrate REAL NOT NULL DEFAULT 0,
                    main_agent TEXT NOT NULL DEFAULT '',
                    match_key TEXT NOT NULL DEFAULT '',
                    summary_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_user_time ON player_snapshots(discord_id, captured_at DESC);

                CREATE TABLE IF NOT EXISTS personal_records (
                    discord_id TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    numeric_value REAL NOT NULL DEFAULT 0,
                    text_value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(discord_id, record_key)
                );

                CREATE TABLE IF NOT EXISTS rivals (
                    owner_id TEXT PRIMARY KEY,
                    rival_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lfg_posts (
                    discord_id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    rank TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT 'eu',
                    mic INTEGER NOT NULL DEFAULT 1,
                    mode TEXT NOT NULL DEFAULT 'Competitive',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS coach_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    response_hash TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_coach_user ON coach_history(discord_id, id DESC);

                CREATE TABLE IF NOT EXISTS generated_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    response_hash TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_generated_user_scope ON generated_history(discord_id, scope, id DESC);

                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notification_preferences (
                    discord_id TEXT PRIMARY KEY,
                    rank_alerts INTEGER NOT NULL DEFAULT 1,
                    match_alerts INTEGER NOT NULL DEFAULT 1,
                    reports INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    async def latest_snapshot(self, discord_id: int | str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM player_snapshots WHERE discord_id=? ORDER BY id DESC LIMIT 1", (str(discord_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    async def snapshots(self, discord_id: int | str, limit: int = 30) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM player_snapshots WHERE discord_id=? ORDER BY id DESC LIMIT ?", (str(discord_id), int(limit))).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def add_snapshot(self, discord_id: int | str, *, rank: str, rr: int, vscore: int, stats: Dict[str, Any], match_key: str = "") -> int:
        async with self.lock:
            conn = self._conn()
            try:
                cur = conn.execute("""
                    INSERT INTO player_snapshots(discord_id,captured_at,rank,rr,vscore,kd,hs_rate,adr,acs,winrate,main_agent,match_key,summary_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    str(discord_id), now_iso(), rank, int(rr), int(vscore), float(stats.get('kd',0)), float(stats.get('hs_rate',0)),
                    float(stats.get('adr',0)), float(stats.get('acs',0)), float(stats.get('winrate',0)), str(stats.get('main_agent',''))[:80],
                    str(match_key)[:180], json.dumps({k: stats.get(k) for k in ('kills','deaths','assists','matches','wins','losses')}, ensure_ascii=False),
                ))
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    async def update_record(self, discord_id: int | str, key: str, numeric_value: float, text_value: str = "") -> tuple[bool, float]:
        async with self.lock:
            conn = self._conn()
            try:
                old = conn.execute("SELECT numeric_value FROM personal_records WHERE discord_id=? AND record_key=?", (str(discord_id), key)).fetchone()
                old_value = float(old['numeric_value']) if old else float('-inf')
                if numeric_value <= old_value:
                    return False, old_value
                conn.execute("""INSERT INTO personal_records(discord_id,record_key,numeric_value,text_value,updated_at)
                                VALUES(?,?,?,?,?) ON CONFLICT(discord_id,record_key) DO UPDATE SET
                                numeric_value=excluded.numeric_value,text_value=excluded.text_value,updated_at=excluded.updated_at""",
                             (str(discord_id), key, float(numeric_value), text_value[:200], now_iso()))
                conn.commit()
                return True, old_value
            finally:
                conn.close()

    async def records(self, discord_id: int | str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM personal_records WHERE discord_id=? ORDER BY numeric_value DESC", (str(discord_id),)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def set_rival(self, owner_id: int | str, rival_id: int | str):
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("INSERT INTO rivals(owner_id,rival_id,created_at) VALUES(?,?,?) ON CONFLICT(owner_id) DO UPDATE SET rival_id=excluded.rival_id,created_at=excluded.created_at",
                             (str(owner_id), str(rival_id), now_iso()))
                conn.commit()
            finally:
                conn.close()

    async def get_rival(self, owner_id: int | str) -> Optional[str]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT rival_id FROM rivals WHERE owner_id=?", (str(owner_id),)).fetchone()
            return str(row['rival_id']) if row else None
        finally:
            conn.close()

    async def upsert_lfg(self, discord_id: int | str, guild_id: int | str, *, rank: str, role: str, region: str, mic: bool, mode: str):
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("""INSERT INTO lfg_posts(discord_id,guild_id,rank,role,region,mic,mode,status,created_at)
                                VALUES(?,?,?,?,?,?,?,'open',?) ON CONFLICT(discord_id) DO UPDATE SET
                                guild_id=excluded.guild_id,rank=excluded.rank,role=excluded.role,region=excluded.region,mic=excluded.mic,
                                mode=excluded.mode,status='open',created_at=excluded.created_at""",
                             (str(discord_id), str(guild_id), rank[:80], role[:80], region[:20], int(mic), mode[:80], now_iso()))
                conn.commit()
            finally:
                conn.close()

    async def close_lfg(self, discord_id: int | str):
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("UPDATE lfg_posts SET status='closed' WHERE discord_id=?", (str(discord_id),))
                conn.commit()
            finally:
                conn.close()

    async def find_lfg(self, guild_id: int | str, exclude_id: int | str, role: str = "", limit: int = 8) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            if role:
                rows = conn.execute("SELECT * FROM lfg_posts WHERE guild_id=? AND discord_id<>? AND status='open' AND lower(role)<>lower(?) ORDER BY created_at DESC LIMIT ?",
                                    (str(guild_id), str(exclude_id), role, int(limit))).fetchall()
            else:
                rows = conn.execute("SELECT * FROM lfg_posts WHERE guild_id=? AND discord_id<>? AND status='open' ORDER BY created_at DESC LIMIT ?",
                                    (str(guild_id), str(exclude_id), int(limit))).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def recent_coach_hashes(self, discord_id: int | str, limit: int = 20) -> List[str]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT response_hash FROM coach_history WHERE discord_id=? ORDER BY id DESC LIMIT ?", (str(discord_id), int(limit))).fetchall()
            return [str(r['response_hash']) for r in rows]
        finally:
            conn.close()

    async def coach_count(self, discord_id: int | str) -> int:
        conn = self._conn()
        try:
            return int(conn.execute("SELECT COUNT(*) c FROM coach_history WHERE discord_id=?", (str(discord_id),)).fetchone()['c'])
        finally:
            conn.close()

    async def save_coach_response(self, discord_id: int | str, text: str) -> str:
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("INSERT INTO coach_history(discord_id,response_hash,response_text,created_at) VALUES(?,?,?,?)", (str(discord_id), h, text[:5000], now_iso()))
                conn.commit()
            finally:
                conn.close()
        return h


    async def recent_generated_hashes(self, discord_id: int | str, scope: str, limit: int = 20) -> List[str]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT response_hash FROM generated_history WHERE discord_id=? AND scope=? ORDER BY id DESC LIMIT ?",
                                (str(discord_id), scope[:80], int(limit))).fetchall()
            return [str(r['response_hash']) for r in rows]
        finally:
            conn.close()

    async def generated_count(self, discord_id: int | str, scope: str) -> int:
        conn = self._conn()
        try:
            return int(conn.execute("SELECT COUNT(*) c FROM generated_history WHERE discord_id=? AND scope=?",
                                    (str(discord_id), scope[:80])).fetchone()['c'])
        finally:
            conn.close()

    async def save_generated_response(self, discord_id: int | str, scope: str, text: str) -> str:
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("INSERT INTO generated_history(discord_id,scope,response_hash,response_text,created_at) VALUES(?,?,?,?,?)",
                             (str(discord_id), scope[:80], h, text[:5000], now_iso()))
                conn.commit()
            finally:
                conn.close()
        return h

    async def add_risk_event(self, guild_id: int | str, user_id: int | str, score: int, event_type: str, detail: str = ""):
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("INSERT INTO risk_events(guild_id,user_id,score,event_type,detail,created_at) VALUES(?,?,?,?,?,?)",
                             (str(guild_id), str(user_id), int(score), event_type[:80], detail[:1200], now_iso()))
                conn.commit()
            finally:
                conn.close()

    async def risk_summary(self, guild_id: int | str, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute("""SELECT user_id,SUM(score) total_score,COUNT(*) events,MAX(created_at) last_event
                                   FROM risk_events WHERE guild_id=? GROUP BY user_id ORDER BY total_score DESC LIMIT ?""",
                                (str(guild_id), int(limit))).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def prefs(self, discord_id: int | str) -> Dict[str, bool]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM notification_preferences WHERE discord_id=?", (str(discord_id),)).fetchone()
            if not row:
                return {'rank_alerts': True, 'match_alerts': True, 'reports': True}
            return {k: bool(row[k]) for k in ('rank_alerts','match_alerts','reports')}
        finally:
            conn.close()

    async def set_pref(self, discord_id: int | str, key: str, value: bool):
        if key not in {'rank_alerts','match_alerts','reports'}:
            raise ValueError('invalid preference')
        async with self.lock:
            conn = self._conn()
            try:
                conn.execute("INSERT INTO notification_preferences(discord_id,updated_at) VALUES(?,?) ON CONFLICT(discord_id) DO NOTHING", (str(discord_id), now_iso()))
                conn.execute(f"UPDATE notification_preferences SET {key}=?, updated_at=? WHERE discord_id=?", (int(value), now_iso(), str(discord_id)))
                conn.commit()
            finally:
                conn.close()


    async def weekly_leaderboard(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = self._conn()
        try:
            users = conn.execute("SELECT DISTINCT discord_id FROM player_snapshots WHERE captured_at>=?", (cutoff,)).fetchall()
            board = []
            for u in users:
                did = str(u['discord_id'])
                newest = conn.execute("SELECT * FROM player_snapshots WHERE discord_id=? AND captured_at>=? ORDER BY id DESC LIMIT 1", (did, cutoff)).fetchone()
                oldest = conn.execute("SELECT * FROM player_snapshots WHERE discord_id=? AND captured_at>=? ORDER BY id ASC LIMIT 1", (did, cutoff)).fetchone()
                if newest and oldest:
                    board.append({
                        'discord_id': did, 'rank': newest['rank'], 'rr': int(newest['rr']),
                        'vscore': int(newest['vscore']), 'vscore_delta': int(newest['vscore'])-int(oldest['vscore']),
                        'rr_delta': int(newest['rr'])-int(oldest['rr']),
                    })
            board.sort(key=lambda x: (x['vscore_delta'], x['vscore']), reverse=True)
            return board[:limit]
        finally:
            conn.close()


store = V4Store()
