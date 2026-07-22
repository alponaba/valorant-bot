import discord
from discord.ext import commands
import asyncio

class TextToSpeech(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="say", aliases=["konuş", "oku"])
    async def say(self, ctx, *, mesaj: str = None):
        if not mesaj:
            await ctx.send("⚠️ Sesli okumamı istediğin yazıyı yazmalısın! Örnek: `v!say Maç başladı beyler`")
            return

        if not ctx.guild.voice_client:
            await ctx.send("❌ Önce botu ses kanalına çağırmalısın (`v!autojoin`).")
            return

        vc = ctx.guild.voice_client

        if vc.is_playing():
            await ctx.send("⚠️ Şu an başka bir şey okuyorum, birazdan tekrar dene.")
            return

        try:
            # Discord'un kendi yerleşik TTS (Metin Okuma) özelliğini kullanarak sese mesaj gönderiyoruz
            await ctx.send(mesaj, tts=True)
        except Exception as e:
            print(f"TTS Hatası: {e}")
            await ctx.send("⚠️ Sesli mesaj gönderilirken bir aksilik çıktı.")

async def setup(bot):
    await bot.add_cog(TextToSpeech(bot))