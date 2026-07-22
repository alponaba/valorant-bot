import discord
from discord.ext import commands
import json
import os

class ParaVer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ECONOMY_FILE = "economy.json"

    def load_json(self, filepath):
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_json(self, filepath, data):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def get_user_balance(self, user_id_str):
        eco = self.load_json(self.ECONOMY_FILE)
        val = eco.get(user_id_str, 1000)
        if isinstance(val, dict):
            return int(val.get("balance", val.get("money", 1000)))
        try:
            return int(val)
        except Exception:
            return 1000

    def update_user_balance(self, user_id_str, amount):
        eco = self.load_json(self.ECONOMY_FILE)
        current = self.get_user_balance(user_id_str)
        new_balance = current + amount
        eco[user_id_str] = {"balance": new_balance}
        self.save_json(self.ECONOMY_FILE, eco)
        return new_balance

    @commands.command(name="paraver", aliases=["paraekle", "addmoney"])
    @commands.has_permissions(administrator=True)
    async def paraver(self, ctx, member: discord.Member = None, amount: int = None):
        """Belirtilen kullanıcıya V-Coin ekler (Sadece yetkililer)."""
        if member is None or amount is None:
            await ctx.send("❌ Eksik kullanım! Örnek: `v!paraver @Kullanici 500`")
            return

        if amount == 0:
            await ctx.send("❌ 0'dan farklı bir miktar girmelisin.")
            return

        uid = str(member.id)
        new_bal = self.update_user_balance(uid, amount)
        
        action_text = f"**+{amount:,} V-Coin** eklendi" if amount > 0 else f"**{amount:,} V-Coin** düşüldü"
        embed = discord.Embed(
            title="💰 BAKIYE GÜNCELLENDİ",
            description=f"**{member.mention}** adlı kullanıcıya {action_text}!\n• Yeni Bakiye: `{new_bal:,} V-Coin`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @paraver.error
    async def paraver_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komutu yalnızca **bot yetkilileri / yöneticiler** kullanabilir!")
        elif isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Hatalı kullanım! Örnek: `v!paraver @Kullanici 500`")
        else:
            await ctx.send(f"❌ Bir hata oluştu: `{error}`")

async def setup(bot):
    await bot.add_cog(ParaVer(bot))