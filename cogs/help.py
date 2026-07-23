# -*- coding: utf-8 -*-
"""
Modül: cogs.help
Gelişmiş, Seçim Menülü ve Butonlu İnteraktif Yardım Sistemi.
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

# ==========================================
# 1. LOGLAMA VE YAPILANDIRMA (CONFIGURATION)
# ==========================================

logger = logging.getLogger("VTracker.HelpSystem")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Sabit Değerler (Constants)
WEB_PANEL_URL = "https://valorant-bot-x6tv.onrender.com/"
SUPPORT_SERVER_URL = "https://discord.gg/vtracker" # Kendi sunucu linkinle değiştirebilirsin
BOT_VERSION = "v2.5.0"
THEME_COLOR_DEFAULT = 0xFA4454  # Valorant Kırmızısı
THEME_COLOR_SUCCESS = 0x00FF99
THEME_COLOR_WARNING = 0xF1C40F
THEME_COLOR_ERROR = 0xE74C3C
THEME_COLOR_INFO = 0x00F0FF

# ==========================================
# 2. VERİ YÖNETİMİ VE İÇERİK DEPOSU (DATA STORE)
# ==========================================

class HelpDataStore:
    """Yardım menüsünde kullanılacak tüm metinleri ve komut verilerini barındırır."""
    
    CATEGORIES = {
        "general": {
            "label": "Genel Bakış",
            "description": "Botun temel özellikleri ve web paneli.",
            "emoji": "📋",
            "color": THEME_COLOR_INFO
        },
        "stats": {
            "label": "Valorant İstatistikleri",
            "description": "K/D, ACS, Rank ve Ajan performansları.",
            "emoji": "📊",
            "color": THEME_COLOR_DEFAULT
        },
        "tactical": {
            "label": "Taktiksel Analiz",
            "description": "Harita kontrolü ve derinlemesine maç verileri.",
            "emoji": "🧠",
            "color": 0x9B59B6
        },
        "economy": {
            "label": "V-Coin & Ekonomi",
            "description": "Sanal bakiye sistemi ve sıralamalar.",
            "emoji": "💰",
            "color": THEME_COLOR_WARNING
        },
        "account": {
            "label": "Hesap & Kayıt",
            "description": "Riot ID eşleştirme ve profil ayarları.",
            "emoji": "🔗",
            "color": THEME_COLOR_SUCCESS
        }
    }

    COMMANDS = {
        "stats": [
            {"name": "v!stats [RiotID]", "desc": "Oyuncunun genel K/D, Kazanma Oranı ve güncel Rank bilgisini getirir."},
            {"name": "v!match [RiotID]", "desc": "Son rekabetçi maçın detaylı özetini (First Blood, KAST, ADR) sunar."},
            {"name": "v!live", "desc": "Şu an oynadığınız canlı maçtaki oyuncuların ranklarını gösterir."}
        ],
        "tactical": [
            {"name": "v!agent [AjanAdı]", "desc": "**Örnek:** `v!agent Omen` veya `v!agent Jett`\nSeçili ajan için sis atma, entry alma ve ulti kullanım istatistiklerini analiz eder."},
            {"name": "v!map [HaritaAdı]", "desc": "Harita başına savunma/saldırı kazanma oranlarınızı (Winrate) hesaplar."},
            {"name": "v!weapons", "desc": "Vandal vs Phantom kullanım oranları ve Headshot yüzdelerini (HS%) listeler."}
        ],
        "economy": [
            {"name": "v!wallet", "desc": "Güncel V-Coin bakiyenizi görüntüler."},
            {"name": "v!daily", "desc": "Günlük giriş ödülünüzü (V-Coin) alırsınız."},
            {"name": "v!top", "desc": "Sunucudaki veya globaldeki en zengin oyuncuları listeler."},
            {"name": "v!shop", "desc": "V-Coin kullanarak Discord profilinize Valorant arka planları satın alın."}
        ],
        "account": [
            {"name": "v!register [RiotID#Tag]", "desc": "Discord hesabınızı Valorant hesabınızla kalıcı olarak eşleştirir."},
            {"name": "v!profile", "desc": "Discord üzerindeki kişiselleştirilmiş V-Tracker profil kartınızı oluşturur."},
            {"name": "v!unlink", "desc": "Mevcut bağlı Riot hesabınızın bağlantısını keser."}
        ]
    }

# ==========================================
# 3. EMBED OLUŞTURUCU (EMBED BUILDER)
# ==========================================

class EmbedGenerator:
    """Dinamik olarak tüm sayfa embedlerini üreten yardımcı sınıf."""
    
    @staticmethod
    def _base_embed(title: str, description: str, color: int, ctx: commands.Context) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
        if ctx.bot.user and ctx.bot.user.display_avatar:
            embed.set_author(name="V-Tracker.gg Yardım Merkezi", icon_url=ctx.bot.user.display_avatar.url)
            embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        embed.set_footer(text=f"Talep eden: {ctx.author.display_name} • Bot Sürümü: {BOT_VERSION}", icon_url=ctx.author.display_avatar.url)
        return embed

    @classmethod
    def get_general_embed(cls, ctx: commands.Context) -> discord.Embed:
        desc = (
            "**V-Tracker.gg**, rekabetçi Valorant oyuncuları için geliştirilmiş "
            "en kapsamlı analiz ve istatistik botudur. Amacımız sadece K/D göstermek değil, "
            "oyun içi performansını derinlemesine incelemektir.\n\n"
            "Aşağıdaki **açılır menüyü** kullanarak kategoriler arasında geçiş yapabilir, "
            "komutların detaylı kullanım örneklerini inceleyebilirsin.\n\n"
            f"🌐 **Web Panel:** [Tıkla ve Sisteme Giriş Yap]({WEB_PANEL_URL})\n"
            f"🛠️ **Destek Sunucusu:** [Yardım için Katıl]({SUPPORT_SERVER_URL})"
        )
        embed = cls._base_embed("V-Tracker.gg - Genel Bakış", desc, HelpDataStore.CATEGORIES["general"]["color"], ctx)
        
        embed.add_field(
            name="🚀 Hızlı Başlangıç",
            value="1. Önce `v!register İsim#Tag` yazarak hesabını bağla.\n"
                  "2. Ardından `v!stats` yazarak genel durumunu gör.\n"
                  "3. Web paneline girerek gelişmiş grafiklerini incele.",
            inline=False
        )
        embed.add_field(
            name="🤖 Gelişmiş Taktik Motoru",
            value="Özellikle Immortal 3 ve radyant seviyesi verileri referans alınarak, oynadığın karakterlerin (örn: Jett, Omen) taktiksel zeka (game sense) ve harita kontrol metriklerini analiz eder.",
            inline=False
        )
        return embed

    @classmethod
    def get_category_embed(cls, ctx: commands.Context, category_id: str) -> discord.Embed:
        cat_data = HelpDataStore.CATEGORIES.get(category_id)
        if not cat_data:
            return cls.get_general_embed(ctx)

        title = f"{cat_data['emoji']} V-Tracker.gg - {cat_data['label']}"
        desc = f"*{cat_data['description']}*\n\nAşağıda bu kategoriye ait komutları bulabilirsiniz. Parametrelerdeki köşeli parantezler `[ ]` zorunlu değildir."
        embed = cls._base_embed(title, desc, cat_data['color'], ctx)

        cmds = HelpDataStore.COMMANDS.get(category_id, [])
        for cmd in cmds:
            embed.add_field(name=f"🔹 `{cmd['name']}`", value=cmd['desc'], inline=False)

        return embed

# ==========================================
# 4. ARAYÜZ BİLEŞENLERİ (UI COMPONENTS)
# ==========================================

class HelpDropdown(discord.ui.Select):
    """Kategoriler arası geçiş sağlayan açılır menü."""
    
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = []
        
        # Seçenekleri dinamik olarak HelpDataStore'dan oluştur
        for key, data in HelpDataStore.CATEGORIES.items():
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"],
                    emoji=data["emoji"],
                    value=key
                )
            )
            
        super().__init__(
            placeholder="İncelemek istediğiniz kategoriyi seçin...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
            custom_id="help_dropdown_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        # Yetkisiz kullanıcı engellemesi (Sadece komutu yazan kullanabilir)
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Bu menüyü sadece komutu yazan kişi kullanabilir.", ephemeral=True)
            return

        selected_category = self.values[0]
        
        if selected_category == "general":
            new_embed = EmbedGenerator.get_general_embed(self.ctx)
        else:
            new_embed = EmbedGenerator.get_category_embed(self.ctx, selected_category)

        # Görünümü güncelle
        await interaction.response.edit_message(embed=new_embed)


class HelpButtons(discord.ui.View):
    """Aksiyon butonlarını ve menü yönetimini içeren View sınıfı."""
    
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=240) # 4 dakika zaman aşımı
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        
        # Dropdown menüyü View'a ekle
        self.add_item(HelpDropdown(ctx))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Kullanıcı kontrolü: Başkalarının butonlara basmasını engeller."""
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message("Bununla etkileşime geçemezsin. Kendi `v!help` menünü oluşturabilirsin.", ephemeral=True)
        return False

    async def on_timeout(self):
        """Zaman aşımına uğradığında menüyü devre dışı bırakır (Sistem yorulmasın diye)."""
        for item in self.children:
            item.disabled = True
            
        if self.message:
            try:
                # Sadece içeriği güncelleyip butonları grileştirir
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Ana Sayfa", style=discord.ButtonStyle.primary, emoji="🏠", row=1, custom_id="help_btn_home")
    async def btn_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Kullanıcıyı tekrar ilk genel bakış sayfasına döndürür."""
        embed = EmbedGenerator.get_general_embed(self.ctx)
        # Dropdown'ın görsel değerini sıfırlamak (görsel düzeltme)
        for item in self.children:
            if isinstance(item, HelpDropdown):
                item._underlying.options = item.options # Seçili değeri temizleme taktiği
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Çöp Kutusuna At", style=discord.ButtonStyle.danger, emoji="🗑️", row=1, custom_id="help_btn_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sohbet kirliliğini önlemek için mesajı siler."""
        try:
            await interaction.message.delete()
        except discord.Forbidden:
            await interaction.response.send_message("Mesajı silmek için yetkim yok.", ephemeral=True)
        except discord.HTTPException as e:
            logger.error(f"Mesaj silinirken hata oluştu: {e}")

    @discord.ui.button(label="Web Paneli", style=discord.ButtonStyle.link, url=WEB_PANEL_URL, emoji="🌐", row=1)
    async def btn_web(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Statik link butonu (callback gerektirmez)."""
        pass

# ==========================================
# 5. KOMUTLAR VE COG YAPISI (COG & COMMANDS)
# ==========================================

class CustomHelpCommand(commands.Cog, name="Yardım Sistemi"):
    """
    Kullanıcılara botun tüm özelliklerini gelişmiş bir arayüzle sunan Cog sınıfı.
    Bu sistem, varsayılan discord.py yardım sisteminin yerine geçecek şekilde tasarlanmıştır.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Bot yüklendiğinde hafızadaki komut listesini analiz etmek için burası kullanılabilir.

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("CustomHelpCommand (Yardım Menüsü) başarıyla sisteme entegre edildi.")

    @commands.command(
        name="help",
        aliases=["vhelp", "yardim", "yardım", "komutlar", "info"],
        brief="Gelişmiş yardım menüsünü açar.",
        description="Açılır menüler ve butonlarla donatılmış interaktif bot rehberini başlatır."
    )
    async def advanced_help(self, ctx: commands.Context, *, specific_command: str = None):
        """
        Ana yardım komutu.
        Parametre girilmezse interaktif menüyü açar.
        Spesifik bir komut yazılırsa (örn: v!help stats) o komutun detaylarını arar.
        """
        
        # 1. Senaryo: Kullanıcı spesifik bir komut hakkında bilgi istiyorsa (Örn: v!help stats)
        if specific_command:
            specific_command = specific_command.lower()
            found_cmd = None
            category_found = None
            
            # Veri deposunda komutu ara
            for cat, cmds in HelpDataStore.COMMANDS.items():
                for cmd in cmds:
                    # 'v!stats [RiotID]' şeklindeki isimden sadece 'stats' kısmını ayıklama
                    base_name = cmd["name"].split()[0].replace("v!", "").lower()
                    if specific_command == base_name or specific_command in cmd["name"].lower():
                        found_cmd = cmd
                        category_found = cat
                        break
                if found_cmd:
                    break
                    
            if found_cmd:
                embed = discord.Embed(
                    title=f"Komut Detayı: {found_cmd['name']}",
                    description=found_cmd["desc"],
                    color=THEME_COLOR_SUCCESS
                )
                embed.add_field(name="Kategori", value=HelpDataStore.CATEGORIES[category_found]["label"])
                embed.set_footer(text="Parametrelerdeki [ ] işaretleri opsiyonel, < > işaretleri zorunludur.")
                return await ctx.send(embed=embed)
            else:
                # Komut bulunamadı
                embed = discord.Embed(
                    title="❌ Komut Bulunamadı",
                    description=f"`{specific_command}` adında bir komut veya kategori bulamadım.\nTüm komutları görmek için sadece `v!help` yazabilirsin.",
                    color=THEME_COLOR_ERROR
                )
                return await ctx.send(embed=embed)

        # 2. Senaryo: Hiçbir parametre girilmedi, ana interaktif menüyü başlat.
        try:
            # Genel embed'i oluştur
            embed = EmbedGenerator.get_general_embed(ctx)
            
            # Gelişmiş View'ı (Butonlar + Dropdown) oluştur
            view = HelpButtons(ctx)
            
            # Mesajı gönder ve view objesine ata (Zaman aşımında düzenleyebilmek için)
            view.message = await ctx.send(embed=embed, view=view)
            
        except discord.Forbidden:
            logger.warning(f"Kanalda mesaj gönderme yetkim yok. Sunucu/Kanal: {ctx.guild.name} / {ctx.channel.name}")
            try:
                await ctx.author.send("Görünüşe göre o kanalda mesaj gönderme yetkim yok. Yardım menüsünü buradan inceleyebilirsin!")
            except discord.Forbidden:
                pass
        except Exception as e:
            logger.error(f"Help komutu çalıştırılırken beklenmeyen bir hata oluştu: {e}")
            await ctx.send("Menü oluşturulurken sistemsel bir hata meydana geldi. Lütfen geliştiriciye bildirin.", delete_after=10)

    @commands.command(name="ping", hidden=True)
    async def check_ping(self, ctx: commands.Context):
        """Gecikme süresini ölçmek için gizli komut."""
        latency = round(self.bot.latency * 1000)
        color = THEME_COLOR_SUCCESS if latency < 100 else THEME_COLOR_WARNING if latency < 200 else THEME_COLOR_ERROR
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Güncel Gecikme (API): **{latency}ms**",
            color=color
        )
        await ctx.send(embed=embed)

# ==========================================
# 6. YÜKLEME VE ÇATI BAĞLANTISI (SETUP)
# ==========================================

async def setup(bot: commands.Bot):
    """
    Cog'u bota ekleyen asenkron kurulum fonksiyonu.
    Mevcut varsayılan help komutu varsa, çakışmayı önlemek için güvenli bir şekilde siler.
    """
    try:
        # Eğer main.py'de kapatılmamışsa burada zorla siliyoruz.
        # Bu işlem daha önce "hellp not found" gibi hatalara sebep olmuştu.
        # remove_command hatasını handle etmek için try-except bloğu hayat kurtarır.
        bot.remove_command("help")
        logger.info("Varsayılan 'help' komutu sistemden kaldırıldı.")
    except Exception as e:
        logger.debug(f"Varsayılan help komutu zaten yok veya kaldırılamadı: {e}")

    # Yeni sistemimizi ekliyoruz.
    await bot.add_cog(CustomHelpCommand(bot))
    logger.info("V-Tracker Gelişmiş Yardım Sistemi Yüklendi ve Aktif!")