# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Gelişmiş Özellikler ve Güvenlik Modülü (advanced_features.py)
Kapsam: Concurrent Write Lock, URL Sanitization, TTL Cache, Otomatik Retry, Otomatik Rol, Dinamik Ödül & Cooldown
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import time
import random
import re
import logging

logger = logging.getLogger("V-Tracker-Features")

# =====================================================================
# GÜVENLİK 1: EŞ ZAMANLI YAZMA KİLİDİ (Concurrent Write Lock)
# =====================================================================
file_lock = asyncio.Lock()

class SafeDatabase:
    @staticmethod
    async def save_json(filename: str, data: dict):
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

    @staticmethod
    def load_json(filename: str) -> dict:
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Dosya okuma hatası ({filename}): {e}")
            return {}

# =====================================================================
# GÜVENLİK 2: URL SANITIZATION (Zararlı/Sahte URL & Script Koruması)
# =====================================================================
def is_safe_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url_pattern = re.compile(r'^https?://[^\s<>"]+|www\.[^\s<>"]+$', re.IGNORECASE)
    if not url_pattern.match(url):
        return False
    dangerous_keywords = ["javascript:", "data:", "vbscript:", "onload=", "onerror="]
    if any(keyword in url.lower() for keyword in dangerous_keywords):
        return False
    return True

# =====================================================================
# API TTL CACHE & OTOMATİK YENİDEN DENEME (Retry & Rate Limit Koruması)
# =====================================================================
class CachedRiotAPI:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 Dakika
        self.headers = {"User-Agent": "V-Tracker-Bot/2.5"}

    async def get_mmr_with_retry(self, session: aiohttp.ClientSession, region: str, puuid: str):
        cache_key = f"mmr_{region}_{puuid}"
        now = time.time()

        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if now - timestamp < self.cache_ttl:
                return data

        url = f"https://api.henrikdev.xyz/valorant/v2/mmr/{region}/by-puuid/{puuid}"
        
        for attempt in range(3):
            try:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        self.cache[cache_key] = (res_data, now)
                        return res_data
                    elif resp.status == 429:
                        await asyncio.sleep(2 * (attempt + 1))
                    else:
                        break
            except Exception as e:
                logger.warning(f"API Bağlantı Hatası (Deneme {attempt+1}/3): {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(1.5)
        return None

# =====================================================================
# GELİŞMİŞ ÖZELLİKLER COG (v!updateroles, v!daily, Cooldown ve Dinamik Metinler)
# =====================================================================
class AdvancedFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.riot_api = CachedRiotAPI()
        
        # Dinamik Ödül Metinleri
        self.daily_flavor_texts = [
            "🚀 Operasyon masasından günlük lojistik desteğin alındı komutan!",
            "⚡ Ajan kasana taktiksel V-Coin bütçesi aktarıldı, iyi harcamalar!",
            "🎯 Hedef vuruldu! Günlük ödülün başarıyla hesabına tanımlandı.",
            "🔥 Savaş alanı fonları cüzdanına eklendi, rakiplerini alt etmeye hazır ol!"
        ]

    # --- MERKEZİ COOLDOWN HATA YÖNETİMİ (<t:Tarih:R> Destekli) ---
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            retry_timestamp = int(time.time() + error.retry_after)
            embed = discord.Embed(
                title="⏳ Taktiksel Bekleme Süresi",
                description=f"Bu komut soğuma aşamasında. Tekrar kullanabilmek için **<t:{retry_timestamp}:R>** beklemelisin.",
                color=0xFF4655
            )
            await ctx.send(embed=embed, delete_after=10)

    # --- OTOMATİK SUNUCU ROLLERİ (v!updateroles) ---
    @commands.hybrid_command(name="updateroles", description="Güncel Valorant kademene göre sunucu rolünü otomatik günceller.")
    async def updateroles_command(self, ctx):
        user_id = str(ctx.author.id)
        users_data = SafeDatabase.load_json("vtracker_users.json")
        user_info = users_data.get(user_id)

        if not user_info:
            return await ctx.send("❌ Önce `v!kayit İsim#Tag` komutuyla hesabını bağlamalısın!")

        puuid = user_info["puuid"]
        region = user_info["region"]

        loading = await ctx.send("🔄 Güncel Valorant kademen sorgulanıyor...")

        async with aiohttp.ClientSession() as session:
            mmr_data = await self.riot_api.get_mmr_with_retry(session, region, puuid)

            if not mmr_data or "data" not in mmr_data:
                return await loading.edit(content="❌ Kademe verisi alınamadı. API yanıt vermiyor.")

            current_tier = mmr_data["data"].get("currenttierpatched")
            if not current_tier:
                return await loading.edit(content="❌ Aktif bir rekabetçi kademen bulunamadı.")

            guild_role = discord.utils.get(ctx.guild.roles, name=current_tier)
            if not guild_role:
                return await loading.edit(content=f"⚠️ `{current_tier}` kademen bulundu ancak sunucuda bu isimde bir rol (**{current_tier}**) oluşturulmamış! Lütfen sunucu yöneticisine bildir.")

            try:
                if guild_role not in ctx.author.roles:
                    await ctx.author.add_roles(guild_role)

                embed = discord.Embed(
                    title="🛡️ Rol Senkronizasyonu Başarılı",
                    description=f"Güncel kademen **{current_tier}** tespit edildi ve rolün güncellendi!",
                    color=0x00FF00
                )
                await loading.edit(content=None, embed=embed)
            except discord.Forbidden:
                await loading.edit(content="❌ Yetersiz yetki! Botun 'Rolleri Yönet' yetkisine ve rol sıralamasında üst sırada olması gerekiyor.")

    # --- DİNAMİK GÜNLÜK ÖDÜL (v!daily) & GERİ SAYIM (<t:Tarih:R>) ---
    @commands.hybrid_command(name="daily", description="Her 24 saatte bir rastgele metinli günlük ödülünü alırsın.")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_command(self, ctx):
        user_id = str(ctx.author.id)
        economy_data = SafeDatabase.load_json("vtracker_economy.json")
        user_eco = economy_data.setdefault(user_id, {"balance": 1000, "last_daily": 0})

        now = int(time.time())
        cooldown_time = 86400

        if now - user_eco["last_daily"] < cooldown_time:
            next_available = user_eco["last_daily"] + cooldown_time
            embed = discord.Embed(
                title="⏳ Günlük Ödül Bekleme Süresi",
                description=f"Günlük lojistik desteğini zaten aldın!\nTekrar alabileceğin zaman: **<t:{next_available}:R>** (<t:{next_available}:F>)",
                color=0xFFA500
            )
            return await ctx.send(embed=embed)

        reward = random.randint(400, 600)
        user_eco["balance"] += reward
        user_eco["last_daily"] = now

        await SafeDatabase.save_json("vtracker_economy.json", economy_data)

        flavor_text = random.choice(self.daily_flavor_texts)
        embed = discord.Embed(
            title="🎁 Günlük Taktiksel Ödül",
            description=f"{flavor_text}\n\nCüzdanına eklenen miktar: **+{reward:,} V-Coin**",
            color=0x00FF00
        )
        embed.set_footer(text="V-Tracker.gg • Dinamik Ekonomi Sistemi")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdvancedFeatures(bot))
    logger.info("Gelişmiş Özellikler (AdvancedFeatures) başarıyla yüklendi!")