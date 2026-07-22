# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Gelişmiş Valorant İstatistik ve Oyuncu Profili Sistemi
Modül: cogs.stats
Açıklama: Görsel formatı koruyan, sıfır hata toleranslı ve tam veri çekme sürümü.
Sürüm: 4.4.0-Enterprise
"""

import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
import logging
import asyncio
from datetime import datetime, timedelta
from collections import Counter
from typing import Dict, Any, Optional, List, Tuple

# =====================================================================
# 1. LOGLAMA VE SİSTEM YAPILANDIRMASI
# =====================================================================

logger = logging.getLogger("VTracker.StatsEngine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

DATA_FILE = "registered_users.json"
FALLBACK_API_KEY = "HDEv-e534fbfe-c3c4-4f21-bccc-54eeeb39fd27"


# =====================================================================
# 2. VERİTABANI VE ÖNBELLEK (CACHE) YÖNETİCİSİ
# =====================================================================

class DatabaseManager:
    """JSON tabanlı kullanıcı veritabanını güvenli bir şekilde yöneten sınıf."""
    
    @staticmethod
    def load_users() -> Dict[str, Any]:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError as jde:
                logger.error(f"Veritabanı JSON ayrıştırma hatası: {jde}")
                return {}
            except Exception as e:
                logger.error(f"Veritabanı okuma hatası: {e}")
                return {}
        return {}

    @staticmethod
    def save_users(data: Dict[str, Any]) -> None:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Veritabanı yazma hatası: {e}")

    @staticmethod
    def get_user_riot_id(discord_id: str) -> Optional[str]:
        db = DatabaseManager.load_users()
        user_data = db.get(str(discord_id))
        if user_data and isinstance(user_data, dict):
            return user_data.get("riot_id")
        return None

    @staticmethod
    def get_user_balance(discord_id: str) -> int:
        db = DatabaseManager.load_users()
        user_data = db.get(str(discord_id))
        if user_data and isinstance(user_data, dict):
            return user_data.get("v_coins", 0)
        return 0


class APICacheManager:
    """HTTP 429 hatalarını önlemek için bellek içi önbellekleme mekanizması."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Tuple[datetime, Any]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            timestamp, data = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key: str, data: Any) -> None:
        self.cache[key] = (datetime.now(), data)


# =====================================================================
# 3. VALORANT API İSTEMCİSİ (GÜNCELLENMİŞ JSON PARSER)
# =====================================================================

