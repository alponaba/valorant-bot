from __future__ import annotations

import discord
from discord.ext import commands

from theme import panel


class HelpView(discord.ui.View):
    def __init__(self, pages: dict[str, discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.author_id = author_id
        self.current = "home"
        self._sync_styles()

    def _sync_styles(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.primary if child.custom_id == self.current else discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu yardım paneli sana ait değil.", ephemeral=True)
            return False
        return True

    async def show(self, interaction: discord.Interaction, key: str):
        self.current = key
        self._sync_styles()
        await interaction.response.edit_message(embed=self.pages[key], view=self)

    @discord.ui.button(label="Genel", custom_id="home")
    async def home_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self.show(interaction, "home")

    @discord.ui.button(label="Oyuncu", custom_id="player")
    async def player_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self.show(interaction, "player")

    @discord.ui.button(label="Otomasyon", custom_id="automation")
    async def automation_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self.show(interaction, "automation")

    @discord.ui.button(label="Topluluk", custom_id="community")
    async def community_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self.show(interaction, "community")

    @discord.ui.button(label="Güvenlik", custom_id="security")
    async def security_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self.show(interaction, "security")


class Help(commands.Cog):
    def __init__(self, bot): self.bot = bot

    def pages(self) -> dict[str, discord.Embed]:
        home = panel("V-Tracker", "Valorant oyuncu analizi, otomasyon, topluluk ve sunucu güvenliğini tek botta birleştiren sistem.")
        home.add_field(
            name="Tüm Özellikler",
            value=(
                "**Oyuncu analizi:** profil paneli, V-Score, Player DNA, koçluk, maç kartı, trend, rekorlar, ajan/harita intelligence, streak ve karşılaştırma\n"
                "**Otomasyon:** rank takibi, yeni maç algılama, rank rol senkronizasyonu, snapshot geçmişi, kişisel rekor kaydı ve bildirim tercihleri\n"
                "**Topluluk:** rival sistemi, duo uyumu, LFG ilanları, haftalık gelişim sıralaması\n"
                "**Güvenlik:** anti-raid, risk score, karantina, scam-link kalıpları, mass mention, spam fingerprint, invite filtresi, audit log ve warn escalation\n"
                "**Ekonomi:** V-Coin, günlük/haftalık ödül, mağaza, kozmetik, görevler ve leaderboard"
            ), inline=False,
        )
        home.add_field(
            name="En Son Eklenenler",
            value=(
                "• Tekrarsız kişisel koç önerileri ve koç geçmişi\n"
                "• Otomatik rank / yeni maç takibi\n"
                "• Player DNA, tilt skoru ve kişisel rekorlar\n"
                "• Rival, duo compatibility ve LFG\n"
                "• Anti-raid, karantina ve AutoMod risk sistemi\n"
                "• Daily / Weekly report ve weekly growth leaderboard"
            ), inline=False,
        )
        home.add_field(name="Hızlı Başlangıç", value="`v!register` → `v!stats` → `v!coach` → `v!notifications`", inline=False)

        player = panel("Oyuncu Özellikleri", "Kişisel Valorant performansını okumak ve geliştirmek için komutlar.")
        player.add_field(name="Ana Panel", value="`stats` / `profile` / `hub`\nButonlarla Genel, Performans, Ajan ve Harita, Koç sekmeleri.", inline=False)
        player.add_field(name="Derin Analiz", value="`playerdna` • `intelligence` • `coach` • `trend` • `records` • `streak`", inline=False)
        player.add_field(name="Maç ve Kıyas", value="`lastmatch` • `compare @üye` • `dailyreport` • `weeklyreport`", inline=False)
        player.add_field(name="Taktik", value="`agents` • `comp <harita>` • `counterstrat <stil>`", inline=False)

        automation = panel("Otomasyon Sistemi", "Komut yazmadan arka planda çalışan takip katmanı.")
        automation.add_field(name="Rank Tracker", value="Rank/RR değişimini izler, snapshot kaydeder ve uygun rank rolünü senkronize eder.", inline=False)
        automation.add_field(name="Match Tracker", value="Yeni maç anahtarını algılar; ilk taramayı sessiz baseline kabul eder ve yalnızca sonraki değişiklikleri duyurur.", inline=False)
        automation.add_field(name="Bildirim Merkezi", value="`notifications`\n`notifications rank on/off`\n`notifications match on/off`\n`notifications report on/off`", inline=False)
        automation.add_field(name="Raporlama", value="`dailyreport` • `weeklyreport` • `weeklytop`", inline=False)

        community = panel("Topluluk Özellikleri", "Sunucudaki oyuncuların birlikte oynamasını ve rekabet etmesini kolaylaştırır.")
        community.add_field(name="Rival", value="`rival @üye` • `rivalstats`", inline=True)
        community.add_field(name="Duo", value="`duo @üye`", inline=True)
        community.add_field(name="LFG", value="`lfg [rol] [mic] [mod]` • `lfgclose`", inline=True)
        community.add_field(name="Ekonomi", value="`balance` • `daily` • `weekly` • `transfer` • `leaderboard` • `shop` • `buy` • `customize` • `challenges`", inline=False)

        security = panel("Güvenlik ve Moderasyon", "Sunucu güvenliğini otomatik risk puanı ve geri döndürülebilir aksiyonlarla korur.")
        security.add_field(name="Koruma", value="Anti-raid • yeni hesap risk analizi • mass mention • scam-link kalıpları • spam fingerprint • isteğe bağlı invite filtresi", inline=False)
        security.add_field(name="Karantina", value="`risk @üye` • `quarantine @üye` • `unquarantine @üye` • `modpanel`", inline=False)
        security.add_field(name="Moderasyon", value="`warn` • `warnings` • `timeout` • `untimeout` • `clear` • `lockdown` • `unlock` • `kick` • `ban` • `auditlog`", inline=False)
        security.add_field(name="Sunucu Araçları", value="`setup` • `status` • `suggest` • `join` • `leave`", inline=False)
        return {"home": home, "player": player, "automation": automation, "community": community, "security": security}

    @commands.hybrid_command(name="help", aliases=["yardim", "yardım"], description="V-Tracker özellik ve komut merkezini gösterir.")
    async def help(self, ctx):
        pages = self.pages()
        await ctx.send(embed=pages["home"], view=HelpView(pages, ctx.author.id))


async def setup(bot): await bot.add_cog(Help(bot))
