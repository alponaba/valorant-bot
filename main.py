# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
from flask import Flask
import threading

# =====================================================================
# 1. 7/24 AKTİF KALMA (WEB SUNUCUSU - FLASK)
# =====================================================================
app = Flask('')

@app.route('/')
def home():
    return "V-Tracker.gg Bot Aktif ve 7/24 Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# =====================================================================
# 2. BOT YETKİLERİ (INTENTS) VE SINIF YAPISI
# =====================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Ses kanalları ve ses özellikleri için aktif

class VTrackerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="v!", intents=intents, help_command=None)
        # HenrikDev API Anahtarın
        self.henrik_api_key = "HDEV-e534fbfe-c3c4-4f21-bccc-54eeb39fd27d"

    async def setup_hook(self):
        print("---------------------------------------------")
        print("🚀 V-Tracker.gg Asistanı başlatılıyor...")
        
        # cogs klasöründeki tüm modülleri otomatik ve güvenli şekilde yükler
        if os.path.exists("./cogs"):
            for filename in os.listdir("./cogs"):
                if filename.endswith(".py"):
                    cog_name = filename[:-3]
                    try:
                        await self.load_extension(f"cogs.{cog_name}")
                        print(f"📦 [COGS] cogs.{cog_name} başarıyla yüklendi.")
                    except Exception as e:
                        print(f"❌ [HATA] cogs.{cog_name} yüklenemedi: {e}")
        print("---------------------------------------------")

    async def on_ready(self):
        print(f"✅ Bot Aktif! Giriş yapıldı: {self.user} (ID: {self.user.id})")
        print("🎮 V-Tracker.gg sistemleri çalışmaya hazır.")
        print("---------------------------------------------")

bot = VTrackerBot()

# Botunu Çalıştıracak Token
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    # 1. Arka planda web sunucusunu (Flask) başlatır (Render / UptimeRobot için)
    keep_alive()
    # 2. Discord botunu başlatır
    bot.run(BOT_TOKEN)