class ValorantAPIClient:
    """Henrik Dev API ile iletişim kuran ve verileri doğru node'lardan alan istemci."""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.primary_base = "https://api.henrikdev.xyz"
        self.cache = APICacheManager(ttl_seconds=300)

    @property
    def api_key(self) -> str:
        return getattr(self.bot, "henrik_api_key", FALLBACK_API_KEY)

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "V-Tracker-Bot/4.4.0"}
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    async def _safe_get(self, session: aiohttp.ClientSession, url: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        headers = self.get_headers()
        logger.info(f"API İstek Gönderiliyor -> URL: {url}")
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                status = response.status
                text = await response.text()
                
                if status == 429:
                    logger.warning(f"⚠️ RATE LIMIT (429) AŞILDI! Bekleniyor: {url}")
                    await asyncio.sleep(2.0)
                    return status, None

                if status == 200:
                    try:
                        data = json.loads(text)
                        return status, data
                    except json.JSONDecodeError:
                        return 500, None
                else:
                    return status, None
        except Exception as e:
            logger.error(f"API İstek İstisnası: {e}")
            return 500, None

    async def get_account(self, session: aiohttp.ClientSession, name: str, tag: str) -> Dict[str, Any]:
        cache_key = f"account_{name}_{tag}".lower()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        
        url = f"{self.primary_base}/riot/v1/account/{encoded_name}/{encoded_tag}"
        status, data = await self._safe_get(session, url)
        
        if status == 200 and data:
            acc_data = data.get("data", {})
            if acc_data and acc_data.get("puuid"):
                result = {
                    "puuid": acc_data.get("puuid"),
                    "region": (acc_data.get("region") or "eu").lower(),
                    "account_level": acc_data.get("account_level", 0),
                    "card": acc_data.get("card", {}),
                    "success": True
                }
                self.cache.set(cache_key, result)
                return result

        return {"puuid": None, "region": "eu", "account_level": 0, "card": {}, "success": False}

    async def get_mmr(self, session: aiohttp.ClientSession, region: str, puuid: Optional[str], name: str, tag: str) -> Dict[str, Any]:
        cache_key = f"mmr_{region}_{puuid or f'{name}_{tag}'}".lower()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        target_regions = list(dict.fromkeys([region, "tr", "eu"]))

        for reg in target_regions:
            url = f"{self.primary_base}/val/v2/by-puuid/mmr/{reg}/{puuid}" if puuid else f"{self.primary_base}/val/v2/mmr/{reg}/{encoded_name}/{encoded_tag}"
            
            status, data = await self._safe_get(session, url)
            if status == 200 and data:
                d = data.get("data", {})
                if d:
                    # Henrik API v2 MMR yapısı kontrolü (current_data veya direkt root)
                    current_data = d.get("current_data", {})
                    tier = current_data.get("currenttierpatched") or d.get("currenttierpatched") or d.get("currenttier")
                    rr = current_data.get("ranking_in_tier") if current_data.get("ranking_in_tier") is not None else d.get("ranking_in_tier", 0)
                    elo = current_data.get("elo") if current_data.get("elo") is not None else d.get("elo", 0)
                    
                    result = {
                        "tier": tier if tier else "Unranked",
                        "rr": rr if rr is not None else 0,
                        "elo": elo if elo is not None else 0,
                        "region": reg,
                        "success": True
                    }
                    self.cache.set(cache_key, result)
                    return result

        return {"tier": "Unranked", "rr": 0, "elo": 0, "region": region, "success": False}

    async def get_matches(self, session: aiohttp.ClientSession, region: str, puuid: Optional[str], name: str, tag: str) -> Dict[str, Any]:
        cache_key = f"matches_{region}_{puuid or f'{name}_{tag}'}".lower()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        target_regions = list(dict.fromkeys([region, "tr", "eu"]))

        for reg in target_regions:
            url = f"{self.primary_base}/val/v3/by-puuid/matches/{reg}/{puuid}" if puuid else f"{self.primary_base}/val/v3/matches/{reg}/pc/{encoded_name}/{encoded_tag}"
            
            status, data = await self._safe_get(session, url)
            if status == 200 and data:
                matches = []
                raw_data = data.get("data", [])
                if isinstance(raw_data, list):
                    matches = raw_data
                elif isinstance(raw_data, dict):
                    matches = raw_data.get("matches", [])

                if matches:
                    result = {"matches": matches, "region": reg, "success": True}
                    self.cache.set(cache_key, result)
                    return result

        return {"matches": [], "region": region, "success": False}


# =====================================================================
# 4. İSTATİSTİK ANALİZ MOTORU
# =====================================================================

class StatisticsAnalyzer:
    """Maç verilerini işleyerek doğru istatistiksel metrikleri çıkaran sınıf."""
    
    @staticmethod
    def analyze_player(matches: List[Dict[str, Any]], puuid: Optional[str], name: str, tag: str) -> Dict[str, Any]:
        agents_played = []
        total_kills = 0
        total_deaths = 0
        total_assists = 0
        total_score = 0
        matches_count = len(matches)

        for match in matches:
            players_section = match.get("players", {})
            players_list = players_section.get("all_players", [])
            
            for p in players_list:
                is_target = False
                if puuid and p.get("puuid") == puuid:
                    is_target = True
                elif p.get("name", "").strip().lower() == name.lower() and p.get("tag", "").strip().lower() == tag.lower():
                    is_target = True

                if is_target:
                    agents_played.append(p.get("character", "Bilinmiyor"))
                    stats = p.get("stats", {})
                    total_kills += stats.get("kills", 0)
                    total_deaths += stats.get("deaths", 0)
                    total_assists += stats.get("assists", 0)
                    total_score += stats.get("score", 0)

        main_agent = Counter(agents_played).most_common(1)[0][0] if agents_played else "Bilinmiyor"
        div = matches_count if matches_count > 0 else 1

        avg_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else float(total_kills)
        avg_kills = round(total_kills / div, 1)
        avg_deaths = round(total_deaths / div, 1)
        avg_assists = round(total_assists / div, 1)
        avg_score = round(total_score / div, 1)

        return {
            "matches_analyzed": matches_count,
            "main_agent": main_agent,
            "avg_kd": avg_kd,
            "avg_kills": avg_kills,
            "avg_deaths": avg_deaths,
            "avg_assists": avg_assists,
            "avg_score": avg_score,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "total_assists": total_assists
        }


# =====================================================================
# 5. ETKİLEŞİMLİ DİSCORD ARAYÜZ (VIEWS)
# =====================================================================

class ProfilePagingView(discord.ui.View):
    """Discord mesajı üzerinde sayfa değiştirmeyi sağlayan buton yöneticisi."""
    
    def __init__(self, ctx, embed_pages: List[discord.Embed]):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.pages = embed_pages
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="◀ Önceki", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Bu menüyü yalnızca komutu kullanan kişi kontrol edebilir.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Sonraki ▶", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Bu menüyü yalnızca komutu kullanan kişi kontrol edebilir.", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass


# =====================================================================
# 6. ANA COG (STATS COMMAND MODULE)
# =====================================================================

class Stats(commands.Cog):
    """Valorant Oyuncu İstatistikleri ve Kapsamlı Profil Modülü."""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_client = ValorantAPIClient(bot)
        self.embed_color = 0x00F0FF  # Cyan / Turkuaz

    def format_rank(self, tier: str) -> str:
        if not tier or tier.lower() == "unranked":
            return "Unranked ⚪"
        return tier

    @commands.command(name="stats", aliases=["istatistik", "stat"])
    async def stats(self, ctx, *, target_user: Optional[str] = None):
        """Oyuncunun Valorant istatistiklerini kusursuz formatta getirir."""
        discord_id = str(ctx.author.id)
        riot_id = ""
        v_coins = 0

        if target_user:
            if "#" not in target_user:
                await ctx.send("❌ Hatalı Riot ID formatı! Örnek: `v!stats İsim#Tag`")
                return
            riot_id = target_user.strip()
            v_coins = DatabaseManager.get_user_balance(discord_id)
        else:
            saved_id = DatabaseManager.get_user_riot_id(discord_id)
            if not saved_id:
                embed_err = discord.Embed(
                    title="❌ Kayıt Bulunamadı",
                    description=(
                        "Sistemde kayıtlı Riot ID'niz bulunamadı.\n"
                        "Doğrudan aratmak için: `v!stats İsim#Tag`\n"
                        "Kalıcı kayıt olmak için: `v!register İsim#Tag`"
                    ),
                    color=0xFF0033
                )
                await ctx.send(embed=embed_err)
                return
            riot_id = saved_id
            v_coins = DatabaseManager.get_user_balance(discord_id)

        if "#" not in riot_id:
            await ctx.send("❌ Geçerli bir Riot ID formatı doğrulanamadı.")
            return

        name, tag = riot_id.split("#", 1)
        name = name.strip()
        tag = tag.strip()

        loading_embed = discord.Embed(
            title="🔍 Riot Games Verileri Taranıyor...",
            description=f"**{name}#{tag}** hesabı sorgulanıyor, lütfen bekleyin...",
            color=self.embed_color
        )
        loading_msg = await ctx.send(embed=loading_embed)

        async with aiohttp.ClientSession() as session:
            account_res = await self.api_client.get_account(session, name, tag)
            puuid = account_res.get("puuid")
            initial_region = account_res.get("region", "eu")
            account_level = account_res.get("account_level", 0)
            card_info = account_res.get("card", {})
            large_card_url = card_info.get("large")
            small_icon_url = card_info.get("small")

            mmr_res = await self.api_client.get_mmr(session, initial_region, puuid, name, tag)
            tier = mmr_res.get("tier", "Unranked")
            rr = mmr_res.get("rr", 0)
            elo = mmr_res.get("elo", 0)
            region = mmr_res.get("region", initial_region)

            match_res = await self.api_client.get_matches(session, region, puuid, name, tag)
            matches = match_res.get("matches", [])

        metrics = StatisticsAnalyzer.analyze_player(matches, puuid, name, tag)

        page_one = discord.Embed(
            title=f"👤 OYUNCU PROFİLİ | {name}#{tag}",
            description=f"🌍 **Bölge:** `{region.upper()}` | 🎖️ **Seviye:** `{account_level}`",
            color=self.embed_color,
            timestamp=datetime.utcnow()
        )

        if small_icon_url:
            page_one.set_thumbnail(url=small_icon_url)
        if large_card_url:
            page_one.set_image(url=large_card_url)

        page_one.add_field(
            name="🏆 Rekabetçi Bilgileri",
            value=(
                f"• **Güncel Rank:** `{self.format_rank(tier)}`\n"
                f"• **Kadem Puanı (RR):** `{rr} RR`\n"
                f"• **ELO Puanı:** `{elo}`"
            ),
            inline=False
        )

        page_one.add_field(
            name="📊 Son Maç Performans Özeti",
            value=(
                f"• **İncelenen Maç Sayısı:** `{metrics['matches_analyzed']}`\n"
                f"• **En Çok Oynanan Ajan:** `{metrics['main_agent']}`\n"
                f"• **Ortalama K/D Oranı:** `{metrics['avg_kd']}`\n"
                f"• **Maç Başı K / D / A:** `{metrics['avg_kills']} / {metrics['avg_deaths']} / {metrics['avg_assists']}`\n"
                f"• **Maç Başı Skor:** `{metrics['avg_score']}`"
            ),
            inline=False
        )

        if v_coins > 0:
            page_one.add_field(
                name="🪙 Cüzdan Bakiyesi",
                value=f"• **V-Coin:** `{v_coins}`",
                inline=False
            )

        page_one.set_footer(
            text=f"V-Tracker.gg • Kurumsal İstatistik Altyapısı • İsteyen: {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        page_two = discord.Embed(
            title=f"📈 DETAYLI SAVAŞ ANALİZİ | {name}#{tag}",
            description=f"Son `{metrics['matches_analyzed']}` karşılaşmanın döküm raporu:",
            color=self.embed_color,
            timestamp=datetime.utcnow()
        )
        if small_icon_url:
            page_two.set_thumbnail(url=small_icon_url)

        page_two.add_field(
            name="⚔️ Toplam Çatışma Verileri",
            value=(
                f"• **Toplam Alınan Skor (Kill):** `{metrics['total_kills']}`\n"
                f"• **Toplam Ölüm (Death):** `{metrics['total_deaths']}`\n"
                f"• **Toplam Asist:** `{metrics['total_assists']}`\n"
                f"• **Genel Başarı Oranı:** `{(metrics['total_kills'] / max(1, metrics['total_deaths'])):.2f} K/D`"
            ),
            inline=False
        )
        page_two.set_footer(text=f"V-Tracker.gg • Sayfa 2/2")

        pages = [page_one, page_two]

        try:
            await loading_msg.edit(content=None, embed=page_one, view=ProfilePagingView(ctx, pages))
        except discord.HTTPException:
            await ctx.send(embed=page_one)

    @commands.command(name="reloadstats", hidden=True)
    @commands.is_owner()
    async def reloadstats(self, ctx):
        await ctx.send("🔄 Stats modülü güncellendi ve önbellekler yenilendi.")


async def setup(bot):
    await bot.add_cog(Stats(bot))
    logger.info("Stats Cog (Enterprise Kararlı Sürüm) başarıyla yüklendi.")