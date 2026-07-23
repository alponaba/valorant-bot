# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Global Database, Kayıt ve PUUID İstatistik Modülü
Modül: cogs.stats
Sürüm: 5.1.0-Global
"""

import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
import logging
import asyncio
from datetime import datetime
from collections import Counter
from typing import Dict, Any, Optional, List, Tuple

# =====================================================================
# 1. LOGLAMA
# =====================================================================

logger = logging.getLogger("VTracker.System")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

GLOBAL_DB_FILE = "global_registered_users.json"
FALLBACK_API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"

# =====================================================================
# 2. KÜRESEL VERİTABANI YÖNETİCİSİ (DISCORD ID -> PUUID)
# =====================================================================

class GlobalDatabase:
    @staticmethod
    def load_db() -> Dict[str, Any]:
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    return json.loads(content) if content else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def save_db(data: Dict[str, Any]) -> None:
        with open(GLOBAL_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def register_user(discord_id: int, puuid: str, name: str, tag: str, region: str) -> None:
        db = GlobalDatabase.load_db()
        db[str(discord_id)] = {
            "puuid": puuid,
            "name": name,
            "tag": tag,
            "region": region,
            "v_coins": db.get(str(discord_id), {}).get("v_coins", 0),
            "updated_at": datetime.utcnow().isoformat()
        }
        GlobalDatabase.save_db(db)

    @staticmethod
    def get_user(discord_id: int) -> Optional[Dict[str, Any]]:
        return GlobalDatabase.load_db().get(str(discord_id))

    @staticmethod
    def get_all_users() -> Dict[str, Any]:
        return GlobalDatabase.load_db()

# =====================================================================
# 3. VALORANT API İSTEMCİSİ (GÜNCELLENMİŞ ROTLAR)
# =====================================================================

class ValorantAPIClient:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.primary_base = "https://api.henrikdev.xyz"

    def get_headers(self) -> Dict[str, str]:
        key = getattr(self.bot, "henrik_api_key", FALLBACK_API_KEY)
        return {"User-Agent": "V-Tracker-Bot/5.1", "Authorization": key}

    async def _safe_get(self, session: aiohttp.ClientSession, url: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        try:
            async with session.get(url, headers=self.get_headers(), timeout=12) as response:
                status = response.status
                if status == 200:
                    return status, await response.json()
                logger.warning(f"API Hata Kodu: {status} | URL: {url}")
                return status, None
        except Exception as e:
            logger.error(f"API İstek Hatası: {e}")
            return 500, None

    async def get_account_by_name(self, session: aiohttp.ClientSession, name: str, tag: str) -> Dict[str, Any]:
        # 404 hatasını çözen düzeltilmiş endpoint: riot/v1 yerine valorant/v1
        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"{self.primary_base}/valorant/v1/account/{encoded_name}/{encoded_tag}"
        
        status, data = await self._safe_get(session, url)
        if status == 200 and data and data.get("data"):
            acc = data["data"]
            return {
                "puuid": acc.get("puuid"),
                "region": (acc.get("region") or "eu").lower(),
                "account_level": acc.get("account_level", 0),
                "card": acc.get("card", {}),
                "name": acc.get("name", name),
                "tag": acc.get("tag", tag),
                "success": True
            }
        return {"success": False}

    async def get_mmr_by_puuid(self, session: aiohttp.ClientSession, region: str, puuid: str) -> Dict[str, Any]:
        # val/v2 yerine valorant/v2
        url = f"{self.primary_base}/valorant/v2/by-puuid/mmr/{region}/{puuid}"
        status, data = await self._safe_get(session, url)
        if status == 200 and data and data.get("data"):
            d = data["data"]
            current = d.get("current_data", {})
            return {
                "tier": current.get("currenttierpatched") or "Unranked",
                "rr": current.get("ranking_in_tier", 0),
                "elo": current.get("elo", 0),
                "success": True
            }
        return {"tier": "Unranked", "rr": 0, "elo": 0, "success": False}

    async def get_matches_by_puuid(self, session: aiohttp.ClientSession, region: str, puuid: str) -> List[Dict[str, Any]]:
        # val/v3 yerine valorant/v3
        url = f"{self.primary_base}/valorant/v3/by-puuid/matches/{region}/{puuid}"
        status, data = await self._safe_get(session, url)
        if status == 200 and data:
            raw_data = data.get("data", [])
            if isinstance(raw_data, list): return raw_data
            if isinstance(raw_data, dict): return raw_data.get("matches", [])
        return []

# =====================================================================
# 4. İSTATİSTİK ANALİZ MOTORU
# =====================================================================

class StatisticsAnalyzer:
    @staticmethod
    def analyze_player(matches: List[Dict[str, Any]], puuid: str) -> Dict[str, Any]:
        agents, kills, deaths, assists, score = [], 0, 0, 0, 0
        
        for match in matches:
            players = match.get("players", {}).get("all_players", [])
            for p in players:
                if p.get("puuid") == puuid:
                    agents.append(p.get("character", "Bilinmiyor"))
                    stats = p.get("stats", {})
                    kills += stats.get("kills", 0)
                    deaths += stats.get("deaths", 0)
                    assists += stats.get("assists", 0)
                    score += stats.get("score", 0)

        match_count = len(matches) or 1
        return {
            "matches_analyzed": len(matches),
            "main_agent": Counter(agents).most_common(1)[0][0] if agents else "Bilinmiyor",
            "avg_kd": round(kills / deaths, 2) if deaths > 0 else float(kills),
            "avg_kills": round(kills / match_count, 1),
            "avg_deaths": round(deaths / match_count, 1),
            "avg_assists": round(assists / match_count, 1),
            "avg_score": round(score / match_count, 1),
            "total_kills": kills, "total_deaths": deaths, "total_assists": assists
        }

# =====================================================================
# 5. ARAYÜZ (VIEWS)
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
        if interaction.user.id != self.ctx.author.id: return
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Sonraki ▶", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return
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

    @commands.command(name="kayit", aliases=["register"])
    async def kayit(self, ctx, *, riot_id: str):
        """Discord hesabınızı kalıcı olarak PUUID ile eşleştirir."""
        if "#" not in riot_id:
            return await ctx.send("Kullanım: `v!kayit İsim#Tag`")
        
        name, tag = [p.strip() for p in riot_id.split("#", 1)]
        tag = tag.split()[0][:6]
        
        msg = await ctx.send(f"⏳ `{name}#{tag}` doğrulanıyor...")
        async with aiohttp.ClientSession() as session:
            acc = await self.api_client.get_account_by_name(session, name, tag)
            if not acc["success"]:
                return await msg.edit(content="❌ Oyuncu bulunamadı (API yanıt vermedi veya isim hatalı).")
            
            GlobalDatabase.register_user(ctx.author.id, acc["puuid"], acc["name"], acc["tag"], acc["region"])
            await msg.edit(content=f"✅ Başarıyla kaydedildi! Sistem Discord kimliğinizi `{acc['name']}#{acc['tag']}` ile eşleştirdi.")

    @commands.command(name="stats", aliases=["istatistik", "stat"])
    async def stats(self, ctx, user: discord.Member = None):
        """Kayıtlı Discord kullanıcılarının verilerini çeker."""
        target = user or ctx.author
        db_user = GlobalDatabase.get_user(target.id)

        if not db_user:
            return await ctx.send(f"❌ {target.mention} global sisteme kayıtlı değil! Önce `v!kayit İsim#Tag` yapılmalı.")

        msg = await ctx.send(embed=discord.Embed(description=f"🔍 `{db_user['name']}#{db_user['tag']}` için veriler getiriliyor...", color=0x00F0FF))

        puuid, region = db_user["puuid"], db_user["region"]
        
        async with aiohttp.ClientSession() as session:
            # Sadece PUUID ile kesin istek atılır, Name/Tag sorunu yaşanmaz.
            mmr = await self.api_client.get_mmr_by_puuid(session, region, puuid)
            matches = await self.api_client.get_matches_by_puuid(session, region, puuid)

        metrics = StatisticsAnalyzer.analyze_player(matches, puuid)
        
        embed1 = discord.Embed(
            title=f"OYUNCU PROFİLİ | {db_user['name']}#{db_user['tag']}",
            description=f"**Bölge:** `{region.upper()}` | **Kayıtlı DC:** {target.mention}",
            color=0x00F0FF
        )
        embed1.add_field(name="🏆 Rekabetçi", value=f"• **Rank:** `{mmr['tier']}`\n• **RR:** `{mmr['rr']}`\n• **ELO:** `{mmr['elo']}`", inline=False)
        embed1.add_field(name="📊 Son Performans Özeti", value=f"• **Maç:** `{metrics['matches_analyzed']}`\n• **Main:** `{metrics['main_agent']}`\n• **K/D:** `{metrics['avg_kd']}`\n• **Skor:** `{metrics['avg_kills']}/{metrics['avg_deaths']}/{metrics['avg_assists']}`", inline=False)
        
        embed2 = discord.Embed(title=f"DETAYLI SAVAŞ ANALİZİ | {db_user['name']}#{db_user['tag']}", color=0x00F0FF)
        embed2.add_field(name="⚔️ Toplam Çatışma Verileri", value=f"• **Kill:** `{metrics['total_kills']}`\n• **Death:** `{metrics['total_deaths']}`\n• **Asist:** `{metrics['total_assists']}`", inline=False)
        
        try:
            view = ProfilePagingView(ctx, [embed1, embed2])
            await msg.edit(content=None, embed=embed1, view=view)
            view.message = msg
        except Exception:
            await ctx.send(embed=embed1)

    @commands.command(name="duo")
    async def duo(self, ctx):
        """Global sistemde yakın ELO'ya sahip eşleşme arar."""
        user_record = GlobalDatabase.get_user(ctx.author.id)
        if not user_record: return await ctx.send("❌ `v!kayit` komutu ile kayıt olmalısınız.")

        msg = await ctx.send("🔍 Veritabanındaki diğer oyuncuların rankları analiz ediliyor...")
        
        async with aiohttp.ClientSession() as session:
            my_mmr = await self.api_client.get_mmr_by_puuid(session, user_record["region"], user_record["puuid"])
            my_elo = my_mmr.get("elo", 0)

            best_match, min_diff = None, float('inf')
            
            for dc_id, data in GlobalDatabase.get_all_users().items():
                if int(dc_id) == ctx.author.id: continue
                
                target_mmr = await self.api_client.get_mmr_by_puuid(session, data["region"], data["puuid"])
                diff = abs(my_elo - target_mmr.get("elo", 0))
                
                if diff < min_diff:
                    min_diff, best_match = diff, {"dc": dc_id, "name": data["name"], "tag": data["tag"], "tier": target_mmr["tier"]}

        if not best_match: return await msg.edit(content="Sistemde uygun oyuncu bulunamadı.")
        
        embed = discord.Embed(title="🔗 Duo Bulundu!", color=0x00FF00)
        embed.add_field(name="Sen", value=f"Rank: `{my_mmr['tier']}`")
        embed.add_field(name="Eşleşme", value=f"Oyuncu: <@{best_match['dc']}>\nRank: `{best_match['tier']}`")
        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Stats(bot))