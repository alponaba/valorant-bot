# -*- coding: utf-8 -*-
"""
Modül: cogs.help
"""

import discord
from discord.ext import commands
import logging

logger = logging.getLogger("VTracker.Help")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Help]: %(message)s"))
    logger.addHandler(handler)

WEB_PANEL_URL = "https://valorant-bot-x6tv.onrender.com/"

class HelpSelect(discord.ui.Select):
    def __init__(self, embeds: dict):
        self.embeds = embeds
        options = [
            discord.SelectOption(label="Genel Bakış", description="Botun çalışma mantığı ve web paneli.", emoji="📋", value="general"),
            discord.SelectOption(label="Kayıt İşlemleri", description="Riot ID ve Discord ID eşleştirme.", emoji="🔗", value="register"),
            discord.SelectOption(label="İstatistik Analizi", description="3 sayfalık detaylı maç raporları.", emoji="📊", value="stats"),
            discord.SelectOption(label="Ekonomi ve Liderlik", description="V-Coin cüzdan ve liderlik tablosu.", emoji="💰", value="economy"),
            discord.SelectOption(label="Hata ve Çözümler", description="Sık karşılaşılan hatalar ve çözümleri.", emoji="⚠️", value="faq")
        ]
        super().__init__(placeholder="Bir kategori seçin...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        target_embed = self.embeds.get(self.values[0])
        if target_embed:
            await interaction.response.edit_message(embed=target_embed)
        else:
            await interaction.response.send_message("Kategori bulunamadı.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self, embeds: dict):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.add_item(HelpSelect(embeds))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Web Paneli", style=discord.ButtonStyle.link, url=WEB_PANEL_URL, emoji="🌐", row=1)
    async def web_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Kapat", style=discord.ButtonStyle.danger, emoji="✖️", row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            await interaction.response.edit_message(content="Menü kapatıldı.", embed=None, view=None)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def create_embeds(self, ctx) -> dict:
        avatar_url = ctx.bot.user.display_avatar.url if ctx.bot.user else None

        embed_general = discord.Embed(
            title="V-Tracker.gg - Genel Bakış",
            description=(
                "**V-Tracker.gg**, Valorant oyuncularının rekabetçi maç istatistiklerini, "
                "silah performanslarını ve isabet oranlarını analiz eden bir Discord botudur.\n\n"
                f"**Web Paneli:** [V-Tracker.gg Arayüzü]({WEB_PANEL_URL})"
            ),
            color=0x00F0FF
        )
        embed_general.add_field(
            name="Çalışma Mantığı",
            value=(
                "1. **Kayıt:** Riot hesabınızı Discord ID'niz ile eşleştirirsiniz.\n"
                "2. **API:** HenrikDev altyapısı ile maç verileriniz çekilir.\n"
                "3. **Analiz:** K/D, ADR, ACS ve vuruş dağılımları raporlanır."
            ),
            inline=False
        )
        embed_general.set_footer(text="Sayfa 1/5 • Genel Bakış", icon_url=avatar_url)

        embed_register = discord.Embed(
            title="V-Tracker.gg - Kayıt İşlemleri",
            description="İstatistik komutlarını kullanabilmek için hesabınızı kaydetmeniz gerekir.",
            color=0x00FF99
        )
        embed_register.add_field(
            name="v!register Komutu",
            value=(
                "**Kullanım:** `v!register [Discord ID] [İsim#Tag]`\n"
                "**Örnek:** `v!register 76003400419407626 nxbx#NABA`\n\n"
                "*Not: Discord ID öğrenmek için Geliştirici Modu'nu açıp profilinize sağ tıklayarak ID'nizi kopyalayabilirsiniz.*"
            ),
            inline=False
        )
        embed_register.set_footer(text="Sayfa 2/5 • Kayıt", icon_url=avatar_url)

        embed_stats = discord.Embed(
            title="V-Tracker.gg - İstatistik Analizi",
            description="Son 15 rekabetçi maçınızı detaylı şekilde inceleyen komuttur.",
            color=0xF1C40F
        )
        embed_stats.add_field(
            name="v!stats Komutu",
            value=(
                "**Kullanım:** `v!stats` veya `v!stats @Kullanici`\n\n"
                "**3 Sayfalık Rapor İçeriği:**\n"
                "• **Sayfa 1:** Genel Bakış (Rank, RR, Seviye, Main Ajan, K/D/A)\n"
                "• **Sayfa 2:** Teknik Hasar (ADR, ACS, Headshot/Bodyshot/Legshot)\n"
                "• **Sayfa 3:** Silah ve Ajan Dağılımı"
            ),
            inline=False
        )
        embed_stats.set_footer(text="Sayfa 3/5 • İstatistik", icon_url=avatar_url)

        embed_economy = discord.Embed(
            title="V-Tracker.gg - Ekonomi ve Liderlik",
            description="V-Coin cüzdan sistemi ve sunucu içi sıralama komutları.",
            color=0xE67E22
        )
        embed_economy.add_field(
            name="Liderlik ve Cüzdan Komutları",
            value=(
                "• **`v!top`**: En yüksek V-Coin biriktiren ilk 10 oyuncuyu listeler.\n"
                "• **`v!wallet`**: Kendi cüzdan bakiyenizi veya etiketlenen kullanıcının bakiyesini gösterir."
            ),
            inline=False
        )
        embed_economy.set_footer(text="Sayfa 4/5 • Ekonomi", icon_url=avatar_url)

        embed_faq = discord.Embed(
            title="V-Tracker.gg - Hata ve Çözümler",
            description="Komut kullanımında karşılaşılan yaygın hatalar.",
            color=0xE74C3C
        )
        embed_faq.add_field(
            name="Sık Karşılaşılan Hatalar",
            value=(
                "• **Kayıt Hatası:** 'Kayıt olmalısın' uyarısı alıyorsanız `v!register` komutunu kullanmalısınız.\n"
                "• **Bulunamadı Hatası:** Riot ID'nizi `İsim#Tag` formatında doğru girdiğinizden emin olun."
            ),
            inline=False
        )
        embed_faq.set_footer(text="Sayfa 5/5 • Destek", icon_url=avatar_url)

        return {
            "general": embed_general,
            "register": embed_register,
            "stats": embed_stats,
            "economy": embed_economy,
            "faq": embed_faq
        }

    @commands.command(name="vhelp", aliases=["help", "yardim", "komutlar"])
    async def vhelp(self, ctx):
        embeds = self.create_embeds(ctx)
        view = HelpView(embeds)
        await ctx.send(embed=embeds["general"], view=view)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
    logger.info("HelpCog başarıyla yüklendi.")