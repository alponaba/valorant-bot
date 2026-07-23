# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Global Discord ID ve PUUID Tabanlı Kayıt ve Duo Eşleştirme Modülü
Modül: cogs.stats
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
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("VTracker.GlobalEngine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

GLOBAL_DB_FILE = "global_registered_users.json"
FALLBACK_API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"


class GlobalDatabase:
    """Discord ID bazlı global veritabanı yöneticisi."""
    
    @staticmethod
    def load_db() -> Dict[str, Any]:
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
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
            "updated_at": datetime.utcnow().isoformat()
        }
        GlobalDatabase.save_db(db)

    @staticmethod
    def get_user(discord_id: int) -> Optional[Dict[str, Any]]:
        db = GlobalDatabase.load_db()
        return db.get(str(discord_id))

    @staticmethod
    def get_all_users() -> Dict[str, Any]:
        return GlobalDatabase.load_db()


class ValorantAPIClient:
    """Global PUUID ve Hesap Bilgisi Çekme İstemcisi."""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.primary_base = "https://api.henrikdev.xyz"

    @property
    def api_key(self) -> str:
        return getattr(self.bot, "henrik_api_key", FALLBACK_API_KEY)

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "V-Tracker-Bot/5.0"}
        key = self.api_key
        if key:
            headers["Authorization"] = key
        return headers

    async def _safe_get(self, session: aiohttp.ClientSession, url: str) -> Tuple[int, Optional[Dict[str, Any]]]:
        headers = self.get_headers()
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                status = response.status
                text = await response.text()
                if status == 200:
                    try:
                        return status, json.loads(text)
                    except json.JSONDecodeError:
                        return 500, None
                return status, None
        except Exception:
            return 500, None

    async def get_account_by_name(self, session: aiohttp.ClientSession, name: str, tag: str) -> Dict[str, Any]:
        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"{self.primary_base}/riot/v1/account/{encoded_name}/{encoded_tag}"
        status, data = await self._safe_get(session, url)
        
        if status == 200 and data:
            acc_data = data.get("data", {})
            if acc_data and acc_data.get("puuid"):
                return {
                    "puuid": acc_data.get("puuid"),
                    "region": (acc_data.get("region") or "eu").lower(),
                    "name": acc_data.get("name", name),
                    "tag": acc_data.get("tag", tag),
                    "success": True
                }
        return {"success": False}

    async def get_mmr_by_puuid(self, session: aiohttp.ClientSession, region: str, puuid: str) -> Dict[str, Any]:
        target_regions = list(dict.fromkeys([region, "tr", "eu"]))
        for reg in target_regions:
            url = f"{self.primary_base}/val/v2/by-puuid/mmr/{reg}/{puuid}"
            status, data = await self._safe_get(session, url)
            if status == 200 and data:
                d = data.get("data", {})
                if d:
                    current_data = d.get("current_data", {})
                    tier = current_data.get("currenttierpatched") or "Unranked"
                    elo = current_data.get("elo", 0)
                    return {"tier": tier, "elo": elo, "success": True}
        return {"tier": "Unranked", "elo": 0, "success": False}


class GlobalStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_client = ValorantAPIClient(bot)

    @commands.command(name="kayit", aliases=["register"])
    async def kayit(self, ctx, *, riot_id: str):
        """Discord ID'sini Riot PUUID ile global olarak eşleştirir."""
        if "#" not in riot_id:
            await ctx.send("❌ Hatalı format! Örnek: `v!kayit İsim#Tag`")
            return

        name_part, tag_part = riot_id.split("#", 1)
        name = name_part.strip()
        tag = tag_part.strip().split()[0][:6]

        async with aiohttp.ClientSession() as session:
            res = await self.api_client.get_account_by_name(session, name, tag)
            if not res.get("success"):
                await ctx.send(f"❌ **{name}#{tag}** Riot sunucularında bulunamadı.")
                return

            GlobalDatabase.register_user(
                discord_id=ctx.author.id,
                puuid=res["puuid"],
                name=res["name"],
                tag=res["tag"],
                region=res["region"]
            )

        await ctx.send(f"✅ Başarıyla global veritabanına kaydedildiniz! Riot ID: `{res['name']}#{res['tag']}`")

    @commands.command(name="duo")
    async def duo(self, ctx):
        """Global veritabanındaki kullanıcılar arasında en yakın ELO'ya sahip kişiyi bulur."""
        user_record = GlobalDatabase.get_user(ctx.author.id)
        if not user_record:
            await ctx.send("❌ Önce `v!kayit İsim#Tag` komutu ile kayıt olmalısınız!")
            return

        async with aiohttp.ClientSession() as session:
            my_mmr = await self.api_client.get_mmr_by_puuid(session, user_record["region"], user_record["puuid"])
            my_elo = my_mmr.get("elo", 0)

            all_users = GlobalDatabase.get_all_users()
            best_match = None
            min_elo_diff = float('inf')

            for dc_id_str, data in all_users.items():
                if int(dc_id_str) == ctx.author.id:
                    continue
                
                target_mmr = await self.api_client.get_mmr_by_puuid(session, data["region"], data["puuid"])
                target_elo = target_mmr.get("elo", 0)
                
                diff = abs(my_elo - target_elo)
                if diff < min_elo_diff:
                    min_elo_diff = diff
                    best_match = {
                        "discord_id": int(dc_id_str),
                        "name": data["name"],
                        "tag": data["tag"],
                        "tier": target_mmr.get("tier", "Unranked"),
                        "elo": target_elo
                    }

        if not best_match:
            await ctx.send("🔍 Global sistemde eşleşebileceğiniz başka kayıtlı oyuncu bulunamadı.")
            return

        embed = discord.Embed(
            title="🔗 En İdeal Global Duo Eşleşmesi",
            description=f"Arama yapılan oyuncu ELO farkı: `{min_elo_diff}`",
            color=0x00FF00
        )
        embed.add_field(name="Siz", value=f"• **Rank:** `{my_mmr.get('tier')}`\n• **ELO:** `{my_elo}`", inline=True)
        embed.add_field(name="Önerilen Duo", value=f"• **Oyuncu:** `{best_match['name']}#{best_match['tag']}`\n• **Rank:** `{best_match['tier']}`\n• **ELO:** `{best_match['elo']}`\n• **Discord ID:** `<@{best_match['discord_id']}>`", inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GlobalStats(bot))