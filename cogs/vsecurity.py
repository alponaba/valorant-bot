# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Riot OAuth2 (RSO) Güvenli Kayıt ve Doğrulama Modülü
Bu modül, kullanıcıların Riot hesaplarını resmi RSO (Riot Sign-On) altyapısı
ile %100 güvenli bir şekilde doğrulamalarını sağlar.
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import logging
import re
import threading
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

# Loglama Ayarları
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("V-Tracker-Security")

# ==============================================================================
# AYARLAR (RENDER VE RIOT İÇİN)
# ==============================================================================
CLIENT_ID = "SENIN_RIOT_CLIENT_ID"
CLIENT_SECRET = "SENIN_RIOT_CLIENT_SECRET"
REDIRECT_URI = "http://localhost:8000/auth/callback" # Canlıda kendi domain/render linkini yaz
PORT = int(os.environ.get("PORT", 8000))

# ==============================================================================
# VERİTABANI YÖNETİMİ
# ==============================================================================
file_lock = asyncio.Lock()

class SecureAuthDatabase:
    USERS_FILE = "global_registered_users.json"
    BACKUP_FILE = "global_registered_users_backup.json"

    @classmethod
    async def load_json(cls, filename: str) -> Dict[str, Any]:
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Dosya okuma hatası ({filename}): {e}")
            if os.path.exists(cls.BACKUP_FILE):
                with open(cls.BACKUP_FILE, "r", encoding="utf-8") as bf:
                    return json.loads(bf.read().strip())
        return {}

    @classmethod
    async def save_json(cls, filename: str, data: Dict[str, Any]) -> None:
        async with file_lock:
            temp_filename = f"{filename}.tmp"
            try:
                if os.path.exists(filename):
                    import shutil
                    shutil.copy(filename, cls.BACKUP_FILE)
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                os.replace(temp_filename, filename)
            except Exception as e:
                logger.error(f"Dosya yazma hatası ({filename}): {e}")

# ==============================================================================
# FASTAPI WEB SUNUCUSU (RIOT YÖNLENDİRMESİ)
# ==============================================================================
app = FastAPI(title="V-Tracker RSO Auth")

