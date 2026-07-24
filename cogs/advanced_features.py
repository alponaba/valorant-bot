# -*- coding: utf-8 -*-

import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os
import time
import random
import re
import logging
from datetime import datetime

logger = logging.getLogger("V-Tracker-Features")

# =====================================================================
# 1. GÜVENLİK VE VERİTABANI KATMANI (Concurrent Write Lock & Sanitization)
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

def is_safe_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url_pattern = re.compile(r'^https?://[^\s<>"]+|www\.[^\s<>"]+$', re.IGNORECASE)
    if not url_pattern.match(url):
        return False
    dangerous_keywords = ["javascript:", "data:", "vbscript:", "onload=", "onerror="]
    return not any(keyword in url.lower() for keyword in dangerous_keywords)

# =====================================================================
# 2. API TTL CACHE & RETRY MOTORU
# =====================================================================
class CachedRiotAPI:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 Dakika Cache
        self.headers = {"User-Agent": "V-Tracker-Bot/2.5"}

    async def _fetch_with_retry(self, session: aiohttp.ClientSession, url: str):
        now = time.time()
        if url in self.cache:
            data, timestamp = self.cache[url]
            if now - timestamp < self.cache_ttl:
                return data

        for attempt in range(3):
            try:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        self.cache[url] = (res_data, now)
                        return res_data
                    elif resp.status == 429:
                        await asyncio.sleep(2 * (attempt + 1))
                    else:
                        break
            except Exception as e:
                logger.warning(f"API Hatası ({attempt+1}/3): {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(1.5)
        return None

    async def get_mmr(self, session: aiohttp.ClientSession, region: str, puuid: str):
        url = f"https://api.henrikdev.xyz/valorant/v2/mmr/{region}/by-puuid/{puuid}"
        return await self._fetch_with_retry(session, url)

    async def get_matches(self, session: aiohttp.ClientSession, region: str, puuid: str, size: int = 5):
        url = f"https://api.henrikdev.xyz/valorant/v3/by-puuid/matches/{region}/{puuid}?size={size}"
        return await self._fetch_with_retry(session, url)

# =====================================================================
# 3. YARDIMCI ANALİZ MOTORLARI (Unvanlar & Akıllı Koç)
# =====================================================================
class BadgeEngine:
    @staticmethod
    def get_badges(kd: float, hs_rate: float, main_agent: str) -> list:
        badges = []
        if hs_rate >= 25.0:
            badges.append("💥 Kafa Avcısı")
        elif hs_rate >= 18.0:
            badges.append("👁️ Keskin Göz")

        if kd >= 1.3:
            badges.append("🔥 Frag Makinesi")
        elif kd >= 1.0:
            badges.append("⚔️ İstikrarlı Savaşçı")

        agent_titles = {
            "Omen": "👤 Gölge Ustası",
            "Jett": "🌪️ Rüzgarın Oğlu",
            "Reyna": "👑 İmparatoriçe",
            "Raze": "💣 Patlama Uzmanı",
            "Sova": "🏹 Avcı",
            "Viper": "🧪 Zehir Kraliçesi",
            "Chamber": "💼 Şık Ajan",
            "Fade": "👁️ Kabus Efendisi"
        }
        if main_agent in agent_titles:
            badges.append(agent_titles[main_agent])

        return badges if badges else ["🔰 Çaylak Ajan"]

class CoachEngine:
    @staticmethod
    def generate_tip(stats: dict) -> str:
        kd = stats.get("kd", 1.0)
        hs = stats.get("hs_rate", 15.0)
        adr = stats.get("adr", 100)

        tips = []
        if hs < 18.0:
            tips.append(f"💡 **Crosshair Hizalaması:** Headshot oranın %{hs}. Nişangahını her zaman düşman kafa hizasında tutmaya özen göster!")
        if kd < 1.0:
            tips.append(f"💡 **Pozisyon Alma:** K/D oranın {kd}. İlk kanı vermemek için raund başlarında daha sabırlı ve takımla dar açı tut.")
        if adr < 120:
            tips.append(f"💡 **Hasar Katkısı:** Raund başı ortalama damage'in {adr}. Utility (yetenek) kullanımını artırarak çatışmalara destek ol.")

        if not tips:
            tips.append("🌟 **Harika Form!** İstatistiklerin çok dengeli ve yüksek. Bu odakla oynamaya devam et!")

        return random.choice(tips)

# =====================================================================
# 4. GELİŞMİŞ ÖZELLİKLER COG
# =====================================================================
class AdvancedFeatures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.riot_api = CachedRiotAPI()

        self.color_shop = {
            "kirmizi": {"hex": 0xFF4655, "name": "Valorant Kırmızı (Varsayılan)", "price": 0},
            "yesil": {"hex": 0x39FF14, "name": "Neon Yeşil", "price": 2500},
            "mor": {"hex": 0x9B59B6, "name": "Gece Moru", "price": 2500},
            "altin": {"hex": 0xFFD700, "name": "Altın Sarısı", "price": 5000},
            "mavi": {"hex": 0x00FFFF, "name": "Siber Mavi", "price": 2500}
        }

        self.daily_flavor_texts = [
            "🚀 Operasyon masasından günlük lojistik desteğin alındı komutan!",
            "⚡ Ajan kasana taktiksel V-Coin bütçesi aktarıldı, iyi harcamalar!",
            "🎯 Hedef vuruldu! Günlük ödülün başarıyla hesabına tanımlandı."
        ]
        self.weekly_flavor_texts = [
            "🏆 Haftalık büyük operasyon bonusu cüzdanına eklendi!",
            "🌟 Haftanın zafer ödülü hesabına aktarıldı, zirveye oynamaya devam et!"
        ]

    # --- MERKEZİ COOLDOWN HATA YÖNETİMİ ---
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

    # --- 1. OTOMATİK SUNUCU ROLLERİ (v!updateroles) ---
    @commands.hybrid_command(name="updateroles", description="Güncel Valorant kademene göre sunucu rolünü otomatik günceller.")
    async def updateroles_command(self, ctx):
        user_id = str(ctx.author.id)
        users_data = SafeDatabase.load_json("vtracker_users.json")
        user_info = users_data.get(user_id)

        if not user_info:
            return await ctx.send("❌ Önce `v!kayit İsim#Tag` komutuyla hesabını bağlamalısın!")

        loading = await ctx.send("🔄 Güncel Valorant kademen sorgulanıyor...")
        async with aiohttp.ClientSession() as session:
            mmr_data = await self.riot_api.get_mmr(session, user_info["region"], user_info["puuid"])

            if not mmr_data or "data" not in mmr_data:
                return await loading.edit(content="❌ Kademe verisi alınamadı. API yanıt vermiyor.")

            current_tier = mmr_data["data"].get("currenttierpatched")
            if not current_tier:
                return await loading.edit(content="❌ Aktif bir rekabetçi kademen bulunamadı.")

            guild_role = discord.utils.get(ctx.guild.roles, name=current_tier)
            if not guild_role:
                return await loading.edit(content=f"⚠️ `{current_tier}` kademen bulundu ancak sunucuda bu isimde bir rol (**{current_tier}**) açılmamış.")

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
                await loading.edit(content="❌ Yetersiz yetki! Botun 'Rolleri Yönet' yetkisini kontrol edin.")

    # --- 2. DİNAMİK GÜNLÜK VE HAFTALIK ÖDÜLLER (v!daily / v!weekly) ---
    @commands.hybrid_command(name="daily", description="Her 24 saatte bir taktiksel günlük ödülünü alırsın.")
    async def daily_command(self, ctx):
        user_id = str(ctx.author.id)
        economy_data = SafeDatabase.load_json("vtracker_economy.json")
        user_eco = economy_data.setdefault(user_id, {"balance": 1000, "last_daily": 0, "last_weekly": 0})

        now = int(time.time())
        if now - user_eco.get("last_daily", 0) < 86400:
            next_available = user_eco["last_daily"] + 86400
            embed = discord.Embed(
                title="⏳ Günlük Ödül Bekleme Süresi",
                description=f"Ödülünü zaten aldın! Tekrar alabileceğin zaman: **<t:{next_available}:R>**",
                color=0xFFA500
            )
            return await ctx.send(embed=embed)

        reward = random.randint(400, 600)
        user_eco["balance"] += reward
        user_eco["last_daily"] = now
        await SafeDatabase.save_json("vtracker_economy.json", economy_data)

        embed = discord.Embed(
            title="🎁 Günlük Taktiksel Ödül",
            description=f"{random.choice(self.daily_flavor_texts)}\n\nCüzdanına eklendi: **+{reward:,} V-Coin**",
            color=0x00FF00
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="weekly", description="Her 7 günde bir büyük haftalık ödülünü alırsın.")
    async def weekly_command(self, ctx):
        user_id = str(ctx.author.id)
        economy_data = SafeDatabase.load_json("vtracker_economy.json")
        user_eco = economy_data.setdefault(user_id, {"balance": 1000, "last_daily": 0, "last_weekly": 0})

        now = int(time.time())
        if now - user_eco.get("last_weekly", 0) < 604800:
            next_available = user_eco["last_weekly"] + 604800
            embed = discord.Embed(
                title="⏳ Haftalık Ödül Bekleme Süresi",
                description=f"Haftalık ödülünü zaten aldın! Tekrar alabileceğin zaman: **<t:{next_available}:R>**",
                color=0xFFA500
            )
            return await ctx.send(embed=embed)

        reward = random.randint(2500, 3500)
        user_eco["balance"] += reward
        user_eco["last_weekly"] = now
        await SafeDatabase.save_json("vtracker_economy.json", economy_data)

        embed = discord.Embed(
            title="🎁 Haftalık Büyük Ödül",
            description=f"{random.choice(self.weekly_flavor_texts)}\n\nCüzdanına eklendi: **+{reward:,} V-Coin**",
            color=0x00FF00
        )
        await ctx.send(embed=embed)

    # --- 3. HIZLI SON MAÇ ÖZETİ (v!lastmatch) ---
    @commands.hybrid_command(name="lastmatch", aliases=["sonmac"], description="En son oynadığın tek maçın hızlı özetini gösterir.")
    async def lastmatch_command(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        users_data = SafeDatabase.load_json("vtracker_users.json")
        user_info = users_data.get(str(target.id))

        if not user_info:
            return await ctx.send(f"❌ {target.display_name} kayıtlı değil! Önce `v!kayit İsim#Tag` olmalı.")

        loading = await ctx.send("⚡ Son maç detayları çekiliyor...")
        async with aiohttp.ClientSession() as session:
            matches_data = await self.riot_api.get_matches(session, user_info["region"], user_info["puuid"], size=1)

            if not matches_data or "data" not in matches_data or len(matches_data["data"]) == 0:
                return await loading.edit(content="❌ Maç verisi bulunamadı veya API yanıt vermiyor.")

            match = matches_data["data"][0]
            players = match.get("players", {}).get("all_players", [])
            p_data = next((p for p in players if p.get("puuid") == user_info["puuid"]), None)

            if not p_data:
                return await loading.edit(content="❌ Maç verilerinde oyuncu bilgisi okunamadı.")

            stats = p_data.get("stats", {})
            kills = stats.get("kills", 0)
            deaths = stats.get("deaths", 1)
            assists = stats.get("assists", 0)
            agent = p_data.get("character", "Bilinmeyen")
            map_name = match.get("metadata", {}).get("map", "Bilinmeyen Harita")

            # Galibiyet / Mağlubiyet Durumu
            team = p_data.get("team", "").lower()
            teams = match.get("teams", {})
            won = False
            if teams and team in teams:
                won = teams[team].get("won", False)

            color = 0x00FF00 if won else 0xFF0000
            status_text = "🏆 ZAFER" if won else "❌ BOZGUM"

            shots = p_data.get("damage_stats", {})
            total_shots = shots.get("headshots", 0) + shots.get("bodyshots", 0) + shots.get("legshots", 0)
            hs_rate = round((shots.get("headshots", 0) / max(1, total_shots)) * 100, 1)

            embed = discord.Embed(
                title=f"{status_text} — {map_name} ({agent})",
                description=f"**{user_info['name']}#{user_info['tag']}** - Son Maç Performansı",
                color=color,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="⚔️ K / D / A", value=f"`{kills} / {deaths} / {assists}`", inline=True)
            embed.add_field(name="🎯 HS Oranı", value=f"`%{hs_rate}`", inline=True)
            embed.add_field(name="📊 K/D Ratio", value=f"`{round(kills/max(1, deaths), 2)}`", inline=True)
            embed.set_footer(text="V-Tracker.gg • Hızlı Son Maç Analizi")

            await loading.edit(content=None, embed=embed)

    # --- 4. VS / DÜELLO MODU (v!vs @Oyuncu) ---
    @commands.hybrid_command(name="vs", description="Başka bir oyuncu ile istatistiklerini kıyaslar.")
    async def vs_command(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send("❌ Kendinle kıyaslama yapamazsın!")

        users_data = SafeDatabase.load_json("vtracker_users.json")
        p1_info = users_data.get(str(ctx.author.id))
        p2_info = users_data.get(str(member.id))

        if not p1_info:
            return await ctx.send("❌ Kıyaslama için önce kendin `v!kayit İsim#Tag` olmalısın!")
        if not p2_info:
            return await ctx.send(f"❌ {member.display_name} sisteme kayıtlı değil!")

        loading = await ctx.send(f"⚔️ **{p1_info['name']}** vs **{p2_info['name']}** düellosu hazırlanıyor...")

        async with aiohttp.ClientSession() as session:
            p1_matches = await self.riot_api.get_matches(session, p1_info["region"], p1_info["puuid"], size=5)
            p2_matches = await self.riot_api.get_matches(session, p2_info["region"], p2_info["puuid"], size=5)

            def calc_simple_stats(data, puuid):
                if not data or "data" not in data:
                    return {"kd": 0.0, "hs": 0.0}
                tot_k, tot_d, hs, tot_s = 0, 0, 0, 0
                for m in data["data"]:
                    p = next((x for x in m.get("players", {}).get("all_players", []) if x.get("puuid") == puuid), None)
                    if p:
                        tot_k += p.get("stats", {}).get("kills", 0)
                        tot_d += p.get("stats", {}).get("deaths", 1)
                        s = p.get("damage_stats", {})
                        hs += s.get("headshots", 0)
                        tot_s += (s.get("headshots", 0) + s.get("bodyshots", 0) + s.get("legshots", 0))
                return {
                    "kd": round(tot_k / max(1, tot_d), 2),
                    "hs": round((hs / max(1, tot_s)) * 100, 1)
                }

            p1_s = calc_simple_stats(p1_matches, p1_info["puuid"])
            p2_s = calc_simple_stats(p2_matches, p2_info["puuid"])

            embed = discord.Embed(
                title=f"⚔️ Valorant Düellosı: {p1_info['name']} vs {p2_info['name']}",
                color=0xFFD700
            )
            embed.add_field(
                name=f"👤 {p1_info['name']}#{p1_info['tag']}",
                value=f"⚖️ **K/D:** `{p1_s['kd']}`\n🎯 **HS:** `%{p1_s['hs']}`",
                inline=True
            )
            embed.add_field(name="⚡ VS", value="🆚", inline=True)
            embed.add_field(
                name=f"👤 {p2_info['name']}#{p2_info['tag']}",
                value=f"⚖️ **K/D:** `{p2_s['kd']}`\n🎯 **HS:** `%{p2_s['hs']}`",
                inline=True
            )
            embed.set_footer(text="V-Tracker.gg • Son 5 Maçlık Düello Analizi")
            await loading.edit(content=None, embed=embed)

    # --- 5. V-COIN ILE OZEL PROFIL RENGI (v!renk) ---
    @commands.hybrid_command(name="renk", description="V-Coin ile /stats ekranın için özel Embed rengi satın alırsın.")
    async def renk_command(self, ctx, secim: str = None):
        user_id = str(ctx.author.id)
        economy = SafeDatabase.load_json("vtracker_economy.json")
        users = SafeDatabase.load_json("vtracker_users.json")

        if str(user_id) not in users:
            return await ctx.send("❌ Önce `v!kayit` olmalısın!")

        user_eco = economy.get(user_id, {"balance": 0})

        if not secim or secim.lower() not in self.color_shop:
            embed = discord.Embed(title="🎨 V-Coin Profil Rengi Mağazası", color=0x00FFFF)
            desc = "Kullanmak/satın almak istediğin rengi yaz: `v!renk <renk_adi>`\n\n"
            for k, v in self.color_shop.items():
                price_text = "Ücretsiz" if v["price"] == 0 else f"{v['price']:,} V-Coin"
                desc += f"• **{k.capitalize()}** — {v['name']} (`{price_text}`)\n"
            embed.description = desc
            return await ctx.send(embed=embed)

        secim = secim.lower()
        color_data = self.color_shop[secim]
        price = color_data["price"]

        if user_eco.get("balance", 0) < price:
            return await ctx.send(f"💸 Yetersiz bakiye! Bu renk `{price:,} V-Coin` değerinde.")

        if price > 0:
            user_eco["balance"] -= price
            await SafeDatabase.save_json("vtracker_economy.json", economy)

        users[user_id]["embed_color"] = color_data["hex"]
        await SafeDatabase.save_json("vtracker_users.json", users)

        await ctx.send(f"🎨 Tebrikler! Stat profil rengin **{color_data['name']}** olarak güncellendi!")

    # --- 6. SUNUCU MVP LIDERLIK PANOSU (v!mvp) ---
    @commands.hybrid_command(name="mvp", description="Sunucunun en zengin ve aktif V-Tracker MVP oyuncularını gösterir.")
    async def mvp_command(self, ctx):
        economy = SafeDatabase.load_json("vtracker_economy.json")
        users = SafeDatabase.load_json("vtracker_users.json")

        if not economy:
            return await ctx.send("❌ Henüz sunucu verisi oluşmadı.")

        sorted_eco = sorted(economy.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:5]

        embed = discord.Embed(
            title="🏆 Haftalık Sunucu MVP & Ekonomi Şampiyonları",
            description="Sunucunun en yüksek V-Coin bakiyesine sahip liderleri:",
            color=0xFFD700
        )

        for idx, (uid, data) in enumerate(sorted_eco, 1):
            u_info = users.get(uid, {})
            riot_title = f" ({u_info['name']}#{u_info['tag']})" if "name" in u_info else ""
            user = self.bot.get_user(int(uid))
            name = user.name if user else f"Ajan ({uid})"

            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
            embed.add_field(
                name=f"{medal} {name}{riot_title}",
                value=f"💰 Bakiyeler: `{data.get('balance', 0):,} VC`",
                inline=False
            )

        embed.set_footer(text="V-Tracker.gg • Haftalık Sunucu Panosu")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdvancedFeatures(bot))
    logger.info("Gelişmiş Özellikler & Analiz Motoru (AdvancedFeatures) başarıyla yüklendi!")