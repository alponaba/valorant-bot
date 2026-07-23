# -*- coding: utf-8 -*-
"""
V-Tracker.gg - PUUID Odaklı Kesin Çözüm ve Kararlı İstatistik Modülü
Modül: cogs.stats
Sürüm: 4.7.1-PUUID-Final
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
FALLBACK_API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"


# =====================================================================
# 2. VERİTABANI VE ÖNBELLEK YÖNETİCİSİ
# =====================================================================

class DatabaseManager:
    @staticmethod
    def load_users() -> Dict[str, Any]:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except Exception:
                return {}
        return {}

    @staticmethod
    def get_user_balance(discord_id: str) -> int:
        db = DatabaseManager.load_users()
        user_data = db.get(str(discord_id))
        if user_data and isinstance(user_data, dict):
            return user_data.get("v_coins", 0)
        return 0


class APICacheManager:
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
# 3. VALORANT API İSTEMCİSİ (PUUID TABANLI KESİN ÇÖZÜM)
# =====================================================================

class ValorantAPIClient:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.primary_base = "https://api.henrikdev.xyz"
        self.cache = APICacheManager(ttl_seconds=300)

    @property
    def api_key(self) -> str:
        return getattr(self.bot, "henrik_api_key", FALLBACK_API_KEY)

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "V-Tracker-Bot/4.7.1"}
        key = self.api_key
        if key:
            headers["Authorization"] = key
        return headers

    async def _safe_get(self, session: aiohttp.ClientSession, url: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        headers = self.get_headers()
        logger.info(f"API İstek Gönderiliyor -> URL: {url}")
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                status = response.status
                text = await response.text()
                
                if status == 429:
                    logger.warning("Rate limit aşıldı, bekleniyor...")
                    await asyncio.sleep(2.0)
                    return status, None

                if status == 200:
                    try:
                        return status, json.loads(text)
                    except json.JSONDecodeError:
                        return 500, None
                else:
                    logger.warning(f"API Durum Kodu: {status} | Yanıt: {text[:200]}")
                    return status, None
        except Exception as e:
            logger.error(f"API İstek Hatası: {e}")
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
                    "name": acc_data.get("name", name),
                    "tag": acc_data.get("tag", tag),
                    "success": True
                }
                self.cache.set(cache_key, result)
                return result

        return {"puuid": None, "region": "eu", "account_level": 0, "card": {}, "name": name, "tag": tag, "success": False}

    async def get_mmr(self, session: aiohttp.ClientSession, region: str, puuid: str) -> Dict[str, Any]:
        cache_key = f"mmr_{region}_{puuid}".lower()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        target_regions = list(dict.fromkeys([region, "tr", "eu"]))
        for reg in target_regions:
            url = f"{self.primary_base}/val/v2/by-puuid/mmr/{reg}/{puuid}"
            status, data = await self._safe_get(session, url)
            if status == 200 and data:
                d = data.get("data", {})
                if d:
                    current_data = d.get("current_data", {})
                    tier = current_data.get("currenttierpatched") or d.get("currenttierpatched") or "Unranked"
                    rr = current_data.get("ranking_in_tier", 0)
                    elo = current_data.get("elo", 0)
                    result = {"tier": tier, "rr": rr, "elo": elo, "region": reg, "success": True}
                    self.cache.set(cache_key, result)
                    return result

        return {"tier": "Unranked", "rr": 0, "elo": 0, "region": region, "success": False}

    async def get_matches(self, session: aiohttp.ClientSession, region: str, puuid: str) -> Dict[str, Any]:
        cache_key = f"matches_{region}_{puuid}".lower()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        target_regions = list(dict.fromkeys([region, "tr", "eu"]))
        for reg in target_regions:
            url = f"{self.primary_base}/val/v3/by-puuid/matches/{reg}/{puuid}"
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
    @staticmethod
    def analyze_player(matches: List[Dict[str, Any]], puuid: str) -> Dict[str, Any]:
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
                if p.get("puuid") == puuid:
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
# 5. ETKİLEŞİMLİ ARAYÜZ (VIEWS)
# =====================================================================

class ProfilePagingView(discord.ui.View):
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
            await interaction.response.send_message("Sadece komutu kullanan kişi değiştirebilir.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Sonraki ▶", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Sadece komutu kullanan kişi değiştirebilir.", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


# =====================================================================
# 6. ANA COG
# =====================================================================

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_client = ValorantAPIClient(bot)
        self.embed_color = 0x00F0FF

    @commands.command(name="stats", aliases=["istatistik", "stat"])
    async def stats(self, ctx, *, target_user: Optional[str] = None):
        if not target_user or "#" not in target_user:
            await ctx.send("Lütfen geçerli bir Riot ID girin! Örnek: `v!stats İsim#Tag`")
            return

        name_part, tag_part = target_user.split("#", 1)
        name = name_part.strip()
        tag = tag_part.strip().split()[0][:6]

        loading_embed = discord.Embed(
            title="PUUID ve Hesap Bilgileri Çekiliyor...",
            description=f"**{name}#{tag}** için Riot sunucularına bağlanılıyor...",
            color=self.embed_color
        )
        loading_msg = await ctx.send(embed=loading_embed)

        async with aiohttp.ClientSession() as session:
            account_res = await self.api_client.get_account(session, name, tag)
            if not account_res.get("success") or not account_res.get("puuid"):
                await loading_msg.edit(content=f"**{name}#{tag}** adında bir oyuncu bulunamadı veya API anahtarı bekleniyor.")
                return

            puuid = account_res["puuid"]
            region = account_res["region"]
            account_level = account_res["account_level"]
            card_info = account_res["card"]
            real_name = account_res["name"]
            real_tag = account_res["tag"]

            mmr_res = await self.api_client.get_mmr(session, region, puuid)
            tier = mmr_res.get("tier", "Unranked")
            rr = mmr_res.get("rr", 0)
            elo = mmr_res.get("elo", 0)

            match_res = await self.api_client.get_matches(session, region, puuid)
            matches = match_res.get("matches", [])

        metrics = StatisticsAnalyzer.analyze_player(matches, puuid)
        v_coins = DatabaseManager.get_user_balance(str(ctx.author.id))

        page_one = discord.Embed(
            title=f"OYUNCU PROFİLİ | {real_name}#{real_tag}",
            description=f"**PUUID:** `{puuid[:12]}...`\n**Bölge:** `{region.upper()}` | **Seviye:** `{account_level}`",
            color=self.embed_color,
            timestamp=datetime.utcnow()
        )

        if card_info.get("small"):
            page_one.set_thumbnail(url=card_info.get("small"))
        if card_info.get("large"):
            page_one.set_image(url=card_info.get("large"))

        page_one.add_field(
            name="Rekabetçi Bilgileri",
            value=f"• **Güncel Rank:** `{tier}`\n• **Kadem Puanı (RR):** `{rr} RR`\n• **ELO:** `{elo}`",
            inline=False
        )

        page_one.add_field(
            name="Son Maç Performans Özeti",
            value=(
                f"• **İncelenen Maç Sayısı:** `{metrics['matches_analyzed']}`\n"
                f"• **En Çok Oynanan Ajan:** `{metrics['main_agent']}`\n"
                f"• **Ortalama K/D:** `{metrics['avg_kd']}`\n"
                f"• **Ortalama K / D / A:** `{metrics['avg_kills']} / {metrics['avg_deaths']} / {metrics['avg_assists']}`\n"
                f"• **Ortalama Skor:** `{metrics['avg_score']}`"
            ),
            inline=False
        )

        if v_coins > 0:
            page_one.add_field(name="Cüzdan Bakiyesi", value=f"• **V-Coin:** `{v_coins}`", inline=False)

        page_one.set_footer(text=f"V-Tracker.gg • PUUID Tabanlı Kesin Sistem • {ctx.author}", icon_url=ctx.author.display_avatar.url)

        page_two = discord.Embed(
            title=f"DETAYLI SAVAŞ ANALİZİ | {real_name}#{real_tag}",
            description=f"Son `{metrics['matches_analyzed']}` maçın PUUID tabanlı dökümü:",
            color=self.embed_color,
            timestamp=datetime.utcnow()
        )
        if card_info.get("small"):
            page_two.set_thumbnail(url=card_info.get("small"))

        page_two.add_field(
            name="Toplam Çatışma Verileri",
            value=(
                f"• **Toplam Kill:** `{metrics['total_kills']}`\n"
                f"• **Toplam Death:** `{metrics['total_deaths']}`\n"
                f"• **Toplam Asist:** `{metrics['total_assists']}`\n"
                f"• **Genel K/D:** `{(metrics['total_kills'] / max(1, metrics['total_deaths'])):.2f}`"
            ),
            inline=False
        )
        page_two.set_footer(text="V-Tracker.gg • Sayfa 2/2")

        pages = [page_one, page_two]
        try:
            view = ProfilePagingView(ctx, pages)
            msg = await loading_msg.edit(content=None, embed=page_one, view=view)
            view.message = msg
        except Exception:
            await ctx.send(embed=page_one)


async def setup(bot):
    await bot.add_cog(Stats(bot))
    logger.info("Stats Cog (PUUID Kesin Sürüm) yüklendi.")