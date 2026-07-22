import discord
from discord.ext import commands
import aiohttp
import urllib.parse
import asyncio

class Compare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.API_KEY = getattr(bot, "henrik_api_key", "HDEv-e534fbfe-c3c4-4f21-bccc-54eeeb39fd27")
        self.CYAN = 0x00F0FF

    async def fetch_player_data(self, session, riot_id):
        if "#" not in riot_id:
            return None, "Geçersiz format (`İsim#Tag` olmalı)"
        
        name, tag = riot_id.split("#", 1)
        name = name.strip()
        tag = tag.strip()
        headers = {"Authorization": self.API_KEY}

        # 1. Adım: Account API ile PUUID ve doğru bölgeyi al (Kesin çözüm)
        account_url = f"https://api.henrikdev.xyz/v1/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
        try:
            async with session.get(account_url, headers=headers) as resp:
                if resp.status != 200:
                    return None, f"Riot ID bulunamadı ({riot_id})"
                acc_data = await resp.json()
                data_block = acc_data.get("data", {})
                puuid = data_block.get("puuid")
                region = data_block.get("region", "eu")
        except Exception as e:
            return None, f"Bağlantı hatası: {e}"

        if not puuid:
            return None, f"Oyuncu verisi çözülemedi ({riot_id})"

        # 2. Adım: PUUID ile Güncel MMR (Rank, RR, Elo) verisini çek
        mmr_url = f"https://api.henrikdev.xyz/v2/by-puuid/mmr/{region}/{puuid}"
        try:
            async with session.get(mmr_url, headers=headers) as resp:
                if resp.status != 200:
                    return {
                        "name": name,
                        "tag": tag,
                        "currenttierpatched": "Unranked",
                        "ranking_in_tier": 0,
                        "elo": 0
                    }, None
                
                mmr_data = await resp.json()
                mmr_info = mmr_data.get("data", {})
                
                tier = mmr_info.get("currenttierpatched")
                if not tier:
                    tier = "Unranked"
                
                rr = mmr_info.get("ranking_in_tier", 0)
                elo = mmr_info.get("elo", 0)

                return {
                    "name": name,
                    "tag": tag,
                    "currenttierpatched": tier,
                    "ranking_in_tier": rr,
                    "elo": elo
                }, None
        except Exception:
            return {
                "name": name,
                "tag": tag,
                "currenttierpatched": "Unranked",
                "ranking_in_tier": 0,
                "elo": 0
            }, None

    @commands.command(name="compare", aliases=["karsilastir", "kıyasla"])
    async def compare(self, ctx, player1: str = None, player2: str = None):
        """İki oyuncuyu PUUID tabanlı doğru veri çekme sistemiyle karşılaştırır."""
        if not player1 or not player2 or "#" not in player1 or "#" not in player2:
            await ctx.send("❌ Hatalı kullanım! İki oyuncunun da Riot ID'sini aralarında boşluk bırakarak yazmalısın.\n• Örnek: `v!compare Alisca#AMEL AliTachi#1907`")
            return

        loading_msg = await ctx.send("⏳ Oyuncu verileri Riot sunucularından taranıyor ve analiz ediliyor...")

        async with aiohttp.ClientSession() as session:
            res1, err1 = await self.fetch_player_data(session, player1)
            res2, err2 = await self.fetch_player_data(session, player2)

        if err1 and not res1:
            await loading_msg.edit(content=f"❌ 1. Oyuncu Hatası: {err1}")
            return
        if err2 and not res2:
            await loading_msg.edit(content=f"❌ 2. Oyuncu Hatası: {err2}")
            return

        tier1 = res1.get("currenttierpatched", "Unranked")
        rr1 = res1.get("ranking_in_tier", 0)
        elo1 = res1.get("elo", 0)

        tier2 = res2.get("currenttierpatched", "Unranked")
        rr2 = res2.get("ranking_in_tier", 0)
        elo2 = res2.get("elo", 0)

        embed = discord.Embed(
            title="⚔️ V-TRACKER.GG | OYUNCU KARŞILAŞTIRMASI",
            description="İki oyuncunun güncel dereceleri ve performans verilerinin iki yönlü analizi:",
            color=self.CYAN
        )

        embed.add_field(
            name=f"👤 {player1}",
            value=f"• Derece: `{tier1}`\n• RR: `{rr1}`\n• Elo Puanı: `{elo1}`",
            inline=True
        )
        embed.add_field(
            name=f"👤 {player2}",
            value=f"• Derece: `{tier2}`\n• RR: `{rr2}`\n• Elo Puanı: `{elo2}`",
            inline=True
        )

        if elo1 > elo2:
            winner_text = f"🏆 Bu kıyaslamada **{player1}** Elo ve derece olarak önde!"
        elif elo2 > elo1:
            winner_text = f"🏆 Bu kıyaslamada **{player2}** Elo ve derece olarak önde!"
        else:
            winner_text = "⚖️ İki oyuncunun güç dengesi kafa kafaya!"

        embed.add_field(name="📊 Detaylı Kıyaslama Sonucu", value=winner_text, inline=False)
        embed.set_footer(text="V-Tracker.gg • PUUID Destekli Gelişmiş Kıyaslama")

        await loading_msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Compare(bot))