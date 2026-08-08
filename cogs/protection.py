from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands

from config import (
    ANTI_RAID_JOIN_COUNT, ANTI_RAID_WINDOW_SECONDS, AUTOMOD_LOG_CHANNEL_ID, BLOCK_INVITES,
    MASS_MENTION_LIMIT, MESSAGE_SPAM_COUNT, MESSAGE_SPAM_WINDOW, NEW_ACCOUNT_RISK_DAYS, QUARANTINE_ROLE_ID,
)
from security import sanitize_text
from theme import error, panel, success, warning
from v4_store import store

URL_RE = re.compile(r"https?://[^\s<>]+", re.I)
INVITE_RE = re.compile(r"(?:discord\.gg/|discord(?:app)?\.com/invite/)[A-Za-z0-9-]+", re.I)
SUSPICIOUS_TOKENS = (
    "discord-nitro", "free-nitro", "steamcomnunity", "stearncommunity", "free-vp", "valorant-gift",
    "riotgames-gift", "claim-skin", "gift-skin", "nitro-free", "discordgift", "dlscord",
)


class Protection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.joins: dict[int, deque[float]] = defaultdict(deque)
        self.messages: dict[tuple[int,int], deque[tuple[float,str]]] = defaultdict(deque)
        self.raid_until: dict[int, float] = defaultdict(float)

    async def _log(self, guild: discord.Guild, title: str, detail: str, member: discord.Member | None = None):
        if not AUTOMOD_LOG_CHANNEL_ID:
            return
        ch = guild.get_channel(AUTOMOD_LOG_CHANNEL_ID) or self.bot.get_channel(AUTOMOD_LOG_CHANNEL_ID)
        if not ch:
            return
        e = warning(title, detail)
        if member:
            e.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=False)
        try:
            await ch.send(embed=e)
        except discord.HTTPException:
            pass

    def _quarantine_role(self, guild: discord.Guild):
        if QUARANTINE_ROLE_ID:
            return guild.get_role(QUARANTINE_ROLE_ID)
        return discord.utils.get(guild.roles, name="V-Tracker Quarantine")

    async def _quarantine(self, member: discord.Member, reason: str):
        role = self._quarantine_role(member.guild)
        if not role:
            return False
        try:
            await member.add_roles(role, reason=f"V-Tracker AutoMod: {reason[:250]}")
            return True
        except discord.HTTPException:
            return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        now = time.time(); dq = self.joins[member.guild.id]
        dq.append(now)
        while dq and now - dq[0] > ANTI_RAID_WINDOW_SECONDS:
            dq.popleft()
        if len(dq) >= ANTI_RAID_JOIN_COUNT:
            self.raid_until[member.guild.id] = now + 120
            await store.add_risk_event(member.guild.id, member.id, 45, "raid_join", f"{len(dq)} joins/{ANTI_RAID_WINDOW_SECONDS}s")
            await self._log(member.guild, "Anti-Raid tetiklendi", f"Son {ANTI_RAID_WINDOW_SECONDS} saniyede **{len(dq)}** yeni üye algılandı. Raid modu 2 dakika aktif.", member)

        age = datetime.now(timezone.utc) - member.created_at
        risk = 0; reasons = []
        if age < timedelta(days=NEW_ACCOUNT_RISK_DAYS):
            risk += 35; reasons.append(f"hesap yaşı {age.days} gün")
        if member.avatar is None:
            risk += 10; reasons.append("özel avatar yok")
        if time.time() < self.raid_until[member.guild.id]:
            risk += 45; reasons.append("aktif raid penceresinde katıldı")
        if risk:
            await store.add_risk_event(member.guild.id, member.id, risk, "join_risk", ", ".join(reasons))
        if risk >= 65:
            quarantined = await self._quarantine(member, ", ".join(reasons))
            await self._log(member.guild, "Yeni üye risk analizi", f"Risk skoru **{risk}/100**\nNeden: {', '.join(reasons)}\nKarantina: **{'uygulandı' if quarantined else 'rol bulunamadı'}**", member)

    def _message_risk(self, message: discord.Message) -> tuple[int, list[str]]:
        text = message.content or ""; low = text.lower(); score = 0; reasons=[]
        mentions = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone or mentions >= MASS_MENTION_LIMIT:
            score += 55; reasons.append(f"mass mention ({mentions})")
        urls = URL_RE.findall(text)
        if urls and any(token in low for token in SUSPICIOUS_TOKENS):
            score += 70; reasons.append("şüpheli link kalıbı")
        if BLOCK_INVITES and INVITE_RE.search(text):
            score += 45; reasons.append("izin verilmeyen Discord daveti")
        return score, reasons

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
            return
        if message.author.guild_permissions.manage_messages:
            return
        now=time.time(); key=(message.guild.id,message.author.id); q=self.messages[key]
        normalized=" ".join((message.content or "").lower().split())[:300]
        q.append((now,normalized))
        while q and now-q[0][0] > MESSAGE_SPAM_WINDOW:
            q.popleft()
        score,reasons=self._message_risk(message)
        if len(q) >= MESSAGE_SPAM_COUNT:
            score += 35; reasons.append(f"mesaj hızı {len(q)}/{MESSAGE_SPAM_WINDOW}s")
        if normalized and sum(1 for _,t in q if t==normalized) >= 4:
            score += 35; reasons.append("tekrarlanan mesaj fingerprint")
        if score <= 0:
            return
        await store.add_risk_event(message.guild.id,message.author.id,min(100,score),"message_risk",", ".join(reasons))
        if score >= 45:
            try: await message.delete()
            except discord.HTTPException: pass
        if score >= 70:
            try: await message.author.timeout(timedelta(minutes=10), reason="V-Tracker AutoMod: "+", ".join(reasons))
            except discord.HTTPException: pass
        await self._log(message.guild,"AutoMod olayı",f"Risk **{min(100,score)}/100**\nNeden: {', '.join(reasons)}\nMesaj: `{sanitize_text(message.content,180)}`",message.author)

    @commands.hybrid_command(name="risk", aliases=["riskscore"], description="Bir kullanıcının son güvenlik risk olaylarını özetler.")
    @commands.has_permissions(moderate_members=True)
    async def risk(self, ctx: commands.Context, member: discord.Member):
        rows=await store.risk_summary(ctx.guild.id,50); found=next((r for r in rows if str(r['user_id'])==str(member.id)),None)
        e=panel("User Risk",f"**{member.display_name}** güvenlik özeti")
        if not found: e.add_field(name="Risk",value="Kayıtlı risk olayı yok.",inline=False)
        else:
            score=min(100,int(found['total_score'])); level="HIGH" if score>=70 else "MEDIUM" if score>=35 else "LOW"
            e.add_field(name="Risk skoru",value=f"**{score}/100 — {level}**",inline=True)
            e.add_field(name="Olay sayısı",value=f"`{found['events']}`",inline=True)
            e.add_field(name="Son olay",value=str(found['last_event']),inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="quarantine", aliases=["karantina"], description="Kullanıcıyı karantina rolüne alır.")
    @commands.has_permissions(moderate_members=True)
    async def quarantine(self, ctx: commands.Context, member: discord.Member, *, reason: str="manuel güvenlik incelemesi"):
        ok=await self._quarantine(member,sanitize_text(reason,500))
        if not ok: return await ctx.send(embed=error("Karantina uygulanamadı","`V-Tracker Quarantine` rolü bulunamadı veya botun rol yetkisi yetersiz."))
        await store.add_risk_event(ctx.guild.id,member.id,25,"manual_quarantine",reason)
        await ctx.send(embed=success("Karantina uygulandı",f"{member.mention} yalnızca izin verilen alanlarda tutulabilir."))

    @commands.hybrid_command(name="unquarantine", aliases=["karantinacikar"], description="Karantina rolünü kaldırır.")
    @commands.has_permissions(moderate_members=True)
    async def unquarantine(self, ctx: commands.Context, member: discord.Member):
        role=self._quarantine_role(ctx.guild)
        if not role or role not in member.roles: return await ctx.send(embed=error("Karantina yok","Kullanıcıda karantina rolü bulunmuyor."))
        await member.remove_roles(role,reason="V-Tracker manual unquarantine")
        await ctx.send(embed=success("Karantina kaldırıldı",member.mention))

    @commands.hybrid_command(name="modpanel", aliases=["securitypanel"], description="Sunucunun V-Tracker güvenlik özetini gösterir.")
    @commands.has_permissions(moderate_members=True)
    async def modpanel(self, ctx: commands.Context):
        risks=await store.risk_summary(ctx.guild.id,8)
        e=panel("Security Center",f"**{ctx.guild.name}** için AutoMod ve risk görünümü")
        raid=time.time()<self.raid_until[ctx.guild.id]
        e.add_field(name="Anti-Raid",value="AKTİF" if raid else "Normal",inline=True)
        e.add_field(name="Spam limiti",value=f"{MESSAGE_SPAM_COUNT} mesaj / {MESSAGE_SPAM_WINDOW} sn",inline=True)
        e.add_field(name="Mass mention",value=f"{MASS_MENTION_LIMIT}+ mention",inline=True)
        if risks:
            lines=[]
            for r in risks:
                m=ctx.guild.get_member(int(r['user_id'])); name=m.display_name if m else r['user_id']
                lines.append(f"• **{name}** — `{min(100,int(r['total_score']))}/100` • {r['events']} olay")
            e.add_field(name="Risk listesi",value="\n".join(lines),inline=False)
        else: e.add_field(name="Risk listesi",value="Kayıtlı risk olayı yok.",inline=False)
        e.add_field(name="Araçlar",value="`v!risk @üye` • `v!quarantine @üye` • `v!auditlog` • `v!lockdown`",inline=False)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Protection(bot))
