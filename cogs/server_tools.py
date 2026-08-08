from __future__ import annotations

import time

import discord
from discord.ext import commands

from config import ADMIN_LOG_CHANNEL_ID, SUGGESTION_CHANNEL_ID
from database import db
from security import DISCORD_ALLOWED_MENTIONS, sanitize_text
from theme import error, panel, success
from valorant_api import api


class ServerTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="suggest", aliases=["oneri", "öneri"], description="Bot/sunucu önerisi gönderir.")
    async def suggest(self, ctx, *, text: str):
        clean = sanitize_text(text, 1200)
        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID) if SUGGESTION_CHANNEL_ID else None
        e = panel("💡 Yeni Öneri", clean)
        e.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        if channel:
            msg = await channel.send(embed=e, allowed_mentions=DISCORD_ALLOWED_MENTIONS)
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            await ctx.send(embed=success("Öneri gönderildi", f"{channel.mention} kanalına iletildi."), ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(embed=e)

    @commands.hybrid_command(name="join", aliases=["gel"], description="Bulunduğun ses kanalına katılır.")
    async def join(self, ctx):
        if not getattr(ctx.author, "voice", None) or not ctx.author.voice.channel:
            return await ctx.send(embed=error("Ses kanalı yok", "Önce bir ses kanalına gir."))
        if ctx.voice_client:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        else:
            await ctx.author.voice.channel.connect()
        await ctx.send(embed=success("Ses kanalına bağlandım", ctx.author.voice.channel.name))

    @commands.hybrid_command(name="leave", aliases=["cik", "çık", "git"], description="Ses kanalından ayrılır.")
    async def leave(self, ctx):
        if not ctx.voice_client:
            return await ctx.send(embed=error("Bağlı değilim", "Şu anda ses kanalında değilim."))
        await ctx.voice_client.disconnect(force=True)
        await ctx.send(embed=success("Ayrıldım", "Ses bağlantısı kapatıldı."))

    @commands.hybrid_command(name="status", aliases=["durum"], description="Bot sistem durumunu gösterir.")
    @commands.has_permissions(administrator=True)
    async def status(self, ctx):
        stats = await db.system_counts()
        api_state = api.status()
        uptime = int(time.time() - self.bot.started_at)
        hours, rem = divmod(uptime, 3600)
        mins, secs = divmod(rem, 60)
        e = panel("🖥️ V-Tracker System Status", "Deploy ve sağlık takibi için anlık sistem özeti")
        e.add_field(name="Discord", value=f"Gateway: `online`\nGuilds: `{len(self.bot.guilds)}`\nUsers: `{sum(g.member_count or 0 for g in self.bot.guilds)}`", inline=True)
        e.add_field(name="API", value=f"Circuit: `{'OPEN' if api_state['circuit_open'] else 'OK'}`\nLatency: `{api_state['last_latency_ms']} ms`\nCache: `{api_state['cache_entries']}`", inline=True)
        e.add_field(name="Uptime", value=f"`{hours}h {mins}m {secs}s`", inline=True)
        e.add_field(name="DB", value=f"Users: `{stats['users']}`\nPending verify: `{stats['pending']}`\nWarnings: `{stats['warnings']}`\nEconomy events: `{stats['economy_events']}`", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="setup", description="Temel V-Tracker sunucu kanallarını/rollerini kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_server(self, ctx):
        guild = ctx.guild
        if not guild:
            return await ctx.send(embed=error("Sunucu gerekli", "Bu komut DM'de kullanılamaz."))
        role_names = [
            ("Doğrulanmış Oyuncu", 0x44D39A),
            ("V-Tracker Verifier", 0xF7D774),
            ("Iron", 0x7F8C8D),
            ("Bronze", 0xA97142),
            ("Silver", 0xBDC3C7),
            ("Gold", 0xF7D774),
            ("Platinum", 0x2FD6C4),
            ("Diamond", 0x7DE8FF),
            ("Ascendant", 0x44D39A),
            ("Immortal", 0xF26C6C),
            ("Radiant", 0xF7D774),
            ("V-Tracker Quarantine", 0xF7D774),
        ]
        for name, color in role_names:
            if not discord.utils.get(guild.roles, name=name):
                await guild.create_role(name=name, color=discord.Color(color), reason="V-Tracker setup")
        cat = discord.utils.get(guild.categories, name="V-TRACKER") or await guild.create_category("V-TRACKER")
        names = ["v-tracker-komut", "istatistikler", "tracker-feed", "lfg", "öneriler", "dogrulama", "automod-log", "admin-log"]
        for name in names:
            if not discord.utils.get(guild.text_channels, name=name):
                await guild.create_text_channel(name, category=cat)
        quarantine = discord.utils.get(guild.roles, name="V-Tracker Quarantine")
        verify_channel = discord.utils.get(guild.text_channels, name="dogrulama")
        if quarantine:
            for channel in guild.text_channels:
                try:
                    if verify_channel and channel.id == verify_channel.id:
                        await channel.set_permissions(quarantine, view_channel=True, send_messages=True, read_message_history=True)
                    else:
                        await channel.set_permissions(quarantine, send_messages=False, add_reactions=False)
                except discord.HTTPException:
                    pass
        await db.log_admin_action(guild.id, ctx.author.id, 0, "SETUP", "roles+channels provisioned")
        await ctx.send(embed=success("Kurulum tamamlandı", "V-Tracker kategorisi, temel kanallar ve roller hazır. `VERIFIER_ROLE_ID`, `VERIFICATION_CHANNEL_ID`, `SUGGESTION_CHANNEL_ID`, `ADMIN_LOG_CHANNEL_ID` değerlerini ortam değişkenlerine gir."))


async def setup(bot):
    await bot.add_cog(ServerTools(bot))
