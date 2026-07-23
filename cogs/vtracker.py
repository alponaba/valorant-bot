# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Kalıcı Kayıt ve 3 Sayfalı Teknik İstatistik Sistemi
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
            "puuid": puuid or "",
            "name": name or "",
            "tag": tag or "",
            "region": region or "eu",
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
                else:
                    logger.warning(f"API HTTP Hata Kodu ({response.status}) - URL: {url}")
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
            "wins": 0, "losses": 0, "score_sum": 0,
            "total_matches": len(matches) if isinstance(matches, list) else 0
        }

        if not isinstance(matches, list):
            return data

        for match in matches:
            if not isinstance(match, dict):
                continue
            
            metadata = match.get("metadata") or {}
            map_name = metadata.get("map", "Bilinmiyor")
            if map_name not in data["maps"]:
                data["maps"][map_name] = {"played": 0, "won": 0}
            data["maps"][map_name]["played"] += 1

            players_obj = match.get("players") or {}
            all_players = players_obj.get("all_players", []) if isinstance(players_obj, dict) else []
            
            player = None
            if isinstance(all_players, list):
                player = next((p for p in all_players if isinstance(p, dict) and p.get("puuid") == puuid), None)

            if player:
                team = str(player.get("team", "")).lower()
                teams = match.get("teams") or {}
                if isinstance(teams, dict) and team in teams and isinstance(teams[team], dict):
                    if teams[team].get("has_won"):
                        data["maps"][map_name]["won"] += 1
                        data["wins"] += 1
                    else:
                        data["losses"] += 1

                stats = player.get("stats") or {}
                data["kills"] += stats.get("kills", 0)
                data["deaths"] += stats.get("deaths", 0)
                data["assists"] += stats.get("assists", 0)
                data["score_sum"] += stats.get("score", 0)
                
                rounds_played = metadata.get("rounds_played", 1)
                if not rounds_played or rounds_played < 1: 
                    rounds_played = 1
                data["total_rounds"] += rounds_played

                agent = player.get("character", "Bilinmiyor")
                data["agents"][agent] = data["agents"].get(agent, 0) + 1

                damage_made = player.get("damage_made", {})
                if isinstance(damage_made, dict):
                    for target_puuid, dmg_info in damage_made.items():
                        if isinstance(dmg_info, dict):
                            data["headshots"] += dmg_info.get("headshots", 0)
                            data["bodyshots"] += dmg_info.get("bodyshots", 0)
                            data["legshots"] += dmg_info.get("legshots", 0)
                            data["total_damage"] += dmg_info.get("damage", 0)

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
        acs = round(data["score_sum"] / data["total_rounds"], 1) if data["total_rounds"] > 0 else 0

        sorted_maps = sorted(data["maps"].items(), key=lambda x: x[1]["played"], reverse=True)[:5]
        sorted_weapons = sorted(data["weapons"].items(), key=lambda x: x[1], reverse=True)[:10]
        sorted_agents = sorted(data["agents"].items(), key=lambda x: x[1], reverse=True)
        main_agent = sorted_agents[0][0] if sorted_agents else "Yok"

        return {
            "kills": data["kills"], "deaths": data["deaths"], "assists": data["assists"],
            "headshots": data["headshots"], "bodyshots": data["bodyshots"], "legshots": data["legshots"],
            "hs_rate": hs_rate, "kd": kd_ratio, "adr": adr, "acs": acs,
            "total_damage": data["total_damage"], "total_rounds": data["total_rounds"],
            "wins": data["wins"], "losses": data["losses"],
            "main_agent": main_agent, "top_agents": sorted_agents,
            "top_maps": sorted_maps, "top_weapons": sorted_weapons, "total_matches": data["total_matches"]
        }

