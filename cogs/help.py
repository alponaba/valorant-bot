import discord
from discord.ext import commands

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
        
        
        self.add_item(discord.ui.Button(
            label="Botu Sunucuna Ekle", 
            url="https://discord.com/oauth2/authorize?client_id=1529436221187686482&permissions=8&integration_type=0&scope=bot", 
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

    @commands.hybrid_command(name="help", description="V-Tracker botunun tüm komutlarını ve özelliklerini gösterir.")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🎯 V-Tracker.gg | Gelişmiş Valorant Asistanı",
            description=(
                "Sıradan bir stat botundan çok daha fazlası. V-Tracker; ajan analizlerinden "
                "özel koçluk sistemine, sunucu moderasyonundan kendi ekonomi sistemine kadar "
                "Discord sunucunu tam donanımlı bir Valorant merkezine çevirir.\n\n"
                "Aşağıdan botun modüllerine ve komutlarına göz atabilirsin:"
            ),
            color=discord.Color.cyan()
        )
        
        
        embed.add_field(
            name="📊 İstatistik & Analiz",
            value="`stats`, `match`, `profile` - Oyuncu verilerini ve maç geçmişini getirir.\n`agents`, `compare` - Ajan bazlı istatistikler ve oyuncu karşılaştırmaları.",
            inline=False
        )
        
        # cogs klasöründeki: coach.py, custom_coach.py, counter_strat.py, comps.py
        embed.add_field(
            name="🧠 Koçluk & Taktik",
            value="`coach`, `custom_coach` - Kişiselleştirilmiş oyun içi tavsiyeler verir.\n`counter_strat`, `comps` - Rakibe karşı anti-strateji ve takım kompozisyonları.",
            inline=False
        )

        # cogs klasöründeki: economy.py, bet.py, paraver.py, challanges.py
        embed.add_field(
            name="💰 Ekonomi & Eğlence",
            value="`balance`, `daily`, `paraver` - Kendi V-Coin ekonomini yönet.\n`bet`, `challanges` - V-Coin ile bahislere gir ve günlük görevleri tamamla.",
            inline=False
        )
        
        # cogs klasöründeki: moderasyon.py, security.py, setup_server.py, temp_voice.py
        embed.add_field(
            name="🛡️ Sunucu Yönetimi",
            value="`setup_server`, `moderasyon` - Hızlı sunucu kurulumu ve denetimi.\n`security`, `temp_voice` - Güvenlik ayarları ve geçici ses kanalları (Temp VC).",
            inline=False
        )
        
        # cogs klasöründeki: autojoin.py, suggestion.py, tts.py
        embed.add_field(
            name="✨ Ekstra Araçlar",
            value="`autojoin`, `tts` - Sesli sohbet araçları ve metin okuma (Text-to-Speech).\n`suggestion` - Sunucu üyeleri için öneri/istek sistemi.",
            inline=False
        )
        
        # Buralara botunun logo linkini veya banner gifini ekleyebilirsin
        embed.set_thumbnail(url="https://i.hizliresim.com/r7m6b3e.png") # Örnek bir görsel koydum, kendi linkinle değiştir
        
        # Gönderen kişinin profil fotoğrafı ve ismini footer'a ekleme
        avatar_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        embed.set_footer(text=f"Talep eden: {ctx.author.name} | V-Tracker.gg", icon_url=avatar_url)
        
        view = HelpView()
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    # Eğer botun default help komutu aktifse çakışmaması için onu siliyoruz
    bot.remove_command("help")
    await bot.add_cog(Help(bot))