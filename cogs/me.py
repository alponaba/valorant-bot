import discord
from discord.ext import commands
import json
import os

class Me(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.USERS_FILE = "users.json"

    def load_users(self):
        if not os.path.exists(self.USERS_FILE):
            return {}
        try:
            with open(self.USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @commands.command(name="me", aliases=["profil", "ben"])
    async def me_command(self, ctx):
        """Kayıtlı Valorant profilini gösterir."""
        users = self.load_users()
        user_id_str = str(ctx.author.id)

        if user_id_str not in users:
            embed = discord.Embed(
                title="❌ PROFİL BULUNAMADI",
                description="Henüz Riot ID kaydı yapmamışsın!\nKayıt olmak için: `v!register İsim#Tag`",
                color=0xFF0055
            )
            await ctx.send(embed=embed)
            return

        riot_id = users[user_id_str]

        embed = discord.Embed(
            title=f"👤 {ctx.author.display_name} - OYUNCU PROFİLİ",
            description=f"**Bağlı Riot ID:** `{riot_id}`",
            color=self.V_CYAN
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="V-Tracker.gg • Kullanıcı Profili")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Me(bot))