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

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CYAN = 0x00F0FF

    @property
    def API_KEY(self):
        return getattr(self.bot, "henrik_api_key", "HDEv-e534fbfe-c3c4-4f21-bccc-54eeeb39fd27")

    @commands.command(name="leaderboard", aliases=["lb", "sıralama"])
    async def leaderboard(self, ctx):
        data = load_data()
        if not data:
            await ctx.send("❌ Henüz sisteme kayıtlı kimse yok!")
            return

        loading = await ctx.send("🏆 Liderlik tablosu hazırlanıyor...")

        leaderboard_data = []
        headers = {"Authorization": self.API_KEY} if self.API_KEY else {}

        async with aiohttp.ClientSession() as session:
            for user_id, user_info in data.items():
                riot_id = user_info.get("riot_id", "")
                v_coins = user_info.get("v_coins", 0)
                
                if "#" not in riot_id:
                    continue
                
                name, tag = riot_id.split("#", 1)
                name = name.strip()
                tag = tag.strip()

                elo = 0
                tier = "Unranked"
                rr = 0
                region = "eu"
                puuid = None

                encoded_name = urllib.parse.quote(name, safe='')
                encoded_tag = urllib.parse.quote(tag, safe='')

                try:
                    acc_url = f"https://api.henrikdev.xyz/val/v1/account/{encoded_name}/{encoded_tag}"
                    async with session.get(acc_url, headers=headers) as resp:
                        if resp.status == 200:
                            acc_json = await resp.json()
                            acc_data = acc_json.get("data", {})
                            puuid = acc_data.get("puuid")
                            region = (acc_data.get("region") or "eu").lower()

                    regions_to_try = list(dict.fromkeys([region, "eu", "tr"]))

                    for reg in regions_to_try:
                        if puuid:
                            mmr_url = f"https://api.henrikdev.xyz/val/v2/by-puuid/mmr/{reg}/{puuid}"
                        else:
                            mmr_url = f"https://api.henrikdev.xyz/val/v2/mmr/{reg}/{encoded_name}/{encoded_tag}"
                        
                        async with session.get(mmr_url, headers=headers) as resp:
                            if resp.status == 200:
                                d = (await resp.json()).get("data", {})
                                if d:
                                    elo = d.get("elo", 0)
                                    tier = d.get("currenttierpatched", "Unranked")
                                    rr = d.get("ranking_in_tier", 0)
                                    break
                except Exception:
                    pass

                leaderboard_data.append({
                    "name": f"{name}#{tag}",
                    "elo": elo,
                    "tier": tier,
                    "rr": rr,
                    "v_coins": v_coins
                })

        if not leaderboard_data:
            await loading.edit(content="❌ Veriler çekilemedi.")
            return

        leaderboard_data = sorted(leaderboard_data, key=lambda x: x["elo"], reverse=True)

        desc = ""
        for idx, player in enumerate(leaderboard_data[:10], start=1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
            desc += f"{medal} **{player['name']}**\n"
            desc += f"└ Rank: `{player['tier']}` (`{player['rr']} RR`) | V-Coin: `🪙 {player['v_coins']}`\n\n"

        embed = discord.Embed(
            title="🏆 V-TRACKER.GG | GLOBAL LİDERLİK TABLOSU",
            description=desc,
            color=self.CYAN
        )
        embed.set_footer(text="Sadece bota kayıtlı olan kullanıcılar sıralanmıştır.")
        await loading.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))