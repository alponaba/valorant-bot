# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Seçkin İstatistik ve Analiz Modülü (Sadece Kayıtlı Üyeler)
Modül: cogs.stats
"""

import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
import logging
from typing import Dict, Any, Optional, List

# =====================================================================
# 1. LOGLAMA VE TEMEL AYARLAR
# =====================================================================

logger = logging.getLogger("VTracker.Stats")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

GLOBAL_DB_FILE = "global_registered_users.json"
API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"

# =====================================================================
# 2. VERİTABANI YÖNETİCİSİ (KİMLİK DOĞRULAMA İÇİN)
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
    def get_user(discord_id: str) -> Optional[Dict[str, Any]]:
        return GlobalDatabase.load_db().get(str(discord_id))

    @staticmethod
    def find_user_by_riot_id(name: str, tag: str) -> Optional[Dict[str, Any]]:
        db = GlobalDatabase.load_db()
        for dc_id, data in db.items():
            if data.get("name", "").lower() == name.lower() and data.get("tag", "").lower() == tag.lower():
                data["discord_id"] = dc_id
                return data
        return None

# =====================================================================
# 3. VALORANT API İSTEMCİSİ (VERİ ÇEKİCİ)
# =====================================================================

class ValorantDataAPI:
    def __init__(self):
        self.base_url = "https://api.henrikdev.xyz"
        self.headers = {"User-Agent": "V-Tracker-Bot/7.0", "Authorization": API_KEY}

    async def _get(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with session.get(url, headers=self.headers, timeout=15) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"API İstek Hatası: {e}")
        return None

    async def get_account(self, session, name: str, tag: str):
        url = f"{self.base_url}/valorant/v1/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
        return await self._get(session, url)

    async def get_mmr(self, session, region: str, puuid: str):
        url = f"{self.base_url}/valorant/v2/by-puuid/mmr/{region}/{puuid}"
        return await self._get(session, url)

    async def get_matches(self, session, region: str, puuid: str, limit: int = 15):
        url = f"{self.base_url}/valorant/v3/by-puuid/matches/{region}/{puuid}?size={limit}"
        return await self._get(session, url)

# =====================================================================
# 4. ANALİZ MOTORU (MATEMATİKSEL İSTATİSTİKLER)
# =====================================================================

class StatsEngine:
    @staticmethod
    def analyze(matches: List[Dict[str, Any]], puuid: str) -> Dict[str, Any]:
        data = {
            "kills": 0, "deaths": 0, "assists": 0,
            "headshots": 0, "bodyshots": 0, "legshots": 0,
            "agents": {}, "maps": {}, "weapons": {},
            "total_matches": len(matches)
        }

        for match in matches:
            # 1. Harita Verileri
            map_name = match.get("metadata", {}).get("map", "Bilinmiyor")
            if map_name not in data["maps"]:
                data["maps"][map_name] = {"played": 0, "won": 0}
            data["maps"][map_name]["played"] += 1

            # 2. Oyuncu Bulma
            all_players = match.get("players", {}).get("all_players", [])
            player = next((p for p in all_players if p.get("puuid") == puuid), None)

            if player:
                # Kazanma Durumu
                team = player.get("team", "").lower()
                teams = match.get("teams", {})
                if team in teams and teams[team].get("has_won"):
                    data["maps"][map_name]["won"] += 1

                # Çatışma
                stats = player.get("stats", {})
                data["kills"] += stats.get("kills", 0)
                data["deaths"] += stats.get("deaths", 0)
                data["assists"] += stats.get("assists", 0)

                # Ajan
                agent = player.get("character", "Bilinmiyor")
                data["agents"][agent] = data["agents"].get(agent, 0) + 1

                # İsabet / Headshot Oranı
                for dmg in player.get("damage_made", []):
                    data["headshots"] += dmg.get("headshots", 0)
                    data["bodyshots"] += dmg.get("bodyshots", 0)
                    data["legshots"] += dmg.get("legshots", 0)

            # 3. Silah Kullanımı
            for kill in match.get("kills", []):
                if kill.get("killer_puuid") == puuid:
                    wep = kill.get("damage_weapon_name", "Bilinmiyor")
                    if wep and wep != "Bilinmiyor":
                        data["weapons"][wep] = data["weapons"].get(wep, 0) + 1

        # Oran Hesaplamaları
        total_shots = data["headshots"] + data["bodyshots"] + data["legshots"]
        hs_rate = round((data["headshots"] / total_shots * 100), 1) if total_shots > 0 else 0
        kd_ratio = round(data["kills"] / data["deaths"], 2) if data["deaths"] > 0 else data["kills"]

        # Sıralamalar
        sorted_maps = sorted(data["maps"].items(), key=lambda x: x[1]["played"], reverse=True)[:5]
        sorted_weapons = sorted(data["weapons"].items(), key=lambda x: x[1], reverse=True)[:3]
        
        main_agent = max(data["agents"], key=data["agents"].get) if data["agents"] else "Yok"
        best_map = max(data["maps"].items(), key=lambda x: (x[1]["won"]/x[1]["played"] if x[1]["played"] > 0 else 0, x[1]["played"]))[0] if data["maps"] else "Yok"

        return {
            "kills": data["kills"], "deaths": data["deaths"], "assists": data["assists"],
            "hs_rate": hs_rate, "kd": kd_ratio, "main_agent": main_agent, "best_map": best_map,
            "top_maps": sorted_maps, "top_weapons": sorted_weapons, "total_matches": data["total_matches"]
        }

# =====================================================================
# 5. KOMUT (COG)
# =====================================================================

class AdvancedStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = ValorantDataAPI()

    @commands.command(name="stats", aliases=["istatistik", "profil"])
    async def stats_command(self, ctx, *, hedef: str = None):
        
        # 1. GİZLİLİK VE YETKİ KONTROLÜ (SADECE KAYITLILAR KULLANABİLİR)
        caller_id = str(ctx.author.id)
        caller_db = GlobalDatabase.get_user(caller_id)
        
        if not caller_db:
            embed = discord.Embed(
                title="🔒 Erişim Reddedildi",
                description="Bu komutu kullanmak ve başkalarının istatistiklerini görmek için **önce sisteme kayıt olmalısınız.**\n\n📝 **Kayıt olmak için:** `v!register [Discord ID] [Riotİsmi#Tag]`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # 2. HEDEF BELİRLEME
        target_name, target_tag, target_puuid, target_region = None, None, None, None
        target_mention = ctx.author.mention

        if not hedef:
            # Kendisi
            target_name, target_tag = caller_db["name"], caller_db["tag"]
            target_puuid, target_region = caller_db["puuid"], caller_db["region"]
        elif hedef.startswith("<@"):
            # Discord Etiketi
            target_dc_id = hedef.strip("<@!>")
            target_db = GlobalDatabase.get_user(target_dc_id)
            if not target_db:
                return await ctx.send("❌ Etiketlediğin kullanıcı V-Tracker sistemine kayıtlı değil.")
            target_name, target_tag = target_db["name"], target_db["tag"]
            target_puuid, target_region = target_db["puuid"], target_db["region"]
            target_mention = f"<@{target_dc_id}>"
        elif "#" in hedef:
            # Riot ID ile Arama (Direkt API veya DB sorgusu)
            name, tag = hedef.split("#", 1)
            msg = await ctx.send(f"🔍 `{name}#{tag}` aranıyor...")
            async with aiohttp.ClientSession() as session:
                acc_data = await self.api.get_account(session, name, tag)
                if not acc_data or "data" not in acc_data:
                    return await msg.edit(content="❌ Oyuncu Riot sunucularında bulunamadı.")
                
                target_puuid = acc_data["data"]["puuid"]
                target_region = acc_data["data"]["region"]
                target_name = acc_data["data"]["name"]
                target_tag = acc_data["data"]["tag"]
                target_mention = f"Riot ID: {target_name}#{target_tag}"
            if 'msg' in locals(): await msg.delete()
        else:
            return await ctx.send("❌ Hatalı format. Sadece komutu yazın, birini `@etiketleyin` veya `İsim#Tag` girin.")

        # 3. VERİ ÇEKME İŞLEMİ (ACCOUNT + MMR + MATCHES)
        loading_msg = await ctx.send(f"🔮 **{target_name}#{target_tag}** için şaheser hazırlanıyor, veriler analiz ediliyor...")

        async with aiohttp.ClientSession() as session:
            acc = await self.api.get_account(session, target_name, target_tag)
            if not acc or "data" not in acc:
                return await loading_msg.edit(content="❌ Hesap bilgileri çekilemedi.")
            
            account_data = acc["data"]
            title = account_data.get("account_title", "Unvansız")
            level = account_data.get("account_level", 0)
            card_small = account_data.get("card", {}).get("small", "")
            card_large = account_data.get("card", {}).get("large", "") # Dikdörtgen PFP

            mmr = await self.api.get_mmr(session, target_region, target_puuid)
            rank_name = "Derecesiz"
            elo = 0
            if mmr and "data" in mmr and mmr["data"].get("current_data"):
                rank_name = mmr["data"]["current_data"].get("currenttierpatched", "Derecesiz")
                elo = mmr["data"]["current_data"].get("ranking_in_tier", 0)

            matches = await self.api.get_matches(session, target_region, target_puuid, limit=15)
            match_data = matches.get("data", []) if matches else []

            if not match_data:
                return await loading_msg.edit(content=f"❌ {target_name}#{target_tag} için son maç verisi bulunamadı.")

            # 4. ANALİZ
            stats = StatsEngine.analyze(match_data, target_puuid)

            # 5. GÖRSEL ŞAHAESER (EMBED) TASARIMI
            embed = discord.Embed(
                title=f"{target_name}#{target_tag}",
                description=f"Son **{stats['total_matches']} Maçın** Profesyonel Analiz Raporu\nTalep eden: {ctx.author.mention}",
                color=0x00F0FF
            )

            # Emojili ve küçük kare resimli yazar kısmı
            embed.set_author(name=f"[{title}] {target_name}", icon_url=card_small)
            
            # Kenarda dikey büyük resim
            if card_large:
                embed.set_thumbnail(url=card_large)

            # Satır 1: Profil
            embed.add_field(name="🏅 Derece", value=f"`{rank_name}`\n**{elo} RR**", inline=True)
            embed.add_field(name="🔮 Seviye", value=f"`{level}`", inline=True)
            embed.add_field(name="🎭 En İyi Ajan", value=f"`{stats['main_agent']}`", inline=True)

            # Satır 2: Çatışma Özeti
            combat_text = (
                f"**K/D/A:** `{stats['kills']}` / `{stats['deaths']}` / `{stats['assists']}`\n"
                f"**K/D Oranı:** `{stats['kd']}`\n"
                f"**HS Oranı:** `% {stats['hs_rate']}` 🎯"
            )
            embed.add_field(name="⚔️ Çatışma Analizi", value=combat_text, inline=False)

            # Satır 3: Haritalar
            map_text = f"🏆 **En Başarılı Harita:** `{stats['best_map']}`\n\n"
            for i, (m_name, m_data) in enumerate(stats['top_maps'], 1):
                wins = m_data["won"]
                played = m_data["played"]
                wr = int((wins / played) * 100) if played > 0 else 0
                map_text += f"{i}. **{m_name}**: %{wr} WR `({wins}W / {played} Maç)`\n"
            
            if not stats['top_maps']:
                map_text += "Harita verisi yok."
                
            embed.add_field(name="🗺️ Harita Performansı", value=map_text, inline=True)

            # Satır 4: Silahlar
            wep_text = ""
            for i, (w_name, w_kills) in enumerate(stats['top_weapons'], 1):
                wep_text += f"{i}. **{w_name}** - `{w_kills} Kill`\n"
            
            if not stats['top_weapons']:
                wep_text = "Silah verisi tespit edilemedi."
                
            embed.add_field(name="🔫 En Çok İş Yapan Silahlar", value=wep_text, inline=True)

            embed.set_footer(text="V-Tracker.gg Özel Analiz Motoru • Sadece Kayıtlı Üyeler İçin")

            await loading_msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(AdvancedStats(bot))
    logger.info("AdvancedStats Modülü Yüklendi.")