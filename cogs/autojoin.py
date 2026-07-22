import discord
from discord.ext import commands
import json
import os

class AutoJoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.users_db = "users.json"

    @commands.command(name="autojoin", aliases=["sesevel", "gel"])
    async def auto_join(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ Önce bir ses kanalına (Voice Channel) katılmalısın!")
            return

        voice_channel = ctx.author.voice.channel
        
        # Eğer bot zaten sesindeyse
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.move_to(voice_channel)
            await ctx.send(f"🔊 Zaten sesteydim, yanına ({voice_channel.name}) geldim!")
            return

        try:
            vc = await voice_channel.connect()
            await ctx.send(f"🔊 Odaya katıldım! **{voice_channel.name}** kanalındayım. Maç bittiğinde sana buradan eşlik edeceğim.")
        except Exception as e:
            print(f"Ses bağlantı hatası: {e}")
            await ctx.send("⚠️ Ses kanalına bağlanırken bir sorun oluştu.")

    @commands.command(name="leave", aliases=["çık", "git"])
    async def leave(self, ctx):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            await ctx.send("🔇 Ses kanalından ayrıldım.")
        else:
            await ctx.send("❌ Zaten bir ses kanalında değilim.")

async def setup(bot):
    await bot.add_cog(AutoJoin(bot))