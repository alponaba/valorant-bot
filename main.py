# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque

import discord
from discord.ext import commands
from flask import Flask, jsonify, render_template

from config import (
    AUTO_SYNC_COMMANDS,
    BOT_PREFIX,
    DISCORD_TOKEN,
    GLOBAL_GUILD_RATE,
    GLOBAL_GUILD_WINDOW,
    GLOBAL_USER_RATE,
    GLOBAL_USER_WINDOW,
    PORT,
)
from database import db
from security import DISCORD_ALLOWED_MENTIONS
from valorant_api import api

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("VTracker")

app = Flask(__name__)
BOT_START_TIME = time.time()


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "V-Tracker",
        "uptime_seconds": int(time.time() - BOT_START_TIME),
        "api": api.status(),
    })


def run_web():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


class VTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=DISCORD_ALLOWED_MENTIONS,
        )
        self.started_at = BOT_START_TIME
        self.user_window = defaultdict(deque)
        self.guild_window = defaultdict(deque)
        self.add_check(self._global_check)

    async def setup_hook(self):
        extensions = [
            "cogs.registration",
            "cogs.stats",
            "cogs.economy",
            "cogs.tactical",
            "cogs.moderation",
            "cogs.server_tools",
            "cogs.community",
            "cogs.protection",
            "cogs.automation",
            "cogs.reports",
            "cogs.help",
        ]
        for ext in extensions:
            try:
                await self.load_extension(ext)
                log.info("Loaded %s", ext)
            except Exception:
                log.exception("Failed to load %s", ext)

        if AUTO_SYNC_COMMANDS:
            try:
                synced = await self.tree.sync()
                log.info("Synced %s slash commands", len(synced))
            except Exception:
                log.exception("Slash command sync failed")

    async def on_ready(self):
        log.info("Bot ready: %s (%s)", self.user, self.user.id if self.user else "?")
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{BOT_PREFIX}help • V-Tracker 4.0")
        try:
            await self.change_presence(status=discord.Status.online, activity=activity)
        except Exception:
            pass

    def _check_global_rate(self, ctx: commands.Context) -> tuple[bool, float]:
        now = time.time()
        uid = ctx.author.id
        dq = self.user_window[uid]
        while dq and now - dq[0] > GLOBAL_USER_WINDOW:
            dq.popleft()
        if len(dq) >= GLOBAL_USER_RATE:
            return False, max(0.0, GLOBAL_USER_WINDOW - (now - dq[0]))
        dq.append(now)

        if ctx.guild:
            gid = ctx.guild.id
            gdq = self.guild_window[gid]
            while gdq and now - gdq[0] > GLOBAL_GUILD_WINDOW:
                gdq.popleft()
            if len(gdq) >= GLOBAL_GUILD_RATE:
                return False, max(0.0, GLOBAL_GUILD_WINDOW - (now - gdq[0]))
            gdq.append(now)
        return True, 0.0

    async def _global_check(self, ctx: commands.Context) -> bool:
        if await self.is_owner(ctx.author):
            return True
        ok, retry_after = self._check_global_rate(ctx)
        if not ok:
            cooldown = commands.Cooldown(1, max(1.0, retry_after))
            raise commands.CommandOnCooldown(cooldown, retry_after, commands.BucketType.user)
        return True

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return
        original = getattr(error, "original", error)
        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f"⏳ Bu komutu tekrar kullanmak için **{error.retry_after:.1f} sn** bekle.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("❌ Bu komut için gerekli sunucu yetkisine sahip değilsin.")
        if isinstance(error, commands.NotOwner):
            return await ctx.send("❌ Bu komut yalnızca bot sahibi tarafından kullanılabilir.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"❌ Eksik parametre: `{error.param.name}`. `v!help` ile kullanımı kontrol et.")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("❌ Parametre biçimi geçersiz. Kullanıcı/numara bilgisini kontrol et.")
        error_id = f"VT-{uuid.uuid4().hex[:6].upper()}"
        log.exception("[%s] Command error in %s", error_id, getattr(ctx.command, 'qualified_name', '?'))
        try:
            await ctx.send(f"❌ Komut çalışırken beklenmeyen bir hata oluştu. Hata Kimliği: `{error_id}`")
        except Exception:
            pass


bot = VTrackerBot()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is missing. Copy .env.example and set the token in your host settings.")
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN, log_handler=None)
