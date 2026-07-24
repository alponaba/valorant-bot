# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Performans Optimize Edilmiş, Güvenlikli Valorant & Ekonomi Cogs
Prefix: v! | Slash Komut Desteği
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import urllib.parse
import json
import os
import logging
import time
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

# =====================================================================
# 1. LOGGING VE SABİTLER YAPILANDIRMASI
# =====================================================================

logger = logging.getLogger("VTracker.System")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

GLOBAL_DB_FILE = os.path.join(PROJECT_ROOT, "global_registered_users.json")
ECONOMY_DB_FILE = os.path.join(PROJECT_ROOT, "economy.json")
API_KEY = "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"

# Güvenlik 1: Eşzamanlı (Concurrent) Dosya Erişim Kilidi (Thread Safety)
FILE_LOCK = asyncio.Lock()

# =====================================================================
# 2. GÜVENLİK VE YARDIMCI FONKSİYONLAR
# =====================================================================

def is_valid_image_url(url: str) -> bool:
    """Güvenlik 2: URL Sanitization & Görsel / GIF Format Doğrulaması"""
    regex = r"^https?://[^\s<>'\"{}|\^~\[\]`]+\.(png|jpg|jpeg|gif|webp)(\?.*)?$"
    return bool(re.match(regex, url, re.IGNORECASE))

# =====================================================================
# 3. VERİTABANI YÖNETİCİSİ (TEMP YEDEKLİ VE KİLİTLİ)
# =====================================================================

