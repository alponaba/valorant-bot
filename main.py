# -*- coding: utf-8 -*-
from flask import Flask, render_template
import discord
from discord.ext import commands
import os
import threading

# =====================================================================
# 1. 7/24 AKTİF KALMA (WEB SUNUCUSU - FLASK)
# =====================================================================
app = Flask('')

@app.route('/')
def home():
  return render_template('index.html')

@app.route('/.well-known/discord')
def discord_verify():
    return "dh=aa44aef03e80a8df234ab8c0ad0b12b8de94375c"

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

if __name__ == '__main__':
  keep_alive()
  token = os.getenv('DISCORD_TOKEN')
  bot.run(token)