# =====================================================================
# 5. SAYFALANDIRMA (3 SAYFALI VIEW)
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
            if not acc_data or not isinstance(acc_data, dict) or "data" not in acc_data:
                return await msg.edit(content=f"❌ Riot hesabı bulunamadı.")

            acc = acc_data["data"]
            if not acc or not isinstance(acc, dict):
                return await msg.edit(content=f"❌ API'den geçersiz veri döndü.")

            GlobalDatabase.register_user(discord_id_input, acc.get("puuid"), acc.get("name"), acc.get("tag"), (acc.get("region") or "eu").lower())
            await msg.edit(content=f"✅ Kayıt Başarılı! Artık `v!stats` komutunu kullanabilirsin.")

    @commands.command(name="stats", aliases=["istatistik", "profil"])
    async def stats_command(self, ctx, *, hedef: str = None):
        target_id = str(ctx.author.id)
        
        if hedef:
            cleaned_target = hedef.strip("<@!>")
            if cleaned_target.isdigit():
                target_id = cleaned_target

        target_db = GlobalDatabase.get_user(target_id)
        
        if not target_db:
            if target_id != str(ctx.author.id):
                return await ctx.send(f"❌ Belirttiğin kullanıcı sisteme kayıtlı değil.")
            else:
                return await ctx.send("🔒 Bu komutu kullanmak için kayıt olmalısın. Örnek: `v!register [Discord ID] [İsim#Tag]`")

        target_name = target_db.get("name")
        target_tag = target_db.get("tag")
        target_puuid = target_db.get("puuid")
        target_region = target_db.get("region", "eu")

        loading_msg = await ctx.send(f"Analiz ediliyor...")

        try:
            async with aiohttp.ClientSession() as session:
                if not target_puuid:
                    acc_init = await self.api.get_account(session, target_name, target_tag)
                    if acc_init and isinstance(acc_init, dict) and "data" in acc_init:
                        acc_init_data = acc_init["data"]
                        if acc_init_data and isinstance(acc_init_data, dict):
                            target_puuid = acc_init_data.get("puuid")
                            target_region = (acc_init_data.get("region") or "eu").lower()
                            GlobalDatabase.register_user(target_id, target_puuid, target_name, target_tag, target_region)

                acc = await self.api.get_account(session, target_name, target_tag)
                if not acc or not isinstance(acc, dict) or "data" not in acc:
                    return await loading_msg.edit(content=f"❌ Riot hesabı bulunamadı veya API yanıt vermedi.")

                account_data = acc.get("data")
                if not account_data or not isinstance(account_data, dict):
                    return await loading_msg.edit(content=f"❌ Oyuncu bilgileri alınamadı.")

                title = account_data.get("account_title", "Unvansız")
                level = account_data.get("account_level", 0)
                card_obj = account_data.get("card")
                card_large = card_obj.get("large", "") if isinstance(card_obj, dict) else ""

                mmr = await self.api.get_mmr(session, target_region, target_puuid)
                rank_name, elo = "Derecesiz", 0
                if mmr and isinstance(mmr, dict) and "data" in mmr:
                    mmr_data = mmr["data"]
                    if mmr_data and isinstance(mmr_data, dict) and mmr_data.get("current_data"):
                        current_data = mmr_data["current_data"]
                        if current_data and isinstance(current_data, dict):
                            rank_name = current_data.get("currenttierpatched", "Derecesiz")
                            elo = current_data.get("ranking_in_tier", 0)

                matches = await self.api.get_matches(session, target_region, target_puuid, limit=15)
                match_data = []
                if matches and isinstance(matches, dict) and "data" in matches:
                    match_data = matches["data"]

                if not match_data or not isinstance(match_data, list):
                    return await loading_msg.edit(content=f"❌ Maç verisi bulunamadı.")

                stats = StatsEngine.analyze(match_data, target_puuid)

                # ================= PAGE 1: GENEL BAKIŞ =================
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

                combat_text1 = (
                    f"**K/D/A:** `{stats['kills']}` / `{stats['deaths']}` / `{stats['assists']}`\n"
                    f"**K/D Oranı:** `{stats['kd']}`\n"
                    f"**HS Oranı:** `% {stats['hs_rate']}`"
                )
                embed1.add_field(name="Çatışma Analizi", value=combat_text1, inline=False)

                map_text = ""
                for i, (m_name, m_data) in enumerate(stats['top_maps'], 1):
                    wins = m_data["won"]
                    played = m_data["played"]
                    wr = int((wins / played) * 100) if played > 0 else 0
                    map_text += f"{i}. **{m_name}**: %{wr} WR `({wins}W / {played} Maç)`\n"
                embed1.add_field(name="En Çok Oynanan Haritalar", value=map_text or "Veri yok.", inline=True)

                wep_text1 = ""
                for i, (w_name, w_kills) in enumerate(stats['top_weapons'][:3], 1):
                    wep_text1 += f"{i}. **{w_name}** - `{w_kills} Kill`\n"
                embed1.add_field(name="En İyi Silahlar", value=wep_text1 or "Veri yok.", inline=True)

                embed1.set_footer(text="Sayfa 1/3 • V-Tracker.gg Genel Bakış")

                # ================= PAGE 2: TEKNİK ÇATIŞMA & HASAR METRİKLERİ =================
                embed2 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description=f"İleri Düzey Çatışma, Hasar ve Vuruş Dağılımı",
                    color=0x00F0FF
                )
                if card_large:
                    embed2.set_thumbnail(url=card_large)

                tech_combat = (
                    f"**Tur Başına Ortalama Hasar (ADR):** `{stats['adr']}`\n"
                    f"**Ortalama Çatışma Skoru (ACS):** `{stats['acs']}`\n"
                    f"**Toplam Verilen Hasar:** `{stats['total_damage']:,}` HP\n"
                    f"**Analiz Edilen Toplam Tur:** `{stats['total_rounds']}` Tur"
                )
                embed2.add_field(name="Hasar and Performans Metrikleri", value=tech_combat, inline=False)

                accuracy_text = (
                    f"**Kafatası (Headshot):** `{stats['headshots']}` vuruş\n"
                    f"**Gövde (Bodyshot):** `{stats['bodyshots']}` vuruş\n"
                    f"**Bacak (Legshot):** `{stats['legshots']}` vuruş\n"
                    f"**Genel İsabet Oranı:** `% {stats['hs_rate']}`"
                )
                embed2.add_field(name="Vuruş Bölgesi Dağılımı", value=accuracy_text, inline=False)

                match_wl = (
                    f"**Kazanılan Maç:** `{stats['wins']} Win`\n"
                    f"**Kaybedilen Maç:** `{stats['losses']} Loss`\n"
                    f"**Kazanma Oranı (Winrate):** `% {int((stats['wins'] / stats['total_matches']) * 100) if stats['total_matches'] > 0 else 0}`"
                )
                embed2.add_field(name="Maç Sonuç Özeti", value=match_wl, inline=False)

                embed2.set_footer(text="Sayfa 2/3 • V-Tracker.gg Teknik Hasar Analizi")

                # ================= PAGE 3: DERİN AJAN VE SİLAH DAĞILIMI =================
                embed3 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description=f"Kapsamlı Ajan Kullanım ve Silah Performans Dökümü",
                    color=0x00F0FF
                )
                if card_large:
                    embed3.set_thumbnail(url=card_large)

                all_agents_text = ""
                for i, (agent_name, agent_count) in enumerate(stats['top_agents'], 1):
                    all_agents_text += f"{i}. **{agent_name}**: `{agent_count} Maç`\n"
                embed3.add_field(name="Tüm Oynanan Ajanlar", value=all_agents_text or "Veri yok.", inline=True)

                all_weaps_text = ""
                for i, (w_name, w_kills) in enumerate(stats['top_weapons'], 1):
                    all_weaps_text += f"{i}. **{w_name}**: `{w_kills} Kill`\n"
                embed3.add_field(name="Detaylı Silah Kill Listesi", value=all_weaps_text or "Veri yok.", inline=True)

                embed3.set_footer(text="Sayfa 3/3 • V-Tracker.gg Derinlemesine İstatistikler")

                view = StatsPaginationView([embed1, embed2, embed3])
                await loading_msg.edit(content=None, embed=embed1, view=view)

        except Exception as e:
            logger.error(f"Stats Hatası: {e}", exc_info=True)
            await loading_msg.edit(content=f"❌ Hata oluştu: `{e}`")

async def setup(bot):
    await bot.add_cog(VTrackerSystem(bot))