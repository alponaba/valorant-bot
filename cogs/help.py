from __future__ import annotations

import discord
from discord.ext import commands

from theme import panel


class HelpView(discord.ui.View):
    def __init__(self, pages: dict[str, discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.author_id = author_id
        self.current = "main"
        self._update()

    def _update(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.secondary
                if child.custom_id == self.current:
                    child.style = discord.ButtonStyle.primary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu yardım paneli sana ait değil.", ephemeral=True)
            return False
        return True

    async def _show(self, interaction: discord.Interaction, key: str):
        self.current = key
        self._update()
        await interaction.response.edit_message(embed=self.pages[key], view=self)

    @discord.ui.button(label="Ana", emoji="🏠", custom_id="main")
    async def main_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "main")

    @discord.ui.button(label="Oyuncu", emoji="🎯", custom_id="player")
    async def player_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "player")

    @discord.ui.button(label="Ekonomi", emoji="💰", custom_id="economy")
    async def economy_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "economy")

    @discord.ui.button(label="Sunucu", emoji="🛠️", custom_id="server")
    async def server_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "server")


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _pages(self) -> dict[str, discord.Embed]:
        e1 = panel("🌀 V-Tracker Komut Merkezi", "Prefix: `v!` • Slash komutları da desteklenir.")
        e1.add_field(name="Yeni V3 öne çıkanlar", value="• Dashboard tarzı `stats/profile`\n• Butonlu yardım merkezi\n• Güvenli verification\n• Global anti-spam\n• Admin audit log", inline=False)
        e1.add_field(name="Hızlı başla", value="1. `v!register`\n2. `v!stats`\n3. `v!coach`\n4. `v!daily`", inline=False)

        e2 = panel("🎯 Oyuncu Komutları", "Kişisel Valorant analizi ve oyuncu paneli")
        e2.add_field(name="Kayıt", value="`register` • `sync` • `verification`", inline=False)
        e2.add_field(name="Performans", value="`stats` • `lastmatch` • `compare @üye` • `coach`", inline=False)
        e2.add_field(name="Taktik", value="`agents` • `comp <harita>` • `counterstrat <stil>`", inline=False)

        e3 = panel("💰 Ekonomi & Profil", "V-Coin, kozmetik ve görevler")
        e3.add_field(name="Ekonomi", value="`balance` • `daily` • `weekly` • `transfer` • `leaderboard`", inline=False)
        e3.add_field(name="Kozmetik", value="`shop` • `buy` • `customize`", inline=False)
        e3.add_field(name="Görevler", value="`challenges`", inline=False)

        e4 = panel("🛠️ Sunucu & Moderasyon", "Yönetim, öneri ve servis araçları")
        e4.add_field(name="Sunucu", value="`suggest` • `join` • `leave` • `setup` • `status`", inline=False)
        e4.add_field(name="Moderasyon", value="`warn` • `warnings` • `timeout` • `untimeout` • `clear` • `lockdown` • `unlock` • `kick` • `ban` • `auditlog`", inline=False)
        return {"main": e1, "player": e2, "economy": e3, "server": e4}

    @commands.hybrid_command(name="help", aliases=["yardim", "yardım"], description="V-Tracker komutlarını gösterir.")
    async def help(self, ctx):
        pages = self._pages()
        await ctx.send(embed=pages["main"], view=HelpView(pages, ctx.author.id))


async def setup(bot):
    await bot.add_cog(Help(bot))
