import discord
from discord.ext import commands

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
        
        self.add_item(discord.ui.Button(
            label="Botu Sunucuna Ekle", 
            url="BURAYA_BOT_DAVET_LINKINI_YAZ", 
            style=discord.ButtonStyle.link,
            emoji="🤖"
        ))
        
        self.add_item(discord.ui.Button(
            label="Web Sitemiz", 
            url="https://valorant-bot-x6tv.onrender.com", 
            style=discord.ButtonStyle.link,
            emoji="🌐"
        ))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Botun tüm komutlarını ve nasıl kullanıldığını gösterir.")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="V-Tracker.gg | Yardım Menüsü",
            description="Botun özelliklerini ve komutların nasıl kullanılacağını aşağıdan inceleyebilirsin.",
            color=discord.Color.blurple()
        )
        
        embed.add_field(
            name="💰 Ekonomi Komutları",
            value="**`/balance`** - Güncut cüzdan bakiyeni ve paranı gösterir.\n**`/daily`** - 24 saatte bir alabileceğin günlük ödülü verir.",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Valorant Komutları",
            value="**`/stats [isim] [etiket]`** - Belirtilen Valorant hesabının istatistiklerini gösterir.\n**`/match [isim] [etiket]`** - Hesabın son oynadığı maçın verilerini getirir.",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Diğer Komutlar",
            value="**`/ping`** - Botun gecikme süresini (ms) ölçer.\n**`/help`** - Bu yardım menüsünü açar.",
            inline=False
        )
        
        embed.set_thumbnail(url="BURAYA_KUCUK_FOTO_LINKI_YAZABILIRSIN")
        embed.set_image(url="BURAYA_BUYUK_GIF_VEYA_FOTO_LINKI_YAZABILIRSIN")
        
        avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None
        embed.set_footer(text="V-Tracker.gg | Senin Valorant Asistanın", icon_url=avatar_url)
        
        view = HelpView()
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    bot.remove_command("help")
    await bot.add_cog(Help(bot))