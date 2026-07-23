# -*- coding: utf-8 -*-
"""
=============================================================================
V-Tracker.gg - Profesyonel ve Modüler İnteraktif Yardım Sistemi (Master Help Cog)
Modül: cogs.help
Geliştirici: V-Tracker.gg Core Engineering Team
Açıklama: 
    Bu modül; botun tüm komutlarını, modüllerini (Kayıt, İstatistik, Ekonomi, 
    Liderlik Tablosu ve Hata Yönetimi) kategorize ederek kullanıcıya açılır 
    menüler (Dropdown), interaktif butonlar ve animasyonlu görsel/GIF destekli 
    embed'ler üzerinden sunar. Anlamsız emojilerden kaçınılarak tamamen işlevsel 
    ve sektörel standartlara uygun ikonlar tercih edilmiştir.
=============================================================================
"""

import discord
from discord.ext import commands
import logging
from typing import List, Dict, Any, Optional

# =====================================================================
# 1. LOGLAMA VE SİSTEM YAPILANDIRMASI
# =====================================================================

# Loglama yöneticisi, yardım modülündeki etkileşimleri konsola raporlar.
logger = logging.getLogger("VTracker.MasterHelpSystem")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [MasterHelp]: %(message)s"))
    logger.addHandler(handler)

# Sabit Medya ve GIF Kaynakları (Valorant / Tracker Tema Destekli)
ASSET_BANNER_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z2bzR2b2R4b2R4b2R4b2R4b2R4b2R4b2R4b2R4b2R4b2R4YiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26ufdipQqU2lhNA4g/giphy.gif"
ASSET_THUMBNAIL_LOGO = "https://images.vexels.com/media/users/3/142770/isolated/preview/65481744bc7a030d9bc9953920a038cf-v-letter-logo-geometric-shape.png"
WEB_PANEL_URL = "https://valorant-bot-x6tv.onrender.com/"


# =====================================================================
# 2. İNTERAKTİF UI BİLEŞENLERİ (SELECT MENU & PAGINATION VIEWS)
# =====================================================================

