import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os
from collections import Counter

DATA_FILE = "registered_users.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

class Coach(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # BURASI ÇOK ÖNEMLİ: Ortak anahtar engellendiği için kendi anahtarınızı buraya yazmalısınız.
        self.API_KEY = getattr(bot, "HDEV-e534fbfe-c3c4-4f21-bccc-54eeb39fd27d", "HDEV-e534fbfe-c3c4-4f21-bccc-54eeb39fd27d")
        self.CYAN = 0x00F0FF

    @commands.command(name="coach", aliases=["koç", "analiz"])
    async def coach(self, ctx):
        user_id = str(ctx.author.id)
        data = load_data()

        if user_id not in data:
            await ctx.send("❌ Önce kayıt olmalısın! Örnek: `v!register İsim#Tag`")
            return

        riot_id = data[user_id]["riot_id"]
        if "#" not in riot_id:
            await ctx.send("❌ Kayıtlı Riot ID formatı hatalı.")
            return

        name, tag = riot_id.split("#", 1)
        name = name.strip()
        tag = tag.strip()
        
        headers = {"Authorization": self.API_KEY}
        params = {"api_key": self.API_KEY}

        loading = await ctx.send(f"🤖 **{name}#{tag}** için Riot API'ye bağlanılıyor...")

        async with aiohttp.ClientSession() as session:
            puuid = None
            region = "eu"
            tier = "Unranked"
            rr = 0
            matches = []

            # 1. Account API İstemi ve Hata Kontrolü
            acc_url = f"https://api.henrikdev.xyz/val/v1/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
            async with session.get(acc_url, headers=headers, params=params) as resp:
                print(f"[API DEBUG] Account Status: {resp.status}")
                if resp.status == 200:
                    acc_json = await resp.json()
                    acc_data = acc_json.get("data", {})
                    puuid = acc_data.get("puuid")
                    region = (acc_data.get("region") or "eu").lower()
                else:
                    err_text = await resp.text()
                    print(f"[API ERROR] Account API Hatası: {resp.status} - {err_text}")
                    if resp.status in [401, 403, 429]:
                        await loading.edit(content=f"❌ **API Yetki veya Kota Hatası ({resp.status})!** Kullandığın API anahtarı geçersiz veya engellenmiş. Lütfen geçerli bir anahtar gir.")
                        return

            regions_to_try = [region, "eu", "tr"]
            regions_to_try = list(dict.fromkeys([r.lower() for r in regions_to_try]))

            # 2. MMR API İstemi
            for reg in regions_to_try:
                if puuid:
                    mmr_url = f"https://api.henrikdev.xyz/val/v2/by-puuid/mmr/{reg}/{puuid}"
                else:
                    mmr_url = f"https://api.henrikdev.xyz/val/v2/mmr/{reg}/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
                
                async with session.get(mmr_url, headers=headers, params=params) as resp:
                    print(f"[API DEBUG] MMR Status ({reg}): {resp.status}")
                    if resp.status == 200:
                        d = (await resp.json()).get("data", {})
                        if d and d.get("currenttierpatched"):
                            tier = d.get("currenttierpatched", "Unranked")
                            rr = d.get("ranking_in_tier", 0)
                            region = reg
                            break

            # 3. Matches API İstemi
            for reg in regions_to_try:
                if puuid:
                    matches_url = f"https://api.henrikdev.xyz/val/v3/by-puuid/matches/{reg}/{puuid}"
                else:
                    matches_url = f"https://api.henrikdev.xyz/val/v3/matches/{reg}/pc/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"

                async with session.get(matches_url, headers=headers, params=params) as resp:
                    print(f"[API DEBUG] Matches Status ({reg}): {resp.status}")
                    if resp.status == 200:
                        m_json = await resp.json()
                        m_data = m_json.get("data", [])
                        if isinstance(m_data, list):
                            matches = m_data
                        elif isinstance(m_data, dict):
                            matches = m_data.get("matches", [])
                        if matches:
                            region = reg
                            break

        # Veri İşleme
        agents = []
        total_kills = 0
        total_deaths = 0
        total_assists = 0

        for match in matches:
            players = match.get("players", {}).get("all_players", [])
            for p in players:
                is_match = False
                if puuid and p.get("puuid") == puuid:
                    is_match = True
                elif p.get("name", "").lower() == name.lower() and p.get("tag", "").lower() == tag.lower():
                    is_match = True

                if is_match:
                    agents.append(p.get("character", "Bilinmiyor"))
                    stats = p.get("stats", {})
                    total_kills += stats.get("kills", 0)
                    total_deaths += stats.get("deaths", 0)
                    total_assists += stats.get("assists", 0)

        main_agent = Counter(agents).most_common(1)[0][0] if agents else "Bilinmiyor"
        avg_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else float(total_kills)
        match_count = len(matches) if matches else 1
        avg_kda = f"{round(total_kills/match_count, 1)} / {round(total_deaths/match_count, 1)} / {round(total_assists/match_count, 1)}" if matches else "0 / 0 / 0"

        advice_list = []
        if avg_kd < 1.0:
            advice_list.append("• **Düello ve Pozisyon:** K/D oranın 1.0 altında. İlk temaslarda crosshair placement ve peek açılışlarına dikkat etmelisin.")
        else:
            advice_list.append("• **Bireysel Performans:** K/D oranın gayet iyi. Bu formu takım oyununa yansıtmalısın.")

        if main_agent.lower() in ["jett", "reyna", "neon", "raze"]:
            advice_list.append(f"• **Düellocu Rolü ({main_agent}):** Alan açarken takımınla koordineli olmalısın.")
        elif main_agent.lower() in ["omen", "viper", "brimstone", "astra", "clove"]:
            advice_list.append(f"• **Kontrolör Rolü ({main_agent}):** Smoke sürelerini takımın atak temposuna göre ayarlamalısın.")
        else:
            advice_list.append(f"• **Ajan Kullanımı ({main_agent}):** Seçtiğin ajanın görevlerini optimize etmelisin.")

        advice_list.append("• **Taktiksel Öneri:** Harita kontrolünü ele almak için yeteneklerini takım arkadaşlarınla kombine et.")

        advice_str = "\n".join(advice_list)

        embed = discord.Embed(
            title=f"🧠 AI DESTEKLİ KOÇLUK & ANALİZ RAPORU",
            description=f"Hedef Oyuncu: **{name}#{tag}** | Rank: **{tier} ({rr} RR)**",
            color=self.CYAN
        )
        embed.add_field(
            name="📊 Performans Özet Metrikleri",
            value=f"• **Main Ajan:** `{main_agent}`\n• **Ortalama K/D:** `{avg_kd}`\n• **Maç Başı K/D/A:** `{avg_kda}`\n• **İncelenen Maç:** `{len(matches)}`",
            inline=False
        )
        embed.add_field(
            name="🎯 Yapay Zeka Taktiksel Tavsiyeleri",
            value=advice_str,
            inline=False
        )
        embed.set_footer(text=f"V-Tracker.gg AI Coach • Bölge: {region.upper()}")
        await loading.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Coach(bot))