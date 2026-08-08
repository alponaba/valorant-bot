from __future__ import annotations

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from config import AUTO_TRACK_ENABLED, TRACK_BATCH_SIZE, TRACK_INTERVAL_SECONDS, TRACKER_CHANNEL_ID
from database import db
from theme import panel
from v4_store import store
from valorant_api import api
from cogs.stats import analyze, compute_vscore, match_key, rank_from_mmr

log = logging.getLogger("VTracker.Automation")

RANK_BASES = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"]


def rank_value(rank: str, rr: int = 0) -> int:
    low = (rank or "").lower()
    base = 0
    for i, name in enumerate(RANK_BASES):
        if name.lower() in low:
            base = i * 400
            break
    tier = 0
    for n in (1, 2, 3):
        if str(n) in low:
            tier = n * 100
            break
    return base + tier + int(rr)


def base_rank_name(rank: str) -> Optional[str]:
    low = (rank or "").lower()
    for name in RANK_BASES:
        if name.lower() in low:
            return name
    return None


class Automation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cursor = 0
        if AUTO_TRACK_ENABLED:
            self.tracker.change_interval(seconds=max(180, TRACK_INTERVAL_SECONDS))
            self.tracker.start()

    def cog_unload(self):
        self.tracker.cancel()

    async def _sync_rank_role(self, discord_id: int, rank: str):
        wanted = base_rank_name(rank)
        if not wanted:
            return
        for guild in self.bot.guilds:
            member = guild.get_member(discord_id)
            if not member:
                continue
            role = discord.utils.get(guild.roles, name=wanted)
            if not role:
                continue
            remove = [r for r in member.roles if r.name in RANK_BASES and r.id != role.id]
            try:
                if remove:
                    await member.remove_roles(*remove, reason="V-Tracker rank sync")
                if role not in member.roles:
                    await member.add_roles(role, reason="V-Tracker rank sync")
            except discord.HTTPException:
                pass

    async def _send_tracker(self, embed: discord.Embed):
        if not TRACKER_CHANNEL_ID:
            return
        channel = self.bot.get_channel(TRACKER_CHANNEL_ID)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    async def _process_user(self, user: dict):
        did = int(user["discord_id"])
        prefs = await store.prefs(did)
        async with aiohttp.ClientSession() as session:
            mmr, matches_payload = await asyncio.gather(
                api.mmr(session, user["region"], user["puuid"]),
                api.matches(session, user["region"], user["puuid"], 10),
            )
        matches = (matches_payload or {}).get("data", [])
        if not matches:
            return
        rank, rr = rank_from_mmr(mmr)
        s = analyze(matches, user["puuid"])
        vscore = compute_vscore(s, rank)
        key = match_key(matches[0])
        previous = await store.latest_snapshot(did)

        # First discovery is baseline only, never an alert storm.
        if previous:
            old_rank, old_rr, old_key = previous["rank"], int(previous["rr"]), previous.get("match_key") or ""
            if (old_rank != rank or old_rr != rr) and prefs["rank_alerts"]:
                direction = "RANK UP" if rank_value(rank, rr) > rank_value(old_rank, old_rr) else "RANK UPDATE"
                e = panel(direction, f"<@{did}> • **{user['game_name']}#{user['tag_line']}**")
                e.add_field(name="Önce", value=f"**{old_rank}**\n`{old_rr} RR`", inline=True)
                e.add_field(name="Şimdi", value=f"**{rank}**\n`{rr} RR`", inline=True)
                e.add_field(name="V-Score", value=f"`{vscore}`", inline=True)
                await self._send_tracker(e)
            if old_key and key != old_key and prefs["match_alerts"]:
                first = s.get("per_match", [{}])[0]
                e = panel("NEW MATCH", f"<@{did}> • **{user['game_name']}#{user['tag_line']}**")
                e.add_field(name="Sonuç", value="**Victory**" if first.get("won") else "**Defeat**", inline=True)
                e.add_field(name="Harita / Ajan", value=f"**{first.get('map','?')}**\n{first.get('agent','?')}", inline=True)
                e.add_field(name="K/D/A", value=f"`{first.get('kills',0)} / {first.get('deaths',0)} / {first.get('assists',0)}`", inline=True)
                e.add_field(name="K/D • HS • ADR", value=f"`{first.get('kd',0)}` • `%{first.get('hs_rate',0)}` • `{first.get('adr',0)}`", inline=False)
                await self._send_tracker(e)

        should_snapshot = previous is None or previous.get("match_key") != key or previous.get("rank") != rank or int(previous.get("rr") or 0) != rr
        if previous and not should_snapshot:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(previous["captured_at"])
                should_snapshot = age.total_seconds() >= 21600
            except Exception:
                should_snapshot = True
        if should_snapshot:
            await store.add_snapshot(did, rank=rank, rr=rr, vscore=vscore, stats=s, match_key=key)

        new_records = []
        for rec_key, rec_val, label in (("vscore", vscore, "V-Score"), ("rr", rr, "RR")):
            changed, old = await store.update_record(did, rec_key, float(rec_val), str(rec_val))
            if changed and old != float('-inf'):
                new_records.append(f"{label}: `{rec_val}`")
        if s.get("per_match"):
            first = s["per_match"][0]
            for rec_key, rec_val, label in (("kills", first.get("kills",0), "Kill"), ("kd", first.get("kd",0), "K/D"), ("hs", first.get("hs_rate",0), "HS"), ("adr", first.get("adr",0), "ADR")):
                changed, old = await store.update_record(did, rec_key, float(rec_val), str(rec_val))
                if changed and old != float('-inf'):
                    new_records.append(f"{label}: `{rec_val}`")
        if previous and new_records and prefs["match_alerts"]:
            e = panel("PERSONAL RECORD", f"<@{did}> • **{user['game_name']}#{user['tag_line']}**")
            e.add_field(name="Yeni zirveler", value="\n".join(new_records[:5]), inline=False)
            await self._send_tracker(e)
        await self._sync_rank_role(did, rank)

    @tasks.loop(seconds=900)
    async def tracker(self):
        try:
            users = await db.list_users(5000)
            if not users:
                return
            start = self.cursor % len(users)
            batch = [users[(start + i) % len(users)] for i in range(min(TRACK_BATCH_SIZE, len(users)))]
            self.cursor = (start + len(batch)) % len(users)
            for user in batch:
                try:
                    await self._process_user(user)
                except Exception:
                    log.exception("Tracker failed for discord_id=%s", user.get("discord_id"))
                await asyncio.sleep(.35)
        except Exception:
            log.exception("Tracker cycle failed")

    @tracker.before_loop
    async def before_tracker(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="notifications", aliases=["bildirimler"], description="Otomatik V-Tracker bildirimlerini yönetir.")
    async def notifications(self, ctx: commands.Context, setting: str = "show", state: str = ""):
        user = await db.get_user(ctx.author.id)
        if not user:
            from theme import error
            return await ctx.send(embed=error("Kayıt bulunamadı", "Önce `v!register` kullan."))
        mapping = {"rank":"rank_alerts", "match":"match_alerts", "mac":"match_alerts", "rapor":"reports", "report":"reports"}
        if setting.lower() in mapping and state.lower() in {"on","off","ac","aç","kapat"}:
            value = state.lower() in {"on","ac","aç"}
            await store.set_pref(ctx.author.id, mapping[setting.lower()], value)
        prefs = await store.prefs(ctx.author.id)
        e = panel("Notification Center", "Otomatik takip tercihleri")
        e.add_field(name="Rank alerts", value="Açık" if prefs["rank_alerts"] else "Kapalı", inline=True)
        e.add_field(name="Match alerts", value="Açık" if prefs["match_alerts"] else "Kapalı", inline=True)
        e.add_field(name="Reports", value="Açık" if prefs["reports"] else "Kapalı", inline=True)
        e.add_field(name="Kullanım", value="`v!notifications rank on/off`\n`v!notifications match on/off`\n`v!notifications report on/off`", inline=False)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Automation(bot))