class MasterHelpDropdown(discord.ui.Select):
    """
    Kullanıcının yardım merkezindeki 5 temel modül arasında anında geçiş 
    yapmasını sağlayan dinamik açılır menü (Dropdown) sınıfı.
    """
    def __init__(self, embeds_dict: Dict[str, discord.Embed]):
        self.embeds_dict = embeds_dict
        
        # Anlamsız emojiler yerine modül işlevini net belirten profesyonel emojiler
        options = [
            discord.SelectOption(
                label="1. Genel Sistem Mimarisi",
                description="V-Tracker.gg altyapısı, web paneli ve genel bakış.",
                emoji="🎯",
                value="general"
            ),
            discord.SelectOption(
                label="2. Kayıt ve Kimlik Modülü",
                description="Discord ID ve Riot ID eşleştirme komutları (`v!register`).",
                emoji="🔗",
                value="register"
            ),
            discord.SelectOption(
                label="3. 3 Sayfalı İstatistik Motoru",
                description="K/D, HS%, ADR, ACS ve harita analiz raporları (`v!stats`).",
                emoji="📊",
                value="stats"
            ),
            discord.SelectOption(
                label="4. V-Coin Ekonomi ve Liderlik",
                description="Liderlik tablosu (`v!top`) ve cüzdan yönetimi (`v!wallet`).",
                emoji="🏆",
                value="economy"
            ),
            discord.SelectOption(
                label="5. Hata Yönetimi ve SSS",
                description="Sık karşılaşılan hatalar, kod çözümleri ve destek.",
                emoji="🛡️",
                value="faq"
            )
        ]
        
        super().__init__(
            placeholder="📂 İncelemek istediğiniz modülü seçin...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        """Kullanıcı açılır menüden bir seçenek seçtiğinde tetiklenen asenkron fonksiyon."""
        selected_key = self.values[0]
        target_embed = self.embeds_dict.get(selected_key)
        
        if target_embed:
            # Seçilen modüle ait embed'i günceller
            await interaction.response.edit_message(embed=target_embed)
            logger.info(f"Kullanıcı {interaction.user} yardım menüsünde '{selected_key}' modülünü görüntüledi.")
        else:
            await interaction.response.send_message("❌ Aradığınız modül içeriği sistemde bulunamadı.", ephemeral=True)


class MasterHelpPaginationView(discord.ui.View):
    """
    Açılır menüyü ve ek kontrol butonlarını barındıran, 300 saniye zaman aşımı 
    süreçlerini yöneten ana interaktif arayüz sınıfı.
    """
    def __init__(self, embeds_dict: Dict[str, discord.Embed]):
        super().__init__(timeout=300)
        self.embeds_dict = embeds_dict
        
        # Açılır menüyü arayüze ekle
        self.add_item(MasterHelpDropdown(self.embeds_dict))

    async def on_timeout(self):
        """Zaman aşımına uğradığında arayüz butonlarını ve menüyü devre dışı bırakır."""
        for child in self.children:
            child.disabled = True
        try:
            # Mevcut mesajı devre dışı bırakılmış olarak güncellemeye çalışır
            logger.info("Yardım menüsü zaman aşımına uğradı ve kilitlendi.")
        except Exception as e:
            logger.error(f"Yardım menüsü zaman aşımı hatası: {e}")

    @discord.ui.button(label="Web Paneli", style=discord.ButtonStyle.link, url=WEB_PANEL_URL, emoji="🌐", row=1)
    async def web_panel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Doğrudan resmi web sitesine yönlendiren sabit buton."""
        pass

    @discord.ui.button(label="Menüyü Kapat", style=discord.ButtonStyle.danger, emoji="✖️", row=1)
    async def close_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Kullanıcının yardım menüsünü mesajdan kaldırmasını sağlar."""
        try:
            await interaction.message.delete()
            logger.info(f"Kullanıcı {interaction.user} yardım menüsünü kapattı.")
        except Exception as e:
            await interaction.response.send_message("❌ Menü kapatılamadı.", ephemeral=True)


# =====================================================================
# 3. YARDIM MERKEZİ ANA COG SINIFI (MASTER HELP COG)
# =====================================================================

class VTrackerMasterHelpCog(commands.Cog):
    """
    V-Tracker.gg botunun kurumsal düzeydeki tüm modüllerini en ince detayına 
    kadar açıklayan, modül bazlı özelleştirilmiş yardım ve rehber sınıftır.
    """
    def __init__(self, bot):
        self.bot = bot
        logger.info("VTrackerMasterHelpCog başarıyla başlatıldı.")

    def build_module_embeds(self, ctx) -> Dict[str, discord.Embed]:
        """
        Her bir modül için özel olarak tasarlanmış, istatistiksel veriler, 
        GIF banner'lar ve profesyonel açıklamalar içeren embed sözlüğünü oluşturur.
        """
        bot_user = ctx.bot.user
        bot_name = bot_user.name if bot_user else "V-Tracker.gg"
        bot_avatar = bot_user.display_avatar.url if bot_user else ASSET_THUMBNAIL_LOGO

        embeds = {}

        # -----------------------------------------------------------------
        # MODÜL 1: GENEL SİSTEM MİMARİSİ
        # -----------------------------------------------------------------
        embed_general = discord.Embed(
            title="🎯 V-Tracker.gg - Genel Sistem Mimarisi ve Tanıtım",
            description=(
                f"**{bot_name}**, Valorant oyuncularının rekabetçi performanslarını, "
                "maç geçmişlerini, silah isabet oranlarını ve oyun içi vuruş haritalarını "
                "derinlemesine analiz eden yeni nesil bir Discord istatistik botudur.\n\n"
                "🌐 **Canlı Web Paneli ve API Servisleri:**\n"
                f"• [V-Tracker.gg Resmi Web Arayüzü]({WEB_PANEL_URL})\n"
                "• Güvenli HenrikDev Valorant API Altyapısı"
            ),
            color=0x00F0FF
        )
        embed_general.set_image(url=ASSET_BANNER_GIF)
        embed_general.set_thumbnail(url=bot_avatar)
        embed_general.add_field(
            name="⚙️ Teknik Altyapı ve Çalışma Prensibi",
            value=(
                "1. **Global JSON Veritabanı:** Kullanıcıların Discord ID'leri ile Riot PUUID bilgileri eşleştirilerek kalıcı olarak saklanır.\n"
                "2. **Asenkron İstek Yönetimi:** `aiohttp` kütüphanesi ile Riot sunucularından anlık veri çekilir ve thread bloklanması önlenir.\n"
                "3. **İstatistik Motoru:** Ham maç verileri işlenerek K/D, ADR, ACS, Headshot yüzdeleri gibi kritik metrikler hesaplanır."
            ),
            inline=False
        )
        embed_general.set_footer(text="Modül 1/5 • Genel Sistem Mimarisi • V-Tracker.gg", icon_url=bot_avatar)
        embeds["general"] = embed_general

        # -----------------------------------------------------------------
        # MODÜL 2: KAYIT VE KİMLİK MODÜLÜ (`v!register`)
        # -----------------------------------------------------------------
        embed_register = discord.Embed(
            title="🔗 Kayıt ve Kimlik Eşleştirme Modülü (`v!register`)",
            description=(
                "Botun istatistik, liderlik tablosu ve cüzdan özelliklerini tam kapasite "
                "kullanabilmeniz için Riot hesabınızı Discord profilinize kaydetmeniz gerekmektedir."
            ),
            color=0x00FF99
        )
        embed_register.set_thumbnail(url=bot_avatar)
        embed_register.add_field(
            name="📝 Komut Sözdizimi ve Parametreler",
            value=(
                "🔹 **Komut:** `v!register` (Alternatif: `v!kayit`)\n"
                "🔹 **Format:** `v!register [Discord ID] [İsim#Tag]`\n"
                "🔹 **Örnek Kullanım:**\n"
                "> `v!register 76003400419407626 nxbx#NABA`"
            ),
            inline=False
        )
        embed_register.add_field(
            name="💡 İpuçları ve Doğrulama",
            value=(
                "• **Discord ID Bulma:** Discord ayarlarından Geliştirici Modu'nu (Developer Mode) açın, profilinize sağ tıklayarak **Kullanıcı Kimliği Kopyala** seçeneğini kullanın.\n"
                "• **Riot ID Doğruluğu:** Oyun içindeki tam adınızı ve etiketçinizi (Örn: `Oyuncu#TR1`) eksiksiz girdiğinizden emin olun."
            ),
            inline=False
        )
        embed_register.set_footer(text="Modül 2/5 • Kayıt Modülü • V-Tracker.gg", icon_url=bot_avatar)
        embeds["register"] = embed_register

        # -----------------------------------------------------------------
        # MODÜL 3: 3 SAYFALI İSTATİSTİK MOTORU (`v!stats`)
        # -----------------------------------------------------------------
        embed_stats = discord.Embed(
            title="📊 3 Sayfalı Gelişmiş İstatistik Analiz Motoru (`v!stats`)",
            description=(
                "Kayıtlı oyuncuların son 15 rekabetçi maçını saniyeler içinde tarayarak "
                "detaylı performans raporları sunan interaktif analiz modülüdür."
            ),
            color=0xF1C40F
        )
        embed_stats.set_thumbnail(url=bot_avatar)
        embed_stats.add_field(
            name="📈 Komut Kullanımı",
            value=(
                "🔹 **Komut:** `v!stats` (Alternatifler: `v!istatistik`, `v!profil`)\n"
                "🔹 **Kendi Profiliniz:** `v!stats` yazmanız yeterlidir.\n"
                "🔹 **Başkasının Profili:** `v!stats @Kullanici` veya `v!stats [Discord ID]`"
            ),
            inline=False
        )
        embed_stats.add_field(
            name="📑 İnteraktif 3 Sayfa Yapısı",
            value=(
                "• **Sayfa 1 (Genel Bakış):** Rank, RR, Hesap Seviyesi, En İyi Ajan, K/D/A Oranı, En Çok Oynanan Haritalar ve Silahlar.\n"
                "• **Sayfa 2 (Teknik Hasar ve Vuruş):** ADR (Tur Başına Ortalama Hasar), ACS (Skor), Toplam Hasar, Headshot / Bodyshot / Legshot dağılımı.\n"
                "• **Sayfa 3 (Derin Döküm):** Tüm oynanan ajanların maç dağılımları ve ayrıntılı silah kill listesi."
            ),
            inline=False
        )
        embed_stats.set_footer(text="Modül 3/5 • İstatistik Motoru • V-Tracker.gg", icon_url=bot_avatar)
        embeds["stats"] = embed_stats

        # -----------------------------------------------------------------
        # MODÜL 4: V-COİN EKONOMİ VE LİDERLİK TABLOSU (`v!top`, `v!wallet`)
        # -----------------------------------------------------------------
        embed_economy = discord.Embed(
            title="🏆 V-Coin Ekonomi ve Liderlik Tablosu Sistemi",
            description=(
                "Aktif oyuncuları ödüllendiren, V-Coin cüzdan bakiyelerini takip eden "
                "ve rekabet ortamı yaratan entegre ekonomi modülüdür."
            ),
            color=0xE67E22
        )
        embed_economy.set_thumbnail(url=bot_avatar)
        embed_economy.add_field(
            name="🥇 Liderlik Tablosu (`v!top`)",
            value=(
                "• **Açıklama:** Sisteme kayıtlı en yüksek V-Coin biriktiren ilk 10 oyuncuyu büyükten küçüğe sıralar.\n"
                "• **Alternatif Komutlar:** `v!siralamasi`, `v!leaderboard`\n"
                "• **Görünüm:** Madalyalarla (`🥇`, `🥈`, `🥉`) zenginleştirilmiş özel Embed listesi."
            ),
            inline=False
        )
        embed_economy.add_field(
            name="💳 Cüzdan ve Bakiye Sorgulama (`v!wallet`)",
            value=(
                "• **Açıklama:** Kendi cüzdan bakiyenizi veya etiketlenen başka bir kullanıcının V-Coin miktarını gösterir.\n"
                "• **Kullanım:** `v!wallet` veya `v!wallet @Kullanici`\n"
                "• **Alternatif Komutlar:** `v!bakiye`, `v!vcoints`"
            ),
            inline=False
        )
        embed_economy.set_footer(text="Modül 4/5 • Ekonomi ve Liderlik • V-Tracker.gg", icon_url=bot_avatar)
        embeds["economy"] = embed_economy

        # -----------------------------------------------------------------
        # MODÜL 5: HATA YÖNETİMİ VE SSS (FAQ)
        # -----------------------------------------------------------------
        embed_faq = discord.Embed(
            title="🛡️ Hata Yönetimi ve Sık Sorulan Sorular (SSS)",
            description=(
                "Komut kullanımında veya API yanıtlarında karşılaşılan yaygın "
                "istisnaların çözüm yolları ve hata yakalama mekanizmaları."
            ),
            color=0xE74C3C
        )
        embed_faq.set_thumbnail(url=bot_avatar)
        embed_faq.add_field(
            name="❌ 'Bu komutu kullanmak için kayıt olmalısın' Hatası",
            value="**Sebep:** Belirtilen Discord ID veritabanında bulunmuyor.\n**Çözüm:** `v!register` komutu ile hesabınızı sisteme tanıtın.",
            inline=False
        )
        embed_faq.add_field(
            name="❌ 'Riot hesabı bulunamadı' Hatası",
            value="**Sebep:** Girilen Riot ID (`İsim#Tag`) hatalı veya oyuncu gizlilik modunda.\n**Çözüm:** Doğru etiket formatı kullandığınızdan emin olun.",
            inline=False
        )
        embed_faq.add_field(
            name="⚡ Otomatik Hata Yakalama (Error Handler)",
            value="Bot, eksik argüman veya geçersiz veri girişlerinde kullanıcıyı bilgilendiren dahili `on_command_error` dinleyicisine sahiptir.",
            inline=False
        )
        embed_faq.set_footer(text="Modül 5/5 • Hata Yönetimi ve SSS • V-Tracker.gg", icon_url=bot_avatar)
        embeds["faq"] = embed_faq

        return embeds

    @commands.command(name="vhelp", aliases=["help", "yardim", "komutlar"])
    async def vhelp_command(self, ctx):
        """
        V-Tracker.gg botunun modül bazlı açılır menülü ana yardım merkezini 
        çalıştıran temel komut fonksiyonudur.
        """
        logger.info(f"Yardım komutu tetiklendi. İsteyen: {ctx.author} (ID: {ctx.author.id})")
        
        # Modül embed'lerini oluştur
        embeds_dict = self.build_module_embeds(ctx)
        
        # Varsayılan açılış embed'i olarak 'general' modülünü belirle
        initial_embed = embeds_dict["general"]
        
        # İnteraktif arayüz view nesnesini oluştur
        view = MasterHelpPaginationView(embeds_dict)
        
        # Mesajı gönder
        await ctx.send(embed=initial_embed, view=view)


# =====================================================================
# 4. BOT SETUP FONKSİYONU
# =====================================================================

async def setup(bot):
    """
    Discord.py uzantı mimarisi (Cog) yükleyicisi. 
    Bu fonksiyon çağrıldığında VTrackerMasterHelpCog bot bünyesine dahil edilir.
    """
    await bot.add_cog(VTrackerMasterHelpCog(bot))
    logger.info("VTrackerMasterHelpCog başarıyla yüklendi ve aktif hale getirildi.")