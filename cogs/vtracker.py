# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Kalıcı Kayıt ve 2 Sayfalı Profesyonel İstatistik Sistemi
Modül: cogs.vtracker
"""

import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

# =====================================================================
# 1. LOGLAMA VE DOSYA YOLU YAPILANDIRMASI
# =====================================================================

logger = logging.getLogger("VTracker.System")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_DB_FILE = os.path.join(BASE_DIR, "global_registered_users.json")
API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"

# =====================================================================
# 2. KALICI VERİTABANI YÖNETİCİSİ
# =====================================================================

class GlobalDatabase:
    @staticmethod
    def load_db() -> Dict[str, Any]:
        data = {}
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
            except Exception as e:
                logger.error(f"Veritabanı okuma hatası: {e}")

        permanent_user_id = "76003400419407626"
        if permanent_user_id not in data:
            data[permanent_user_id] = {
                "puuid": "",
                "name": "nxbx",
                "tag": "NABA",
                "region": "eu",
                "v_coins": 0,
                "updated_at": datetime.utcnow().isoformat()
            }
        return data

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
        discord_id_str = str(discord_id)
        db[discord_id_str] = {
            "puuid": puuid,
            "name": name,
            "tag": tag,
            "region": region,
            "v_coins": db.get(discord_id_str, {}).get("v_coins", 0),
            "updated_at": datetime.utcnow().isoformat()
        }
        GlobalDatabase.save_db(db)

    @staticmethod
    def get_user(discord_id: str) -> Optional[Dict[str, Any]]:
        db = GlobalDatabase.load_db()
        discord_id_str = str(discord_id)
        if discord_id_str in db:
            return db[discord_id_str]
        return None

# =====================================================================
# 3. VALORANT API İSTEMCİSİ
# =====================================================================

class ValorantAPI:
    def __init__(self):
        self.base_url = "https://api.henrikdev.xyz"
        self.headers = {"User-Agent": "V-Tracker-Bot/8.0", "Authorization": API_KEY}

    def _fix_region(self, region: str) -> str:
        if not region:
            return "eu"
        r = region.lower()
        if r in ["tr", "ru"]:
            return "eu"
        return r

    async def _get(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"API İstek İstisnası ({url}): {e}")
        return None

    async def get_account(self, session, name: str, tag: str):
        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"{self.base_url}/valorant/v1/account/{encoded_name}/{encoded_tag}"
        return await self._get(session, url)

    async def get_mmr(self, session, region: str, puuid: str):
        fixed_reg = self._fix_region(region)
        url = f"{self.base_url}/valorant/v2/by-puuid/mmr/{fixed_reg}/{puuid}"
        return await self._get(session, url)

    async def get_matches(self, session, region: str, puuid: str, limit: int = 15):
        fixed_reg = self._fix_region(region)
        url = f"{self.base_url}/valorant/v3/by-puuid/matches/{fixed_reg}/{puuid}?size={limit}"
        return await self._get(session, url)

# =====================================================================
# 4. İSTATİSTİK ANALİZ MOTORU
# =====================================================================

class StatsEngine:
    @staticmethod
    def analyze(matches: List[Dict[str, Any]], puuid: str) -> Dict[str, Any]:
        data = {
            "kills": 0, "deaths": 0, "assists": 0,
            "headshots": 0, "bodyshots": 0, "legshots": 0,
            "agents": {}, "maps": {}, "weapons": {},
            "total_damage": 0, "total_rounds": 0,
            "wins": 0, "losses": 0,
            "total_matches": len(matches) if isinstance(matches, list) else 0
        }

        if not isinstance(matches, list):
            return data

        for match in matches:
            if not isinstance(match, dict):
                continue
            
            map_name = match.get("metadata", {}).get("map", "Bilinmiyor")
            if map_name not in data["maps"]:
                data["maps"][map_name] = {"played": 0, "won": 0}
            data["maps"][map_name]["played"] += 1

            players_obj = match.get("players", {})
            all_players = players_obj.get("all_players", []) if isinstance(players_obj, dict) else []
            
            player = None
            if isinstance(all_players, list):
                player = next((p for p in all_players if isinstance(p, dict) and p.get("puuid") == puuid), None)

            if player:
                team = str(player.get("team", "")).lower()
                teams = match.get("teams", {})
                if isinstance(teams, dict) and team in teams and isinstance(teams[team], dict):
                    if teams[team].get("has_won"):
                        data["maps"][map_name]["won"] += 1
                        data["wins"] += 1
                    else:
                        data["losses"] += 1

                stats = player.get("stats", {}) or {}
                data["kills"] += stats.get("kills", 0)
                data["deaths"] += stats.get("deaths", 0)
                data["assists"] += stats.get("assists", 0)
                
                rounds_played = match.get("metadata", {}).get("rounds_played", 1)
                if rounds_played < 1: rounds_played = 1
                data["total_rounds"] += rounds_played

                agent = player.get("character", "Bilinmiyor")
                data["agents"][agent] = data["agents"].get(agent, 0) + 1

                damage_made = player.get("damage_made", [])
                if isinstance(damage_made, list):
                    for dmg in damage_made:
                        if isinstance(dmg, dict):
                            data["headshots"] += dmg.get("headshots", 0)
                            data["bodyshots"] += dmg.get("bodyshots", 0)
                            data["legshots"] += dmg.get("legshots", 0)
                            data["total_damage"] += dmg.get("damage", 0)

            kills_list = match.get("kills", [])
            if isinstance(kills_list, list):
                for kill in kills_list:
                    if isinstance(kill, dict) and kill.get("killer_puuid") == puuid:
                        wep = kill.get("damage_weapon_name", "Bilinmiyor")
                        if wep and wep != "Bilinmiyor":
                            data["weapons"][wep] = data["weapons"].get(wep, 0) + 1

        total_shots = data["headshots"] + data["bodyshots"] + data["legshots"]
        hs_rate = round((data["headshots"] / total_shots * 100), 1) if total_shots > 0 else 0
        kd_ratio = round(data["kills"] / data["deaths"], 2) if data["deaths"] > 0 else data["kills"]
        adr = round(data["total_damage"] / data["total_rounds"], 1) if data["total_rounds"] > 0 else 0

        sorted_maps = sorted(data["maps"].items(), key=lambda x: x[1]["played"], reverse=True)[:5]
        sorted_weapons = sorted(data["weapons"].items(), key=lambda x: x[1], reverse=True)[:3]
        sorted_agents = sorted(data["agents"].items(), key=lambda x: x[1], reverse=True)
        main_agent = sorted_agents[0][0] if sorted_agents else "Yok"

        return {
            "kills": data["kills"], "deaths": data["deaths"], "assists": data["assists"],
            "hs_rate": hs_rate, "kd": kd_ratio, "adr": adr,
            "wins": data["wins"], "losses": data["losses"],
            "main_agent": main_agent, "top_agents": sorted_agents,
            "top_maps": sorted_maps, "top_weapons": sorted_weapons, "total_matches": data["total_matches"]
        }

# =====================================================================
# 5. SAYFALANDIRMA (PAGINATION VIEW)
# =====================================================================

class StatsPaginationView(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed]):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="İleri", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

# =====================================================================
# 6. BİRLEŞTİRİLMİŞ COG
# =====================================================================

class VTrackerSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = ValorantAPI()

    @commands.command(name="register", aliases=["kayit"])
    async def register_command(self, ctx, discord_id_input: str = None, *, riot_id: str = None):
        if not discord_id_input or not riot_id or "#" not in riot_id:
            return await ctx.send("❌ Hatalı kullanım. Örnek: `v!register 76003400419407626 Oyuncu#TR1`")

        name, tag = riot_id.split("#", 1)
        msg = await ctx.send(f"🔍 `{name}#{tag}` doğrulanıyor...")

        async with aiohttp.ClientSession() as session:
            acc_data = await self.api.get_account(session, name, tag)
            if not acc_data or "data" not in acc_data:
                return await msg.edit(content=f"❌ Riot hesabı bulunamadı.")

            acc = acc_data["data"]
            GlobalDatabase.register_user(discord_id_input, acc.get("puuid"), acc.get("name"), acc.get("tag"), (acc.get("region") or "eu").lower())
            await msg.edit(content=f"✅ Kayıt Başarılı! Artık `v!stats` komutunu kullanabilirsin.")

    @commands.command(name="stats", aliases=["istatistik", "profil"])
    async def stats_command(self, ctx, *, hedef: str = None):
        caller_id = str(ctx.author.id)
        caller_db = GlobalDatabase.get_user(caller_id)
        
        if not caller_db:
            return await ctx.send("🔒 Bu komutu kullanmak için kayıt olmalısın. Örnek: `v!register [Discord ID] [İsim#Tag]`")

        target_name, target_tag, target_puuid, target_region = caller_db["name"], caller_db["tag"], caller_db["puuid"], caller_db["region"]

        loading_msg = await ctx.send(f"Analiz ediliyor...")

        try:
            async with aiohttp.ClientSession() as session:
                if not target_puuid:
                    acc_init = await self.api.get_account(session, target_name, target_tag)
                    if acc_init and "data" in acc_init:
                        target_puuid = acc_init["data"].get("puuid")
                        target_region = (acc_init["data"].get("region") or "eu").lower()
                        GlobalDatabase.register_user(ctx.author.id, target_puuid, target_name, target_tag, target_region)

                acc = await self.api.get_account(session, target_name, target_tag)
                account_data = acc.get("data", {})
                title = account_data.get("account_title", "Unvansız")
                level = account_data.get("account_level", 0)
                card_large = account_data.get("card", {}).get("large", "")

                mmr = await self.api.get_mmr(session, target_region, target_puuid)
                rank_name, elo = "Derecesiz", 0
                if mmr and "data" in mmr and mmr["data"].get("current_data"):
                    rank_name = mmr["data"]["current_data"].get("currenttierpatched", "Derecesiz")
                    elo = mmr["data"]["current_data"].get("ranking_in_tier", 0)

                matches = await self.api.get_matches(session, target_region, target_puuid, limit=15)
                match_data = matches.get("data", []) if matches and "data" in matches else []

                if not match_data:
                    return await loading_msg.edit(content=f"Maç verisi bulunamadı.")

                stats = StatsEngine.analyze(match_data, target_puuid)

                # ================= PAGE 1 =================
                embed1 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description=f"Son **{stats['total_matches']} Maçın** Genel Analiz Raporu\nTalep eden: {ctx.author.mention}",
                    color=0x00F0FF
                )
                if card_large:
                    embed1.set_thumbnail(url=card_large)

                embed1.add_field(name="Derece", value=f"`{rank_name}`\n**{elo} RR**", inline=True)
                embed1.add_field(name="Seviye", value=f"`{level}`", inline=True)
                embed1.add_field(name="En İyi Ajan", value=f"`{stats['main_agent']}`", inline=True)

                combat_text = (
                    f"**K/D/A:** `{stats['kills']}` / `{stats['deaths']}` / `{stats['assists']}`\n"
                    f"**K/D Oranı:** `{stats['kd']}`\n"
                    f"**HS Oranı:** `% {stats['hs_rate']}`"
                )
                embed1.add_field(name="Çatışma Analizi", value=combat_text, inline=False)

                map_text = ""
                for i, (m_name, m_data) in enumerate(stats['top_maps'], 1):
                    wins = m_data["won"]
                    played = m_data["played"]
                    wr = int((wins / played) * 100) if played > 0 else 0
                    map_text += f"{i}. **{m_name}**: %{wr} WR `({wins}W / {played} Maç)`\n"
                embed1.add_field(name="En Çok Oynanan Haritalar", value=map_text or "Veri yok.", inline=True)

                wep_text = ""
                for i, (w_name, w_kills) in enumerate(stats['top_weapons'], 1):
                    wep_text += f"{i}. **{w_name}** - `{w_kills} Kill`\n"
                embed1.add_field(name="En İyi Silahlar", value=wep_text or "Veri yok.", inline=True)

                embed1.set_footer(text="Sayfa 1/2 • V-Tracker.gg Özel Analiz Motoru")

                # ================= PAGE 2 =================
                embed2 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description=f"Detaylı Rekabetçi Performans ve Ajan Dağılımı",
                    color=0x00F0FF
                )
                if card_large:
                    embed2.set_thumbnail(url=card_large)

                overview_text = (
                    f"**Hasar / Tur (ADR):** `{stats['adr']}`\n"
                    f"**K/D Oranı:** `{stats['kd']}`\n"
                    f"**HS Oranı:** `% {stats['hs_rate']}`\n"
                    f"**Kazanılan / Kaybedilen:** `{stats['wins']}W` / `{stats['losses']}L`"
                )
                embed2.add_field(name="Rekabetçi Genel Bakış", value=overview_text, inline=False)

                agent_text = ""
                for i, (agent_name, agent_count) in enumerate(stats['top_agents'][:5], 1):
                    agent_text += f"{i}. **{agent_name}** - `{agent_count} Maç`\n"
                embed2.add_field(name="En Çok Oynanan Ajanlar", value=agent_text or "Veri yok.", inline=False)

                embed2.set_footer(text="Sayfa 2/2 • V-Tracker.gg Detaylı İstatistikler")

                view = StatsPaginationView([embed1, embed2])
                await loading_msg.edit(content=None, embed=embed1, view=view)

        except Exception as e:
            logger.error(f"Stats Hatası: {e}", exc_info=True)
            await loading_msg.edit(content=f"❌ Hata oluştu: `{e}`")

async def setup(bot):
    await bot.add_cog(VTrackerSystem(bot))