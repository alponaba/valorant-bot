import discord
from discord.ext import commands

class HelpButtons(discord.ui.View):
    def __init__(self, bot, author_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.V_CYAN = 0x00F0FF

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Bu menüyü sadece komutu kullanan kişi değiştirebilir.", ephemeral=True)
            return False
        return True

    # 1. Moderasyon & Güvenlik
    @discord.ui.button(label="Moderasyon & Güvenlik", style=discord.ButtonStyle.danger, emoji="🛡️", row=0)
    async def mod_sec_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ MODERASYON & GÜVENLİK SİSTEMLERİ",
            description=(
                "`v!ban`, `v!kick`, `v!mute`, `v!unmute` — Klasik ceza komutları.\n"
                "`v!clear [Miktar]` — Belirtilen miktarda mesajı siler.\n"
                "`v!warn @kullanıcı [Sebep]` — Kullanıcıya uyarı verir.\n"
                "`v!lockdown` / `v!unlock` — Kanalları kilitler / açar.\n"
                "⚡ **Anti-Nuke:** Sunucu güvenliği arka planda otomatik korunur."
            ),
            color=0xFF0055
        )
        embed.set_footer(text="V-Tracker.gg • Moderation & Security")
        await interaction.response.edit_message(embed=embed, view=None)

    # 2. Valorant Stats, Profil & Coach
    @discord.ui.button(label="Valorant & Coach", style=discord.ButtonStyle.primary, emoji="🎯", row=0)
    async def val_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎯 VALORANT, STATS & KOÇLUK",
            description=(
                "`v!stats [İsim Tag]` — Canlı Riot API istatistiklerini gösterir.\n"
                "`v!register [İsim Tag]` — Riot ID'ni kaydeder.\n"
                "`v!me` — Kayıtlı profilini gösterir.\n"
                "`v!coach` — Oyun tarzına göre taktiksel koçluk verir.\n"
                "`v!custom_coach` — Özel koçluk asistanı.\n"
                "`v!lastmatch` — Son maçının detaylı analizini sunar.\n"
                "`v!leaderboards` — Sıralama tablosu."
            ),
            color=self.V_CYAN
        )
        embed.set_footer(text="V-Tracker.gg • Valorant Pro Suite")
        await interaction.response.edit_message(embed=embed, view=None)

    # 3. Taktik & Ajanlar (Agents, Comps, Counter Strats)
    @discord.ui.button(label="Taktik & Ajanlar", style=discord.ButtonStyle.secondary, emoji="🧩", row=1)
    async def tactics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🧩 AJANLAR & TAKTİKSEL ANALİZLER",
            description=(
                "`v!agents` — Valorant ajanları ve yetenek bilgileri.\n"
                "`v!comps` — Haritalara özel takım kompozisyonları.\n"
                "`v!counter_strats` — Rakip taktiklerine karşı stratejiler.\n"
                "`v!compare` — Oyuncu veya istatistik karşılaştırma."
            ),
            color=0xFFAA00
        )
        embed.set_footer(text="V-Tracker.gg • Tactical Systems")
        await interaction.response.edit_message(embed=embed, view=None)

    # 4. Ekonomi, Bahis & Ses (Economy, TTS, Temp Voice)
    @discord.ui.button(label="Ekonomi & Ses", style=discord.ButtonStyle.success, emoji="🪙", row=1)
    async def eco_voice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🪙 EKONOMİ, V-COİN & SES SİSTEMLERİ",
            description=(
                "`v!balance` (veya `v!bakiye`) — Cüzdanındaki V-Coin'i gösterir.\n"
                "`v!daily` — Günlük V-Coin ödülünü toplar.\n"
                "`v!bet [Miktar]` — V-Coin ile bahis oynar.\n"
                "`v!tts [Metin]` — Metni seste okutma sistemi.\n"
                "🔊 **Temp-Voice:** `➕ | Oda Oluştur` kanalına girerek geçici oda açabilirsin."
            ),
            color=0x00FF88
        )
        embed.set_footer(text="V-Tracker.gg • Economy & Voice")
        await interaction.response.edit_message(embed=embed, view=None)

    # 5. Klip, Kurulum & Diğerleri
    @discord.ui.button(label="Klip, Kurulum & Diğer", style=discord.ButtonStyle.secondary, emoji="🎬", row=2)
    async def misc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎬 KLİP, KURULUM & DİĞER MODÜLLER",
            description=(
                "`v!addclip [Başlık] [URL]` — Klip ekler, `v!clips` ile listeler.\n"
                "`v!kur` / `v!setup` — Logları ve rolleri otomatik kurar.\n"
                "`v!öneri [sunucu/bot] [Metin]` — Öneri ve talep iletir.\n"
                "`v!autojoin` / `v!challanges` — Otomatik katılım ve meydan okumalar."
            ),
            color=self.V_CYAN
        )
        embed.set_footer(text="V-Tracker.gg • Misc & Setup")
        await interaction.response.edit_message(embed=embed, view=None)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.bot.remove_command("help")

    @commands.command(name="help", aliases=["yardim", "yardım", "h"])
    async def help_command(self, ctx):
        """Tüm dosya modüllerini içeren kapsamlı yardım panosu."""
        embed = discord.Embed(
            title="⚡ V-TRACKER.GG | ANA KOMUT MERKEZİ",
            description=(
                "Projedeki tüm modüllere ve sistemlere ait komutları incelemek için **aşağıdaki butonları kullanabilirsin**.\n\n"
                "📌 **Kategori Grupları:**\n"
                "• 🛡️ **Moderasyon & Güvenlik** — Ceza, Lockdown, Anti-Nuke\n"
                "• 🎯 **Valorant & Coach** — `v!stats`, `v!me`, `v!coach`, `v!lastmatch`\n"
                "• 🧩 **Taktik & Ajanlar** — `v!agents`, `v!comps`, `v!counter_strats`\n"
                "• 🪙 **Ekonomi & Ses** — `v!balance`, `v!bet`, `v!tts`, Temp-Voice\n"
                "• 🎬 **Klip, Kurulum & Diğer** — `v!kur`, `v!öneri`, klipler ve meydan okumalar"
            ),
            color=self.V_CYAN
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user else None)
        embed.set_footer(text="V-Tracker.gg • v5.5 Ultimate Engine", icon_url=ctx.author.display_avatar.url)

        view = HelpButtons(self.bot, ctx.author.id)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))