@app.get("/auth/callback")
async def riot_callback(code: str, state: str):
    discord_user_id = state
    token_url = "https://auth.riotgames.com/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(token_url, headers=headers, data=payload) as resp:
                if resp.status != 200:
                    return HTMLResponse("<h1 style='color:red;'>Hata: Riot token alınamadı. İşlem iptal edildi.</h1>", status_code=400)
                token_data = await resp.json()
                access_token = token_data.get("access_token")

            userinfo_url = "https://auth.riotgames.com/userinfo"
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            async with session.get(userinfo_url, headers=auth_headers) as resp:
                if resp.status != 200:
                    return HTMLResponse("<h1 style='color:red;'>Hata: Kullanıcı kimliği (PUUID) alınamadı.</h1>", status_code=400)
                user_info = await resp.json()
                puuid = user_info.get("sub")
                region = user_info.get("region", "eu").lower()

            account_url = f"https://api.henrikdev.xyz/valorant/v1/by-puuid/account/{puuid}"
            async with session.get(account_url) as resp:
                if resp.status != 200:
                    name, tag = "Bilinmiyor", "TR1"
                else:
                    acc_json = await resp.json()
                    acc_data = acc_json.get("data", {})
                    name = acc_data.get("name", "Bilinmiyor")
                    tag = acc_data.get("tag", "TR1")

            users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
            existing_cosmetics = users.get(discord_user_id, {}).get("cosmetics", {
                "color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []
            })
            existing_coins = users.get(discord_user_id, {}).get("v_coins", 0)

            users[discord_user_id] = {
                "puuid": puuid,
                "name": name,
                "tag": tag,
                "region": region,
                "dc_name": "DiscordUser",
                "v_coins": existing_coins,
                "cosmetics": existing_cosmetics,
                "is_verified": True
            }
            
            await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)

            success_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ background-color: #0f1923; color: #ece8e1; font-family: sans-serif; text-align: center; margin-top: 15vh; }}
                    .container {{ background-color: #1f2326; padding: 40px; border-radius: 12px; border-top: 5px solid #ff4655; display: inline-block; }}
                    h1 {{ color: #ff4655; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Doğrulama Başarılı!</h1>
                    <p>Riot hesabınız (<strong>{name}#{tag}</strong>) V-Tracker sistemine güvenle bağlandı.</p>
                    <p>Bu sekmeyi kapatıp Discord'a dönebilirsiniz.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=success_html)
        except Exception as e:
            logger.error(f"Callback işlemi sırasında hata: {e}")
            return HTMLResponse("<h1>Sunucu Hatası.</h1>", status_code=500)

def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

# ==============================================================================
# DISCORD BOT - DOĞRULAMA KOMUTLARI
# ==============================================================================
class RiotOAuthSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        threading.Thread(target=run_fastapi, daemon=True).start()

    def is_valid_format(self, riot_id: str) -> bool:
        if not riot_id:
            return False
        return bool(re.match(r"^.{3,16}#.{2,5}$", str(riot_id).strip()))

    @commands.hybrid_command(name="dogrula", aliases=["verify"], description="Riot hesabınızın size ait olduğunu resmi olarak doğrular.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dogrula_command(self, ctx, *, riot_id: str = None):
        if not self.is_valid_format(riot_id):
            error_embed = discord.Embed(
                title="❌ Hatalı veya Eksik Format",
                description=(
                    "Sisteme kayıt olmak için Riot İsminizi ve Etiketinizi eksiksiz girmelisiniz.\n\n"
                    "**Doğru Kullanım Şekli:**\n"
                    "`v!dogrula OyuncuAdı#Etiket`\n\n"
                    "**Örnekler:**\n"
                    "✅ `v!dogrula Tenz#NA1`\n"
                    "✅ `v!dogrula Alperen#TR1`\n\n"
                    "*Lütfen arada boşluk bırakmadan, `#` işareti ile birlikte tam Riot ID'nizi yazarak tekrar deneyin.*"
                ),
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed, ephemeral=True)

        user_id = str(ctx.author.id)
        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        
        if user_id in users and users[user_id].get("is_verified"):
            registered_name = f"{users[user_id].get('name')}#{users[user_id].get('tag')}"
            return await ctx.send(f"⚠️ Sisteme zaten **{registered_name}** adlı Riot hesabınla bağlısın! Yeni bir hesap bağlamak için önce `v!hesapsil` yazmalısın.", ephemeral=True)

        auth_url = (
            f"https://auth.riotgames.com/authorize?"
            f"client_id={CLIENT_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid&"
            f"state={user_id}"
        )

        embed = discord.Embed(
            title="🛡️ Riot Games Resmi Hesap Doğrulaması",
            description=(
                f"Selam! Başkalarının senin adına kayıt olmasını engellemek için **{riot_id}** hesabının "
                "gerçekten sana ait olduğunu kanıtlaman gerekiyor.\n\n"
                "Aşağıdaki butona tıklayarak doğrudan **Riot Games'in resmi sayfasına** yönlendirileceksin."
            ),
            color=0xFF4655
        )
        
        embed.add_field(
            name="🔒 Şifremi Bot Görecek Mi?",
            value="**HAYIR.** Yönlendirileceğin sayfa V-Tracker'a ait değildir. Adres çubuğunda `auth.riotgames.com` yazan %100 orijinal Riot sunucusudur. Şifreni sadece Riot Games görür.",
            inline=False
        )
        embed.add_field(
            name="🔑 PUUID Nedir ve Bot Ne Alıyor?",
            value="Sen giriş yaptıktan sonra Riot Games bize sadece **PUUID** adı verilen uzun, şifrelenmiş bir numara gönderir. Bu numara ile hesabına giriş yapılması, maç başlatılması veya VP harcanması teknik olarak **imkansızdır**. Sadece maç istatistiklerini çekmek için kullanılır.",
            inline=False
        )
        embed.add_field(
            name="✅ Nasıl Yapacağım?",
            value="1️⃣ Mavi butona tıkla.\n2️⃣ Riot hesabına giriş yap.\n3️⃣ 'Doğrulandı' yazısını görünce Discord'a geri dön.",
            inline=False
        )
        embed.set_thumbnail(url="https://logodownload.org/wp-content/uploads/2019/12/riot-games-logo-0.png")
        embed.set_footer(text="V-Tracker.gg • Güvenliğinizi Önemsiyoruz")

        view = discord.ui.View()
        button = discord.ui.Button(label="Resmi Site Üzerinden Doğrula", style=discord.ButtonStyle.link, url=auth_url, emoji="🔗")
        view.add_item(button)

        await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="hesapsil", description="Doğrulanmış Riot hesabınızın bağlantısını keser.")
    async def hesapsil_command(self, ctx):
        user_id = str(ctx.author.id)
        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        
        if user_id not in users or not users[user_id].get("is_verified"):
            return await ctx.send("❌ Sisteme kayıtlı ve doğrulanmış bir hesabın zaten yok.", ephemeral=True)
            
        del users[user_id]
        await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)
        await ctx.send("✅ Riot hesabının V-Tracker ile olan bağlantısı tamamen kesildi.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RiotOAuthSystem(bot))