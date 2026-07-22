import discord
from discord.ext import commands
import aiohttp
import json
import os
import urllib.parse

class CounterStrat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.USERS_FILE = "users.json"
        self.API_KEY = getattr(bot, "henrik_api_key", "HDEv-e534fbfe-c3c4-4f21-bccc-54eeeb39fd27")
        self.CYAN = 0x00F0FF

    def load_json(self, filepath):
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get_user_riot_id(self, user_id_str):
        data = self.load_json(self.USERS_FILE)
        user_data = data.get(user_id_str)
        if not user_data:
            return None
        if isinstance(user_data, dict):
            name = user_data.get("name")
            tag = user_data.get("tag")
            if name and tag:
                return f"{name}#{tag}"
        elif isinstance(user_data, str):
            return user_data.strip()
        return None

    @commands.command(name="counterstrat", aliases=["counter", "strat", "karsistrat"])
    async def counterstrat(self, ctx):
        """Aktif maçınızı analiz eder ve rakip takımda smurf kontrolü yapar."""
        uid_str = str(ctx.author.id)
        riot_id = self.get_user_riot_id(uid_str)

        if not riot_id or "#" not in riot_id:
            await ctx.send("❌ Kayıtlı Riot ID bulunamadı! Lütfen önce profilini kaydedin veya komutu `v!stats İsim#Tag` mantığına uygun hale getirin.")
            return

        name, tag = riot_id.split("#", 1)
        headers = {"Authorization": self.API_KEY}
        live_url = f"https://api.henrikdev.xyz/v1/live-match/eu/{urllib.parse.quote(name.strip())}/{urllib.parse.quote(tag.strip())}"

        async with aiohttp.ClientSession() as session:
            async with session.get(live_url, headers=headers) as resp:
                if resp.status != 200:
                    await ctx.send("❌ **İlk önce maça girin!** Şu an aktif bir maçta olduğunuz tespit edilemedi.")
                    return
                data = await resp.json()

        match_data = data.get("data", {})
        if not match_data:
            await ctx.send("❌ **İlk önce maça girin!** Aktif maç verisi bulunamadı.")
            return

        map_name = match_data.get("map", "Bilinmeyen Harita")
        game_mode = match_data.get("mode", "Dereceli / Normal")
        players = match_data.get("players", [])

        # Oyuncuyu ve takımları ayırt et (Örn: Red vs Blue)
        # Henrik API live match yapısına göre rakip oyuncuları filtrele
        my_team = None
        for p in players:
            if p.get("name").lower() == name.lower() and p.get("tag").lower() == tag.lower():
                my_team = p.get("team")
                break

        enemies = [p for p in players if p.get("team") != my_team] if my_team else players[:5]

        embed = discord.Embed(
            title="🎯 V-TRACKER | COUNTER-STRAT & SMURF ANALİZİ",
            description=f"Harita: **{map_name}** | Mod: **{game_mode}**\nRakip Takım Analizi ve Smurf Taraması Gerçekleştiriliyor...",
            color=self.CYAN
        )

        smurf_detected = False
        enemy_desc = ""

        for idx, enemy in enumerate(enemies, 1):
            e_name = enemy.get("name", "Bilinmiyor")
            e_tag = enemy.get("tag", "TR1")
            e_agent = enemy.get("character", "Bilinmiyor")
            e_level = enemy.get("level", 1)
            
            # Smurf Algoritması Kriteri: Düşük Hesap Seviyesi (Örn: 30 level altı) ve yüksek performans şüphesi
            is_smurf = e_level < 35
            smurf_tag = "🚨 **SMURF ŞÜPHESİ!**" if is_smurf else "✅ Normal Oyuncu"
            
            if is_smurf:
                smurf_detected = True

            enemy_desc += f"**{idx}. {e_name}#{e_tag}** ({e_agent})\n" \
                          f"• Seviye: `{e_level}` | {smurf_tag}\n\n"

        embed.add_field(name="⚔️ Rakip Oyuncu Listesi", value=enemy_desc if enemy_desc else "Rakip verisi çözülemedi.", inline=False)

        if smurf_detected:
            embed.add_field(
                name="⚠️ TAKTİKSEL UYARI",
                value="Rakip takımda düşük seviyeli yüksek şüpheli hesaplar tespit edildi! Dikkatli oynamanızı ve peek atarken kontrollü olmanızı öneririz.",
                inline=False
            )
        else:
            embed.add_field(
                name="🛡️ TAKTİKSEL DURUM",
                value="Rakip takımda göze çarpan belirgin bir smurf sinyali bulunmuyor. Normal bir eşleşme.",
                inline=False
            )

        embed.set_footer(text="V-Tracker.gg • Canlı Maç Counter-Strat Sistemi")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CounterStrat(bot))