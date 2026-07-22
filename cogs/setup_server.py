import discord
from discord.ext import commands
import asyncio

class ServerSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF

    @commands.command(name="kur", aliases=["setup", "sunucukur"])
    @commands.has_permissions(administrator=True)
    async def setup_server(self, ctx):
        """Botla %100 uyumlu hazır Valorant & Loglu sunucu yapısını kurar."""
        guild = ctx.guild

        confirm_embed = discord.Embed(
            title="⚠️ OTOMATİK SUNUCU KURULUMU",
            description=(
                "Bu işlem sunucuya hazır kategoriler, log kanalları (`mod-log`, `chat-log`) ve bot uyumlu roller ekleyecektir.\n"
                "Devam etmek istiyor musunuz? **30 saniye içinde `evet` yazın.**"
            ),
            color=self.V_CYAN
        )
        await ctx.send(embed=confirm_embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "evet"

        try:
            await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("❌ Kurulum işlemi zaman aşılanarak iptal edildi.")
            return

        status_msg = await ctx.send("🔄 **Sunucu şablonu ve log kanalları kuruluyor, lütfen bekleyin...**")

        # 1. ROLLERİN OLUŞTURULMASI
        roles_data = [
            {"name": "👑 Kurucu", "color": discord.Color.gold(), "hoist": True},
            {"name": "🛡️ Yönetici", "color": discord.Color.red(), "hoist": True},
            {"name": "⚡ Moderator", "color": discord.Color.blue(), "hoist": True},
            {"name": "🎬 Clip Master", "color": discord.Color.purple(), "hoist": True},
            {"name": "Oyuncu", "color": discord.Color.green(), "hoist": True},
        ]

        for r_info in roles_data:
            existing_role = discord.utils.get(guild.roles, name=r_info["name"])
            if not existing_role:
                await guild.create_role(
                    name=r_info["name"],
                    color=r_info["color"],
                    hoist=r_info["hoist"],
                    reason="[Otomatik Şablon Kurulumu]"
                )

        # 2. KATEGORİ VE KANALLARIN OLUŞTURULMASI (Loglar dahil)
        structure = {
            "📌 INFORMASYON": [
                {"name": "hoş-geldin", "type": "text"},
                {"name": "duyurular", "type": "text"},
                {"name": "kurallar", "type": "text"}
            ],
            "💬 TOPLULUK": [
                {"name": "sohbet", "type": "text"},
                {"name": "v-coin-bot", "type": "text"},
                {"name": "klip-paylaşım", "type": "text"}
            ],
            "🎮 VALORANT ODALARI": [
                {"name": "duo-arama", "type": "text"},
                {"name": "🔊 Squad #1 (5/5)", "type": "voice"},
                {"name": "🔊 Squad #2 (5/5)", "type": "voice"},
                {"name": "🔊 Duo #1 (2/2)", "type": "voice"}
            ],
            "🛠️ YÖNETİM & LOG": [
                {"name": "mod-log", "type": "text"},     # Moderasyon logları için
                {"name": "chat-log", "type": "text"},    # Mesaj silinme/düzenlenme logları için
                {"name": "🔒-yetkili-sohbet", "type": "text"}
            ]
        }

        for cat_name, channels in structure.items():
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                category = await guild.create_category(cat_name)

            for ch in channels:
                if ch["type"] == "text":
                    if not discord.utils.get(category.text_channels, name=ch["name"]):
                        await guild.create_text_channel(ch["name"], category=category)
                elif ch["type"] == "voice":
                    if not discord.utils.get(category.voice_channels, name=ch["name"]):
                        await guild.create_voice_channel(ch["name"], category=category)

        done_embed = discord.Embed(
            title="✅ SUNUCU ŞABLONU BAŞARIYLA KURULDU",
            description=(
                "**Oluşturulan Yapı:**\n"
                "• **Roller:** `Oyuncu`, `Clip Master`, `Moderator`, `Yönetici`, `Kurucu`\n"
                "• **Kanallar:** `hoş-geldin`, `sohbet`, `mod-log`, `chat-log` ve Ses Odaları\n\n"
                "*Artık `v!kur` komutu ile tüm log kanalları ve otomasyon altyapısı eksiksiz hazır hale getirilmiştir.*"
            ),
            color=0x00FF88
        )
        await status_msg.edit(content=None, embed=done_embed)

async def setup(bot):
    await bot.add_cog(ServerSetup(bot))