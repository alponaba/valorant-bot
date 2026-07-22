import discord
from discord.ext import commands
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

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CYAN = 0x00F0FF

    @commands.command(name="register", aliases=["kayit", "kaydol"])
    async def register(self, ctx, *, riot_id: str = None):
        if not riot_id or "#" not in riot_id:
            await ctx.send("❌ Eksik kullanım! Örnek: `v!register Alisca#AMEL`")
            return

        if riot_id.count("#") != 1:
            await ctx.send("❌ Hatalı format! Riot ID'de yalnızca bir adet `#` olmalıdır.")
            return

        user_id = str(ctx.author.id)
        data = load_data()

        data[user_id] = {
            "riot_id": riot_id.strip(),
            "username": str(ctx.author)
        }
        save_data(data)

        embed = discord.Embed(
            title="✅ BAŞARILI KAYIT",
            description=f"Riot ID'in başarıyla kaydedildi: **{riot_id.strip()}**\n\n*Bu kayıt globaldir; botun olduğu hiçbir sunucuda tekrar kayıt olman gerekmez.*",
            color=self.CYAN
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Register(bot))