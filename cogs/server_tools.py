import discord
from discord.ext import commands
from config import SUGGESTION_CHANNEL_ID
from theme import error, info, success

class ServerTools(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.hybrid_command(name="suggest",aliases=["oneri","öneri"],description="Bot/sunucu önerisi gönderir.")
    async def suggest(self,ctx,*,text:str):
        channel=self.bot.get_channel(SUGGESTION_CHANNEL_ID) if SUGGESTION_CHANNEL_ID else None
        e=info("Yeni Öneri",text); e.set_author(name=str(ctx.author),icon_url=ctx.author.display_avatar.url)
        if channel:
            msg=await channel.send(embed=e); await msg.add_reaction('👍'); await msg.add_reaction('👎'); await ctx.send(embed=success("Öneri gönderildi",f"{channel.mention} kanalına iletildi."),ephemeral=True if ctx.interaction else False)
        else: await ctx.send(embed=e)
    @commands.hybrid_command(name="join",aliases=["gel"],description="Bulunduğun ses kanalına katılır.")
    async def join(self,ctx):
        if not getattr(ctx.author,'voice',None) or not ctx.author.voice.channel: return await ctx.send(embed=error("Ses kanalı yok","Önce bir ses kanalına gir."))
        if ctx.voice_client: await ctx.voice_client.move_to(ctx.author.voice.channel)
        else: await ctx.author.voice.channel.connect()
        await ctx.send(embed=success("Ses kanalına bağlandım",ctx.author.voice.channel.name))
    @commands.hybrid_command(name="leave",aliases=["cik","çık","git"],description="Ses kanalından ayrılır.")
    async def leave(self,ctx):
        if not ctx.voice_client: return await ctx.send(embed=error("Bağlı değilim","Şu anda ses kanalında değilim."))
        await ctx.voice_client.disconnect(force=True); await ctx.send(embed=success("Ayrıldım","Ses bağlantısı kapatıldı."))
    @commands.hybrid_command(name="setup",description="Temel V-Tracker sunucu kanallarını/rollerini kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_server(self,ctx):
        guild=ctx.guild
        if not guild: return await ctx.send(embed=error("Sunucu gerekli","Bu komut DM'de kullanılamaz."))
        # Idempotent: existing names are reused.
        role_names=[("Doğrulanmış Oyuncu",0x2ECC71),("Immortal",0xE74C3C),("Ascendant",0x2ECC71),("Diamond",0x9B59B6)]
        for name,color in role_names:
            if not discord.utils.get(guild.roles,name=name): await guild.create_role(name=name,color=discord.Color(color),reason="V-Tracker setup")
        cat=discord.utils.get(guild.categories,name="V-TRACKER") or await guild.create_category("V-TRACKER")
        for name in ["v-tracker-komut","istatistikler","öneriler"]:
            if not discord.utils.get(guild.text_channels,name=name): await guild.create_text_channel(name,category=cat)
        await ctx.send(embed=success("Kurulum tamamlandı","V-Tracker kategorisi, temel kanallar ve roller hazır."))

async def setup(bot): await bot.add_cog(ServerTools(bot))
