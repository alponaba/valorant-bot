# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Riot OAuth2 (RSO) Güvenli Doğrulama Modülü
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import logging
from fastapi import FastAPI, Request
import uvicorn
import threading

logger = logging.getLogger("V-Tracker-RSO")

# --- RIOT DEVELOPER BILGILERINI BURAYA GIR ---
CLIENT_ID = "SENIN_RIOT_CLIENT_ID"
CLIENT_SECRET = "SENIN_RIOT_CLIENT_SECRET"
REDIRECT_URI = "http://localhost:8000/auth/callback"  # Canlıya alınca kendi domain/ip adresini yazmalısın
# ---------------------------------------------

file_lock = asyncio.Lock()

class SecureAuthDatabase:
    USERS_FILE = "global_registered_users.json"
    PENDING_FILE = "vtracker_rso_pending.json"

    @classmethod
    async def load_json(cls, filename):
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Dosya okuma hatası ({filename}): {e}")
        return {}

    @classmethod
    async def save_json(cls, filename, data):
        async with file_lock:
            temp_filename = f"{filename}.tmp"
            try:
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                os.replace(temp_filename, filename)
            except Exception as e:
                logger.error(f"Dosya yazma hatası ({filename}): {e}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

# FastAPI Web Sunucusu (Riot Callback'leri yakalamak için)
app = FastAPI()

@app.get("/auth/callback")
async def riot_callback(code: str, state: str):
    """
    Riot giriş yaptıktan sonra kullanıcıyı bu adrese yönlendirir.
    state parametresi Discord User ID'sini tutar.
    """
    discord_user_id = state
    
    # 1. Authorization Code ile Riot Token Alma
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
        async with session.post(token_url, headers=headers, data=payload) as resp:
            if resp.status != 200:
                return {"error": "Riot token alınamadı."}
            token_data = await resp.json()
            access_token = token_data.get("access_token")

        # 2. Access Token ile Kullanıcı Bilgilerini (PUUID) Çekme
        userinfo_url = "https://auth.riotgames.com/userinfo"
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        async with session.get(userinfo_url, headers=auth_headers) as resp:
            if resp.status != 200:
                return {"error": "Kullanıcı bilgileri alınamadı."}
            user_info = await resp.json()
            puuid = user_info.get("sub")
            region = user_info.get("region", "eu").lower()

        # 3. HenrikDev API üzerinden güncel Riot ID (İsim#Tag) öğrenme
        account_url = f"https://api.henrikdev.xyz/valorant/v1/by-puuid/account/{puuid}"
        async with session.get(account_url) as resp:
            if resp.status != 200:
                return {"error": "Riot hesap detayları çözülemedi."}
            acc_json = await resp.json()
            acc_data = acc_json.get("data", {})
            name = acc_data.get("name", "Bilinmiyor")
            tag = acc_data.get("tag", "TR1")

    # 4. Veritabanına Kaydetme (Mevcut V-Coin ve kozmetikleri koruyarak)
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
        "dc_name": "DiscordUser", # İsteğe bağlı güncellenebilir
        "v_coins": existing_coins,
        "cosmetics": existing_cosmetics
    }
    await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)

    # Şık bir HTML başarı sayfası döndür
    return HTMLResponse(content="""
        <html>
            <body style="background-color: #0f1923; color: #ff4655; font-family: Arial, sans-serif; text-align: center; padding-top: 100px;">
                <h1>🎉 Hesap Başarıyla Doğrulandı!</h1>
                <p style="color: #ece8e1;">V-Tracker hesabınız güvenle eşleştirildi. Bu pencereyi kapatıp Discord'a dönebilirsiniz.</p>
            </body>
        </html>
    """)

from fastapi.responses import HTMLResponse

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


class RiotOAuthSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # FastAPI sunucusunu arka planda (daemon thread olarak) başlatıyoruz
        threading.Thread(target=run_fastapi, daemon=True).start()

    @commands.hybrid_command(name="dogrula", description="Riot hesabınızı güvenli RSO altyapısı ile resmi olarak bağlar.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dogrula(self, ctx):
        user_id = str(ctx.author.id)

        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        if user_id in users and users[user_id].get("puuid"):
            return await ctx.send("⚠️ Zaten doğrulanmış ve sisteme bağlı bir Riot hesabın var! Değiştirmek için önce `v!unregister` kullanmalısın.")

        # Riot OAuth Giriş Linki (state parametresine Discord User ID'sini ekliyoruz)
        auth_url = (
            f"https://auth.riotgames.com/authorize?"
            f"client_id={CLIENT_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid&"
            f"state={user_id}"
        )

        embed = discord.Embed(
            title="🛡️ Güvenli Riot Hesap Doğrulaması (RSO)",
            description=(
                "Hesabınızı eşleştirmek için aşağıdaki resmi Riot Games bağlantısını kullanın.\n\n"
                "🔒 **Güvence:** Şifreniz asla botumuz tarafından görülmez. İşlem doğrudan **Riot Games'in resmi sunucuları** üzerinden şifrelenmiş olarak gerçekleşir.\n\n"
                f"👉 **[Resmi Riot Giriş Sayfası için Tıklayın]({auth_url})**"
            ),
            color=0xFF4655
        )
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RiotOAuthSystem(bot))
    logger.info("Riot OAuth2 Güvenlik Modülü başarıyla yüklendi ve Web Sunucusu aktif!")