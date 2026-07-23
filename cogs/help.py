import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["yardim", "komutlar", "info"])
    async def help_command(self, ctx):
        # Valorant kırmızısı renginde, şık bir Embed (mesaj kartı) oluşturuyoruz
        embed = discord.Embed(
            title="🎯 V-Tracker Bot | Yardım Menüsü",
            description="V-Tracker botunun tüm komutları aşağıda kategorilere ayrılmıştır.\nKomutları kullanırken başına `v!` eklemeyi unutmayın.",
            color=discord.Color.from_rgb(250, 68, 84) 
        )
        
        # --- KATEGORİ 1: İstatistik ---
        embed.add_field(
            name="📊 İstatistik & Analiz",
            value=(
                "`v!stats` - Genel performansını ve K/D oranını gösterir.\n"
                "`v!match` - Oynadığın son maçın özetini getirir.\n"
                "`v!agent` - Main ajanındaki istatistiklerini analiz eder."
            ),
            inline=False
        )
        
        # --- KATEGORİ 2: Hesap ---
        embed.add_field(
            name="🔗 Hesap İşlemleri",
            value=(
                "`v!register [İsim#Tag]` - Riot hesabını Discord'a bağlar.\n"
                "`v!profile` - Sana özel V-Tracker profil kartını çizer.\n"
                "`v!unlink` - Kayıtlı Riot hesabını sistemden siler."
            ),
            inline=False
        )
        
        # --- KATEGORİ 3: Ekonomi ---
        embed.add_field(
            name="💰 V-Coin & Ekonomi",
            value=(
                "`v!wallet` - Mevcut V-Coin bakiyeni gösterir.\n"
                "`v!daily` - Günlük ücretsiz V-Coin ödülünü alırsın.\n"
                "`v!top` - Sunucudaki en zengin oyuncuları listeler."
            ),
            inline=False
        )

        # --- ALT BİLGİ ---
        # İsteyen kişinin profil fotoğrafını ve adını sağ alta ekliyoruz
        embed.set_footer(
            text=f"Talep eden: {ctx.author.name} | V-Tracker.gg", 
            icon_url=ctx.author.display_avatar.url
        )
        
        # Botun kendi profil fotoğrafını sağ üste küçük simge olarak ekliyoruz
        if self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Menüyü kanala gönder
        await ctx.send(embed=embed)

async def setup(bot):
    # Çakışma olmaması için Discord'un varsayılan help komutunu siliyoruz
    try:
        bot.remove_command("help")
    except Exception:
        pass
    
    # Yeni klasik yardım menümüzü bota ekliyoruz
    await bot.add_cog(HelpCog(bot))