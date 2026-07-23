# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Gelişmiş Kayıt Sistemi (Register Modülü)
Modül: cogs.register
"""

import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# =====================================================================
# 1. LOGLAMA YAPILANDIRMASI
# =====================================================================

logger = logging.getLogger("VTracker.Register")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

GLOBAL_DB_FILE = "global_registered_users.json"
# Güncel HenrikDev API Anahtarınız
API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"

# =====================================================================
# 2. GLOBAL VERİTABANI YÖNETİCİSİ
# =====================================================================

class GlobalDatabase:
    @staticmethod
    def load_db() -> Dict[str, Any]:
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    return json.loads(content) if content else {}
            except Exception as e:
                logger.error(f"Veritabanı okuma hatası: {e}")
                return {}
        return {}

    @staticmethod
    def save_db(data: Dict[str, Any]) -> None:
        try:
            with open(GLOBAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Veritabanı yazma hatası: {e}")

    @staticmethod
    def register_user(discord_id: str, puuid: str, name: str, tag: str, region: str) -> None:
        db = GlobalDatabase.load_db()
        db[discord_id] = {
            "puuid": puuid,
            "name": name,
            "tag": tag,
            "region": region,
            "v_coins": db.get(discord_id, {}).get("v_coins", 0),
            "updated_at": datetime.utcnow().isoformat()
        }
        GlobalDatabase.save_db(db)

    @staticmethod
    def get_user(discord_id: str) -> Optional[Dict[str, Any]]:
        return GlobalDatabase.load_db().get(discord_id)

# =====================================================================
# 3. VALORANT API İSTEMCİSİ
# =====================================================================

class ValorantAccountAPI:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.primary_base = "https://api.henrikdev.xyz"

    def get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "V-Tracker-Bot/6.0",
            "Authorization": API_KEY
        }

    async def fetch_account(self, session: aiohttp.ClientSession, name: str, tag: str) -> Dict[str, Any]:
        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"{self.primary_base}/valorant/v1/account/{encoded_name}/{encoded_tag}"
        
        try:
            async with session.get(url, headers=self.get_headers(), timeout=15) as response:
                status = response.status
                if status == 200:
                    data = await response.json()
                    if data and data.get("data"):
                        acc = data["data"]
                        return {
                            "puuid": acc.get("puuid"),
                            "region": (acc.get("region") or "eu").lower(),
                            "name": acc.get("name", name),
                            "tag": acc.get("tag", tag),
                            "success": True
                        }
                return {"success": False, "status": status}
        except Exception as e:
            logger.error(f"Hesap sorgulama hatası: {e}")
            return {"success": False, "status": 500}

# =====================================================================
# 4. KAYIT KOMUTU (REGISTER COG)
# =====================================================================

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_client = ValorantAccountAPI(bot)

    @commands.command(name="register", aliases=["kayit"])
    async def register_command(self, ctx, discord_id_input: str = None, *, riot_id: str = None):
        """
        Kullanım: v!register [Discord ID] [İsim#Tag]
        """
        
        # 1. Girdi Kontrolleri
        if not discord_id_input or not riot_id:
            embed = discord.Embed(
                title="❌ Hatalı Kullanım",
                description="Lütfen komutu doğru formatta girin.\n**Kullanım:** `v!register [Discord ID] [Riotİsmi#Tag]`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # 2. Discord ID Doğrulaması
        if not discord_id_input.isdigit():
            embed = discord.Embed(
                title="❌ Geçersiz Discord ID",
                description="Girdiğiniz Discord ID yalnızca rakamlardan oluşmalıdır.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # 3. Boşluk Kontrolü
        if " " in riot_id:
            embed = discord.Embed(
                title="❌ Boşluk Hatası",
                description="Riot adınızda veya tag (#) çevresinde boşluk bulunmamalıdır.\n**Doğru Örnek:** `v!register 1234567890 Oyuncu#TR1`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # 4. Hashtag Kontrolü
        if "#" not in riot_id:
            embed = discord.Embed(
                title="❌ Tag Hatası",
                description="Riot ID'niz `#` işareti içermelidir.\n**Doğru Örnek:** `Oyuncu#TR1`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        name, tag = riot_id.split("#", 1)
        msg = await ctx.send(f"🔍 API üzerinden `{name}#{tag}` doğrulanıyor, lütfen bekleyin...")

        # 5. API Doğrulaması
        async with aiohttp.ClientSession() as session:
            acc_data = await self.api_client.fetch_account(session, name, tag)

            if not acc_data["success"]:
                status_code = acc_data.get('status')
                err_msg = f"❌ **{name}#{tag}** doğrulanamadı. (API Hata Kodu: {status_code})"
                if status_code == 401:
                    err_msg += "\n⚠️ API anahtarı yetkisiz/geçersiz. Lütfen HenrikDev portalından anahtarın aktifliğini kontrol edin."
                return await msg.edit(content=err_msg)

            fetched_puuid = acc_data["puuid"]
            fetched_name = acc_data["name"]
            fetched_tag = acc_data["tag"]
            fetched_region = acc_data["region"]

            # 6. Veritabanı ve İsim Değişikliği Kontrolü
            existing_user = GlobalDatabase.get_user(discord_id_input)

            if existing_user:
                old_riot_id = f"{existing_user['name']}#{existing_user['tag']}"
                new_riot_id = f"{fetched_name}#{fetched_tag}"

                if existing_user["puuid"] == fetched_puuid:
                    if old_riot_id.lower() != new_riot_id.lower():
                        GlobalDatabase.register_user(discord_id_input, fetched_puuid, fetched_name, fetched_tag, fetched_region)
                        
                        embed_change = discord.Embed(
                            title="⚠️ Ad Değişikliği Tespit Edildi",
                            description=f"Discord ID (`{discord_id_input}`) sistemde zaten tanınıyor.",
                            color=discord.Color.gold()
                        )
                        embed_change.add_field(name="Eski Kayıtlı İsim", value=f"`{old_riot_id}`", inline=False)
                        embed_change.add_field(name="Yeni Doğrulanan İsim", value=f"`{new_riot_id}`", inline=False)
                        embed_change.set_footer(text="Veritabanı başarıyla güncellendi.")
                        
                        return await msg.edit(content=None, embed=embed_change)
                    else:
                        return await msg.edit(content=f"✅ Discord ID (`{discord_id_input}`) zaten `{new_riot_id}` olarak güncel şekilde sisteme kayıtlı.")
                else:
                    GlobalDatabase.register_user(discord_id_input, fetched_puuid, fetched_name, fetched_tag, fetched_region)
                    
                    embed_new_acc = discord.Embed(
                        title="🔄 Bağlı Hesap Değiştirildi",
                        description=f"Discord ID (`{discord_id_input}`) üzerindeki eski hesap güncellendi.",
                        color=discord.Color.blue()
                    )
                    embed_new_acc.add_field(name="Eski Hesap", value=f"`{old_riot_id}`", inline=True)
                    embed_new_acc.add_field(name="Yeni Hesap", value=f"`{new_riot_id}`", inline=True)
                    
                    return await msg.edit(content=None, embed=embed_new_acc)

            else:
                GlobalDatabase.register_user(discord_id_input, fetched_puuid, fetched_name, fetched_tag, fetched_region)
                
                embed_success = discord.Embed(
                    title="✅ Kayıt Başarılı",
                    description=f"Discord ID (`{discord_id_input}`) global sisteme eklendi.",
                    color=discord.Color.green()
                )
                embed_success.add_field(name="Bağlanan Riot Hesabı", value=f"`{fetched_name}#{fetched_tag}`", inline=False)
                
                return await msg.edit(content=None, embed=embed_success)

async def setup(bot):
    await bot.add_cog(Register(bot))
    logger.info("Register Modülü yüklendi.")