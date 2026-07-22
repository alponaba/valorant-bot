import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import json
import os

DATA_FILE = "registered_users.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

class LastMatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.API_KEY = getattr(bot, "henrik_api_key", "HDEv-e534fbfe-c3c4-4f21-bccc-54eeeb39fd27")
        self.CYAN = 0x00F0FF
        self.GREEN = 0x00FF66
        self.RED = 0xFF3333

    @commands.command(name="lastmatch", aliases=["sonmac", "sonmaç", "last"])
    async def lastmatch(self, ctx):
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

        loading = await ctx.send(f"🔍 **{name}#{tag}** son maç verileri çekiliyor...")

        async with aiohttp.ClientSession() as session:
            puuid = None
            region = "eu"
            match_data = None

            acc_url = f"https://api.henrikdev.xyz/val/v1/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
            try:
                async with session.get(acc_url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        acc_json = await resp.json()
                        acc_data = acc_json.get("data", {})
                        puuid = acc_data.get("puuid")
                        region = (acc_data.get("region") or "eu").lower()
            except Exception:
                pass

            regions_to_try = [region, "eu", "tr"]
            regions_to_try = list(dict.fromkeys([r.lower() for r in regions_to_try]))

            for reg in regions_to_try:
                if puuid:
                    matches_url = f"https://api.henrikdev.xyz/val/v3/by-puuid/matches/{reg}/{puuid}"
                else:
                    matches_url = f"https://api.henrikdev.xyz/val/v3/matches/{reg}/pc/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"

                try:
                    async with session.get(matches_url, headers=headers, params=params) as resp:
                        if resp.status == 200:
                            m_json = await resp.json()
                            m_list = m_json.get("data", [])
                            if isinstance(m_list, list) and len(m_list) > 0:
                                match_data = m_list[0]
                                region = reg
                                break
                            elif isinstance(m_list, dict):
                                matches = m_list.get("matches", [])
                                if matches:
                                    match_data = matches[0]
                                    region = reg
                                    break
                except Exception:
                    continue

        if not match_data:
            await loading.edit(content="❌ Son maç verisi bulunamadı veya API yanıt vermedi.")
            return

        metadata = match_data.get("metadata", {})
        map_name = metadata.get("map", "Bilinmiyor")
        mode = metadata.get("mode", "Bilinmiyor")
        game_length = metadata.get("game_length", 0)
        minutes = game_length // 60
        seconds = game_length % 60

        players = match_data.get("players", {}).get("all_players", [])
        target_player = None
        for p in players:
            if puuid and p.get("puuid") == puuid:
                target_player = p
                break
            elif p.get("name", "").lower() == name.lower() and p.get("tag", "").lower() == tag.lower():
                target_player = p
                break

        if not target_player:
            await loading.edit(content="❌ Oyuncu bu maçın katılımcıları arasında bulunamadı.")
            return

        team_id = target_player.get("team", "").lower()
        stats = target_player.get("stats", {})
        kills = stats.get("kills", 0)
        deaths = stats.get("deaths", 0)
        assists = stats.get("assists", 0)
        score = stats.get("score", 0)
        agent = target_player.get("character", "Bilinmiyor")

        teams = match_data.get("teams", {})
        won = False
        my_team_rounds = 0
        enemy_rounds = 0

        if isinstance(teams, dict):
            red_team = teams.get("red", {})
            blue_team = teams.get("blue", {})
            
            if team_id == "red":
                won = red_team.get("won", False)
                my_team_rounds = red_team.get("rounds_won", 0)
                enemy_rounds = blue_team.get("rounds_won", 0)
            else:
                won = blue_team.get("won", False)
                my_team_rounds = blue_team.get("rounds_won", 0)
                enemy_rounds = red_team.get("rounds_won", 0)

        status_text = "🎉 KAZANDI (VICTORY)" if won else "💀 KAYBETTİ (DEFEAT)"
        embed_color = self.GREEN if won else self.RED

        kd = round(kills / deaths, 2) if deaths > 0 else float(kills)

        embed = discord.Embed(
            title=f"🎮 SON MAÇ ANALİZİ | {name}#{tag}",
            description=f"**{status_text}**\nHarita: **{map_name}** | Mod: **{mode}**",
            color=embed_color
        )

        embed.add_field(
            name="📊 Maç Skoru & Süre",
            value=f"• **Skor:** `{my_team_rounds} - {enemy_rounds}`\n• **Süre:** `{minutes} dk {seconds} sn`",
            inline=False
        )

        embed.add_field(
            name="🎯 Oyuncu İstatistikleri",
            value=f"• **Ajan:** `{agent}`\n• **K / D / A:** `{kills} / {deaths} / {assists}`\n• **K/D Oranı:** `{kd}`\n• **Skor:** `{score}`",
            inline=False
        )

        embed.set_footer(text=f"V-Tracker.gg • Bölge: {region.upper()}")
        await loading.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(LastMatch(bot))