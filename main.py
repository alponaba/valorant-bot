# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import os
import threading

import discord
from discord.ext import commands
from flask import Flask, jsonify, render_template

from config import AUTO_SYNC_COMMANDS, BOT_PREFIX, DISCORD_TOKEN, PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("VTracker")

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "V-Tracker"})


def run_web():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


class VTrackerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix=BOT_PREFIX, intents=intents, help_command=None, case_insensitive=True)

    async def setup_hook(self):
        extensions = [
            "cogs.registration",
            "cogs.stats",
            "cogs.economy",
            "cogs.tactical",
            "cogs.moderation",
            "cogs.server_tools",
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
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{BOT_PREFIX}help • Valorant stats")
        try:
            await self.change_presence(status=discord.Status.online, activity=activity)
        except Exception:
            pass

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return
        original = getattr(error, "original", error)
        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f"⏳ Bu komutu tekrar kullanmak için **{error.retry_after:.1f} sn** bekle.", delete_after=6)
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("❌ Bu komut için gerekli sunucu yetkisine sahip değilsin.", delete_after=7)
        if isinstance(error, commands.NotOwner):
            return await ctx.send("❌ Bu komut yalnızca bot sahibi tarafından kullanılabilir.", delete_after=7)
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"❌ Eksik parametre: `{error.param.name}`. `v!help` ile kullanımı kontrol et.", delete_after=8)
        if isinstance(error, commands.BadArgument):
            return await ctx.send("❌ Parametre biçimi geçersiz. Kullanıcı/numara bilgisini kontrol et.", delete_after=8)
        log.error("Command error: %r", original)
        try:
            await ctx.send("❌ Komut çalışırken beklenmeyen bir hata oluştu. Konsol logunu kontrol et.", delete_after=8)
        except Exception:
            pass


bot = VTrackerBot()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is missing. Copy .env.example and set the token in your host settings.")
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN, log_handler=None)