class GlobalDatabase:
    @staticmethod
    async def _save_json_atomic(filepath: str, data: Dict[str, Any]) -> None:
        async with FILE_LOCK:
            temp_file = f"{filepath}.tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                os.replace(temp_file, filepath)
            except Exception as e:
                logger.error(f"Dosya güvenli kaydetme hatası ({filepath}): {e}")

    @staticmethod
    def load_db() -> Dict[str, Any]:
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.error(f"Veritabanı okuma hatası (Yedekten kurtarma deneniyor): {e}")
                if os.path.exists(f"{GLOBAL_DB_FILE}.tmp"):
                    try:
                        with open(f"{GLOBAL_DB_FILE}.tmp", "r", encoding="utf-8") as f:
                            return json.loads(f.read())
                    except Exception:
                        pass
        return {}

    @staticmethod
    async def save_db(data: Dict[str, Any]) -> None:
        await GlobalDatabase._save_json_atomic(GLOBAL_DB_FILE, data)

    @staticmethod
    def load_economy() -> Dict[str, Any]:
        if os.path.exists(ECONOMY_DB_FILE):
            try:
                with open(ECONOMY_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.error(f"Ekonomi veritabanı okuma hatası: {e}")
        return {}

    @staticmethod
    def get_user_balance(discord_id: str) -> int:
        economy = GlobalDatabase.load_economy()
        discord_id_str = str(discord_id)
        if discord_id_str in economy and "balance" in economy[discord_id_str]:
            return economy[discord_id_str]["balance"]
        db = GlobalDatabase.load_db()
        return db.get(discord_id_str, {}).get("v_coins", 0)

    @staticmethod
    async def update_user_balance(discord_id: str, new_balance: int) -> None:
        discord_id_str = str(discord_id)
        economy = GlobalDatabase.load_economy()
        if discord_id_str not in economy:
            economy[discord_id_str] = {}
        economy[discord_id_str]["balance"] = new_balance
        await GlobalDatabase._save_json_atomic(ECONOMY_DB_FILE, economy)

        db = GlobalDatabase.load_db()
        if discord_id_str in db:
            db[discord_id_str]["v_coins"] = new_balance
            await GlobalDatabase.save_db(db)

    @staticmethod
    async def register_user(discord_id: str, puuid: str, name: str, tag: str, region: str, dc_name: str = "") -> None:
        db = GlobalDatabase.load_db()
        discord_id_str = str(discord_id)
        existing_cosmetics = db.get(discord_id_str, {}).get("cosmetics", {
            "color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []
        })
        
        db[discord_id_str] = {
            "puuid": puuid or "",
            "name": name or "",
            "tag": tag or "",
            "region": region or "eu",
            "dc_name": dc_name or db.get(discord_id_str, {}).get("dc_name", "Bilinmeyen"),
            "v_coins": db.get(discord_id_str, {}).get("v_coins", 0),
            "cosmetics": existing_cosmetics,
            "updated_at": datetime.utcnow().isoformat()
        }
        await GlobalDatabase.save_db(db)

    @staticmethod
    async def unregister_user(discord_id: str) -> bool:
        db = GlobalDatabase.load_db()
        discord_id_str = str(discord_id)
        if discord_id_str in db:
            del db[discord_id_str]
            await GlobalDatabase.save_db(db)
            return True
        return False

    @staticmethod
    def get_user(discord_id: str) -> Optional[Dict[str, Any]]:
        db = GlobalDatabase.load_db()
        return db.get(str(discord_id))

# =====================================================================
# 4. VALORANT API İSTEMCİSİ (TTL CACHE & AUTO RETRY ENTEGRELİ)
# =====================================================================

class ValorantAPI:
    def __init__(self):
        self.base_url = "https://api.henrikdev.xyz"
        self.headers = {"User-Agent": "V-Tracker-Bot/8.0", "Authorization": API_KEY}
        self.timeout = aiohttp.ClientTimeout(total=12)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 180  # 3 Dakika Bellekte Tutma Süresi

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self._cache:
            timestamp, data = self._cache[key]["time"], self._cache[key]["data"]
            if time.time() - timestamp < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {"time": time.time(), "data": data}

    def _fix_region(self, region: str) -> str:
        if not region:
            return "eu"
        r = region.lower()
        return "eu" if r in ["tr", "ru"] else r

    async def _get_with_retry(self, session: aiohttp.ClientSession, url: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        cached = self._get_cache(url)
        if cached:
            return cached

        for attempt in range(retries):
            try:
                async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cache(url, data)
                        return data
                    elif response.status in [429, 500, 502, 503, 504]:
                        await asyncio.sleep(1.5 * (attempt + 1))
                    else:
                        logger.warning(f"API HTTP Hata Kodu ({response.status}) - URL: {url}")
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == retries - 1:
                    logger.error(f"API İstek Hatası ({url}): {e}")
                await asyncio.sleep(1.5)
        return None

    async def get_account(self, session, name: str, tag: str):
        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"{self.base_url}/valorant/v1/account/{encoded_name}/{encoded_tag}"
        return await self._get_with_retry(session, url)

    async def get_mmr(self, session, region: str, puuid: str):
        fixed_reg = self._fix_region(region)
        url = f"{self.base_url}/valorant/v2/by-puuid/mmr/{fixed_reg}/{puuid}"
        return await self._get_with_retry(session, url)

    async def get_matches(self, session, region: str, puuid: str, limit: int = 15):
        fixed_reg = self._fix_region(region)
        url = f"{self.base_url}/valorant/v3/by-puuid/matches/{fixed_reg}/{puuid}?size={limit}"
        return await self._get_with_retry(session, url)

# =====================================================================
# 5. İSTATİSTİK ANALİZ MOTORU
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
                
                hs = stats.get("headshots", 0)
                bs = stats.get("bodyshots", 0)
                ls = stats.get("legshots", 0)
                
                dmg = 0
                raw_dmg = player.get("damage_made")
                if isinstance(raw_dmg, (int, float)):
                    dmg = int(raw_dmg)
                elif isinstance(raw_dmg, dict):
                    for _, dmg_info in raw_dmg.items():
                        if isinstance(dmg_info, dict):
                            hs += dmg_info.get("headshots", 0)
                            bs += dmg_info.get("bodyshots", 0)
                            ls += dmg_info.get("legshots", 0)
                            dmg += dmg_info.get("damage", 0)
                elif isinstance(stats.get("damage"), (int, float)):
                    dmg = int(stats.get("damage"))

                data["headshots"] += hs
                data["bodyshots"] += bs
                data["legshots"] += ls
                data["total_damage"] += dmg

                rounds_played = metadata.get("rounds_played", 1)
                if not rounds_played or rounds_played < 1: 
                    rounds_played = 1
                data["total_rounds"] += rounds_played

                agent = player.get("character", "Bilinmiyor")
                data["agents"][agent] = data["agents"].get(agent, 0) + 1

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

        # Performans Rozeti Belirleme
        kd_badge = "🟢" if kd_ratio >= 1.2 else ("🟡" if kd_ratio >= 0.9 else "🔴")

        sorted_maps = sorted(data["maps"].items(), key=lambda x: x[1]["played"], reverse=True)[:5]
        sorted_weapons = sorted(data["weapons"].items(), key=lambda x: x[1], reverse=True)[:10]
        sorted_agents = sorted(data["agents"].items(), key=lambda x: x[1], reverse=True)
        main_agent = sorted_agents[0][0] if sorted_agents else "Yok"

        return {
            "kills": data["kills"], "deaths": data["deaths"], "assists": data["assists"],
            "headshots": data["headshots"], "bodyshots": data["bodyshots"], "legshots": data["legshots"],
            "hs_rate": hs_rate, "kd": kd_ratio, "kd_badge": kd_badge, "adr": adr, "acs": acs,
            "total_damage": data["total_damage"], "total_rounds": data["total_rounds"],
            "wins": data["wins"], "losses": data["losses"],
            "main_agent": main_agent, "top_agents": sorted_agents,
            "top_maps": sorted_maps, "top_weapons": sorted_weapons, "total_matches": data["total_matches"]
        }

# =====================================================================
# 6. SAYFALANDIRMA VIEW SINIFLARI
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

class RegisterBoardPaginationView(discord.ui.View):
    def __init__(self, data_list: List[Dict[str, Any]], author_id: int):
        super().__init__(timeout=60)
        self.data_list = data_list
        self.author_id = author_id
        self.current_page = 0
        self.per_page = 15
        self.max_pages = max(1, (len(data_list) + self.per_page - 1) // self.per_page)

    def create_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data_list[start:end]

        embed = discord.Embed(
            title="📋 V-Tracker | Global Kayıtlı Oyuncular ve V-Coin Sıralaması",
            description=f"Sistemde toplam **{len(self.data_list)}** kayıtlı kullanıcı bulunuyor.\n",
            color=0x00FFFF
        )

        if not page_data:
            embed.description += "\n*Henüz kayıtlı bir oyuncu bulunmuyor.*"
        else:
            board_text = ""
            for idx, user in enumerate(page_data, start=start + 1):
                board_text += f"`{idx}.` **{user['dc_name']}** — `{user['riot_id']}` | 💰 `{user['balance']:,} V-Coin`\n"
            embed.add_field(name="Sıralama Listesi (Top V-Coin)", value=board_text, inline=False)

        embed.set_footer(text=f"Sayfa {self.current_page + 1}/{self.max_pages} • V-Tracker.gg")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu sıralama butonlarını sadece komutu çalıştıran kişi kullanabilir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Önceki", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Sonraki", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

# =====================================================================
# 7. BİRLEŞTİRİLMİŞ MAIN COG
# =====================================================================

class VTrackerSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = ValorantAPI()

    # --- MERKEZİ HATA YÖNETİCİSİ (GLOBAL COG ERROR HANDLER) ---
    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = round(error.retry_after, 1)
            embed = discord.Embed(
                title="⏳ Yavaşla Şampiyon!",
                description=f"Bu komutu tekrar kullanabilmek için **{seconds} saniye** beklemelisin.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Eksik parametre girdiniz! Doğru kullanım için `{ctx.prefix}help` inceleyin.")
        else:
            logger.error(f"Komut Hatası ({ctx.command}): {error}")

    # --- KOMUT 1: v!register ---
    @commands.hybrid_command(name="register", aliases=["kayit"], description="Riot hesabını (İsim#Tag) Discord hesabına bağlar.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def register_command(self, ctx, *, riot_id: str = None):
        await ctx.defer()
        
        if not riot_id or "#" not in riot_id or len(riot_id.split("#")) != 2:
            embed = discord.Embed(
                title="❌ Hatalı Format!",
                description=f"Lütfen Riot ID'nizi `OyuncuAdı#Etiket` şeklinde girin.\n**Örnek:** `{ctx.prefix}register Alperen#TR1`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        name, tag = [x.strip() for x in riot_id.split("#")]
        clean_riot_id = f"{name}#{tag}"
        user_id_str = str(ctx.author.id)

        existing_user = GlobalDatabase.get_user(user_id_str)
        if existing_user and existing_user.get("name") and existing_user.get("tag"):
            embed = discord.Embed(
                title="⚠️ Zaten Kayıtlısınız!",
                description=f"Discord hesabınız zaten **{existing_user['name']}#{existing_user['tag']}** hesabına bağlı.\nHesabı değiştirmek için önce `{ctx.prefix}unregister` kullanmalısınız.",
                color=discord.Color.gold()
            )
            return await ctx.send(embed=embed)

        async with aiohttp.ClientSession() as session:
            acc_data = await self.api.get_account(session, name, tag)
            if not acc_data or not isinstance(acc_data, dict) or "data" not in acc_data:
                embed = discord.Embed(
                    title="❌ Riot Hesabı Bulunamadı",
                    description=f"`{clean_riot_id}` isimli oyuncu Valorant sisteminde bulunamadı.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

            acc = acc_data.get("data", {})
            puuid = acc.get("puuid", "")
            region = (acc.get("region") or "eu").lower()

            await GlobalDatabase.register_user(user_id_str, puuid, name, tag, region, dc_name=ctx.author.name)

            embed = discord.Embed(
                title="✅ Kayıt Başarılı!",
                description=f"**{ctx.author.name}**, Riot hesabınız başarıyla eşlendi:\n🎯 **Riot ID:** `{name}#{tag}`\n🌐 **Bölge:** `{region.upper()}`",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

    # --- KOMUT 2: v!unregister ---
    @commands.hybrid_command(name="unregister", aliases=["kayitsil"], description="Mevcut Riot hesabı bağlantınızı sistemden siler.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unregister_command(self, ctx):
        user_id_str = str(ctx.author.id)
        existing = GlobalDatabase.get_user(user_id_str)

        if not existing or not existing.get("name"):
            return await ctx.send("❌ Sistemde kayıtlı bir Riot hesabınız bulunmuyor.")

        riot_id_str = f"{existing.get('name')}#{existing.get('tag')}"
        await GlobalDatabase.unregister_user(user_id_str)

        embed = discord.Embed(
            title="🗑️ Kayıt Silindi",
            description=f"**{riot_id_str}** hesabı ile olan bağlantınız kaldırıldı.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    # --- KOMUT 3: v!registerboard ---
    @commands.hybrid_command(name="registerboard", aliases=["kayitlistesi"], description="Kayıtlı oyuncuları ve V-Coin sıralamasını listeler.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def registerboard_command(self, ctx):
        all_users = GlobalDatabase.load_db()

        data_list = []
        for uid, udata in all_users.items():
            riot_full = f"{udata.get('name', 'Bilinmiyor')}#{udata.get('tag', '0000')}"
            user_balance = GlobalDatabase.get_user_balance(uid)

            data_list.append({
                "dc_name": udata.get("dc_name", "Bilinmeyen Kullanıcı"),
                "riot_id": riot_full,
                "balance": user_balance
            })

        data_list.sort(key=lambda x: x["balance"], reverse=True)

        view = RegisterBoardPaginationView(data_list, ctx.author.id)
        embed = view.create_embed()
        await ctx.send(embed=embed, view=view)

    # --- KOMUT 4: v!shop ---
    @commands.hybrid_command(name="shop", aliases=["magaza"], description="V-Coin Mağazasını ve profil özelleştirme fiyatlarını gösterir.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def shop_command(self, ctx):
        balance = GlobalDatabase.get_user_balance(ctx.author.id)
        embed = discord.Embed(
            title="🛍️ V-Tracker.gg | V-Coin Profil Özelleştirme Mağazası",
            description=f"Mevcut Bakiyeniz: 💰 **{balance:,} V-Coin**\n\nMağazadan satın alabileceğiniz özelleştirme kategorileri:",
            color=0xFFD700
        )
        embed.add_field(
            name="🎨 Embed Çizgi Rengi — `2,500 V-Coin`",
            value="İstatistik Embed'inizin yan çizgi rengini özelleştirin.\n*(Seçenekler: Altın, Mor, Kırmızı, Yeşil, Siyah, Siber)*",
            inline=False
        )
        embed.add_field(
            name="😀 Özel Profil İkonu / Emoji — `5,000 V-Coin`",
            value="Profil başlığınızın yanına özel bir emoji/rozet ekleyin.\n*(Seçenekler: 🎯, 🔥, 👻, 👑, ⚡, 💎)*",
            inline=False
        )
        embed.add_field(
            name="🖼️ Özel Banner / Fotoğraf — `10,000 V-Coin`",
            value="İstatistik kartınızın altına istediğiniz bir resmin URL bağlantısını ekleyin.",
            inline=False
        )
        embed.add_field(
            name="🎬 Hareketli GIF / Animasyon — `20,000 V-Coin`",
            value="İstatistik kartınızın altına özel hareketli GIF ekleme slotu açın.",
            inline=False
        )
        embed.set_footer(text=f"Satın almak için {ctx.prefix}satinal <ürün> | Özelleştirmek için {ctx.prefix}profil_ayarla")
        await ctx.send(embed=embed)

    # --- KOMUT 5: v!buy ---
    @commands.hybrid_command(name="buy", aliases=["satinal"], description="V-Coin Mağazasından özelleştirme veya slot satın alır.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def buy_command(self, ctx, urun: str):
        user_id = str(ctx.author.id)
        user_db = GlobalDatabase.get_user(user_id)
        
        if not user_db:
            return await ctx.send(f"❌ Mağazayı kullanabilmek için önce `{ctx.prefix}register` ile kayıt olmalısınız.")

        prices = {"renk": 2500, "emoji": 5000, "banner": 10000, "gif": 20000}

        item_key = urun.lower().strip()
        if item_key not in prices:
            return await ctx.send("❌ Geçersiz ürün! Kullanabileceğiniz seçenekler: `renk`, `emoji`, `banner`, `gif`")

        cost = prices[item_key]
        balance = GlobalDatabase.get_user_balance(user_id)

        if balance < cost:
            return await ctx.send(f"❌ Yetersiz bakiye! **{item_key.upper()}** için `{cost:,} V-Coin` gerekiyor. Bakiyeniz: `{balance:,} V-Coin`")

        cosmetics = user_db.get("cosmetics", {"color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []})
        unlocked_list = cosmetics.get("unlocked", [])

        if item_key in unlocked_list:
            return await ctx.send(f"⚠️ **{item_key.upper()}** kilit açma özelliğine zaten sahipsiniz!")

        await GlobalDatabase.update_user_balance(user_id, balance - cost)
        unlocked_list.append(item_key)
        cosmetics["unlocked"] = unlocked_list
        
        all_db = GlobalDatabase.load_db()
        all_db[user_id]["cosmetics"] = cosmetics
        await GlobalDatabase.save_db(all_db)

        embed = discord.Embed(
            title="🎉 Satın Alım Başarılı!",
            description=f"**{item_key.upper()}** kilidi başarıyla açıldı!\n💰 Kalan Bakiye: `{balance - cost:,} V-Coin`\n\nAyarlamak için `{ctx.prefix}profil_ayarla` komutunu kullanabilirsiniz.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # --- KOMUT 6: v!customize ---
    @commands.hybrid_command(name="customize", aliases=["profil_ayarla"], description="Satın aldığınız renk, emoji, banner veya GIF'i profilinize ekler.")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def customize_command(self, ctx, tur: str, degertip: str):
        user_id = str(ctx.author.id)
        all_db = GlobalDatabase.load_db()
        user_db = all_db.get(user_id)

        if not user_db:
            return await ctx.send(f"❌ Profilinizi düzenlemek için önce `{ctx.prefix}register` yapmalısınız.")

        cosmetics = user_db.get("cosmetics", {"color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []})
        unlocked = cosmetics.get("unlocked", [])
        tur_clean = tur.lower().strip()

        if tur_clean not in unlocked and tur_clean != "renk":
            return await ctx.send(f"🔒 **{tur_clean.upper()}** özelliğini kullanmak için önce `{ctx.prefix}satinal {tur_clean}` yapmalısınız.")

        color_map = {
            "altin": "0xFFD700", "mor": "0x9B59B6", "kirmizi": "0xFF0000",
            "yesil": "0x2ECC71", "siyah": "0x111111", "siber": "0x00FFFF"
        }

        if tur_clean == "renk":
            hex_code = color_map.get(degertip.lower(), degertip)
            if not hex_code.startswith("0x") and not hex_code.startswith("#"):
                hex_code = f"0x{hex_code}"
            cosmetics["color"] = hex_code.replace("#", "0x")

        elif tur_clean == "emoji":
            cosmetics["emoji"] = degertip

        elif tur_clean in ["banner", "gif"]:
            # Güvenlik Kontrolü (URL Doğrulama)
            if not is_valid_image_url(degertip):
                return await ctx.send("❌ Geçersiz URL! Lütfen `.png`, `.jpg`, `.jpeg`, `.gif` veya `.webp` ile biten geçerli bir resim bağlantısı girin.")
            cosmetics[tur_clean] = degertip

        all_db[user_id]["cosmetics"] = cosmetics
        await GlobalDatabase.save_db(all_db)

        await ctx.send(f"✅ Profil **{tur_clean.upper()}** özelleştirmesi başarıyla güncellendi!")

    # --- KOMUT 7: v!reset_cosmetics ---
    @commands.hybrid_command(name="reset_cosmetics", aliases=["profil_sifirla"], description="Profilinize eklediğiniz banner, gif veya renk görsellerini varsayılana sıfırlar.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def reset_cosmetics_command(self, ctx):
        user_id = str(ctx.author.id)
        all_db = GlobalDatabase.load_db()
        user_db = all_db.get(user_id)

        if not user_db:
            return await ctx.send("❌ Kayıtlı profiliniz bulunamadı.")

        cosmetics = user_db.get("cosmetics", {})
        unlocked = cosmetics.get("unlocked", [])

        all_db[user_id]["cosmetics"] = {
            "color": "0x00FFFF",
            "emoji": "",
            "banner": "",
            "gif": "",
            "unlocked": unlocked
        }
        await GlobalDatabase.save_db(all_db)

        await ctx.send("✅ Profil görselleriniz ve renkleriniz başarıyla sıfırlandı!")

    # --- KOMUT 8: v!stats ---
    @commands.hybrid_command(name="stats", aliases=["istatistik", "profil"], description="Valorant hesabının 3 sayfalı detaylı analizini gösterir.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stats_command(self, ctx, *, hedef: str = None):
        target_id = str(ctx.author.id)
        
        if hedef:
            cleaned_target = hedef.strip("<@!>")
            if cleaned_target.isdigit():
                target_id = cleaned_target

        target_db = GlobalDatabase.get_user(target_id)
        
        if not target_db or not target_db.get("name"):
            if target_id != str(ctx.author.id):
                return await ctx.send("❌ Belirttiğin kullanıcı sisteme kayıtlı değil.")
            else:
                return await ctx.send(f"🔒 İstatistiklerinizi görmek için önce kayıt olmalısınız.\n**Kullanım:** `{ctx.prefix}register Oyuncu#TAG`")

        target_name = target_db.get("name")
        target_tag = target_db.get("tag")
        target_puuid = target_db.get("puuid")
        target_region = target_db.get("region", "eu")

        loading_msg = await ctx.send("🔍 Valorant sunucularından veriler çekiliyor ve analiz ediliyor...")

        try:
            async with aiohttp.ClientSession() as session:
                acc = await self.api.get_account(session, target_name, target_tag)
                if not acc or not isinstance(acc, dict) or "data" not in acc:
                    return await loading_msg.edit(content="❌ Riot hesabı bulunamadı veya API yanıt vermedi.")

                account_data = acc.get("data", {})
                target_puuid = account_data.get("puuid") or target_puuid
                target_region = (account_data.get("region") or "eu").lower()

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
                match_data = matches.get("data", []) if (matches and isinstance(matches, dict)) else []

                if not match_data or not isinstance(match_data, list):
                    return await loading_msg.edit(content="❌ Son maç verileri bulunamadı veya API kısıtlamasına takıldı.")

                stats = StatsEngine.analyze(match_data, target_puuid)

                # PAGE 1: GENEL BAKIŞ
                embed1 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description=f"Son **{stats['total_matches']} Maçın** Genel Analiz Raporu\nTalep eden: {ctx.author.mention}",
                )
                if card_large:
                    embed1.set_thumbnail(url=card_large)

                embed1.add_field(name="Derece", value=f"`{rank_name}`\n**{elo} RR**", inline=True)
                embed1.add_field(name="Seviye", value=f"`{level}`", inline=True)
                embed1.add_field(name="En İyi Ajan", value=f"`{stats['main_agent']}`", inline=True)

                combat_text1 = (
                    f"**K/D/A:** `{stats['kills']}` / `{stats['deaths']}` / `{stats['assists']}`\n"
                    f"**K/D Oranı:** `{stats['kd']}` {stats['kd_badge']}\n"
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

                # PAGE 2: TEKNİK ÇATIŞMA & HASAR METRİKLERİ
                embed2 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description="İleri Düzey Çatışma, Hasar ve Vuruş Dağılımı",
                )
                if card_large:
                    embed2.set_thumbnail(url=card_large)

                tech_combat = (
                    f"**Tur Başına Ortalama Hasar (ADR):** `{stats['adr']}`\n"
                    f"**Ortalama Çatışma Skoru (ACS):** `{stats['acs']}`\n"
                    f"**Toplam Verilen Hasar:** `{stats['total_damage']:,}` HP\n"
                    f"**Analiz Edilen Toplam Tur:** `{stats['total_rounds']}` Tur"
                )
                embed2.add_field(name="Hasar ve Performans Metrikleri", value=tech_combat, inline=False)

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

                # PAGE 3: DERİN AJAN VE SİLAH DAĞILIMI
                embed3 = discord.Embed(
                    title=f"[{title}] {target_name}#{target_tag}",
                    description="Kapsamlı Ajan Kullanım ve Silah Performans Dökümü",
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
                embed3.add_field(name="En İyi Silahlar Dökümü", value=all_weaps_text or "Veri yok.", inline=True)

                embed3.set_footer(text="Sayfa 3/3 • V-Tracker.gg Ajan & Silah Analizi")

                # KOZMETİK UYGULAMALARI
                embeds = [embed1, embed2, embed3]
                target_cosmetics = target_db.get("cosmetics", {})

                color_hex = target_cosmetics.get("color", "0x00FFFF")
                try:
                    embed_color = int(color_hex, 16)
                except ValueError:
                    embed_color = 0x00FFFF

                custom_emoji = target_cosmetics.get("emoji", "")
                custom_gif = target_cosmetics.get("gif", "")
                custom_banner = target_cosmetics.get("banner", "")

                for emb in embeds:
                    emb.color = embed_color
                    if custom_emoji:
                        emb.title = f"{custom_emoji} {emb.title}"
                    
                    if custom_gif:
                        emb.set_image(url=custom_gif)
                    elif custom_banner:
                        emb.set_image(url=custom_banner)

                await loading_msg.delete()
                view = StatsPaginationView(embeds)
                await ctx.send(embed=embeds[0], view=view)

        except Exception as e:
            logger.error(f"Stats Komut Hatası: {e}")
            await loading_msg.edit(content="❌ İstatistikler çekilirken bir hata oluştu.")

async def setup(bot):
    await bot.add_cog(VTrackerSystem(bot))