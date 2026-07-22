import discord
from discord.ext import commands
import json
import os
from datetime import datetime

class ChallengesView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.uid = str(ctx.author.id)

    @discord.ui.button(label="📅 Günlük Görevler", style=discord.ButtonStyle.primary)
    async def daily_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu menüyü sadece komutu kullanan kişi yönetebilir!", ephemeral=True)

        embed = discord.Embed(
            title="📅 GÜNLÜK MEYDAN OKUMALAR",
            description="Her gün yenilenen 3 görevini tamamla, V-Coin ödüllerini topla!\n",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="1️⃣ Şansını Dene",
            value="• Açıklama: `v!bet` komutunu kullanarak 3 kez bahis oyna.\n• Ödül: **300 V-Coin**\n• Durum: 🔄 Aktif",
            inline=False
        )
        embed.add_field(
            name="2️⃣ Oyuncu Analizi",
            value="• Açıklama: `v!stats` komutuyla herhangi bir oyuncunun istatistiğini sorgula.\n• Ödül: **200 V-Coin**\n• Durum: 🔄 Aktif",
            inline=False
        )
        embed.add_field(
            name="3️⃣ Günlük Harçlık",
            value="• Açıklama: `v!daily` komutunu kullanarak günlük ödülünü al.\n• Ödül: **150 V-Coin**\n• Durum: 🔄 Aktif",
            inline=False
        )
        embed.set_footer(text="V-Tracker.gg • Günlük Görev Sistemi")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🗓️ Haftalık Görevler", style=discord.ButtonStyle.success)
    async def weekly_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu menüyü sadece komutu kullanan kişi yönetebilir!", ephemeral=True)

        embed = discord.Embed(
            title="🗓️ HAFTALIK MEYDAN OKUMALAR",
            description="Hafta boyunca tamamlayabileceğin büyük ödüllü 3 görev:\n",
            color=discord.Color.green()
        )
        embed.add_field(
            name="1️⃣ Büyük Kumarbaz",
            value="• Açıklama: Toplamda 5,000 V-Coin tutarında bahis oyna.\n• Ödül: **1,500 V-Coin**\n• Durum: 🔄 İlerleme Kaydediliyor",
            inline=False
        )
        embed.add_field(
            name="2️⃣ Özel Oda Kurucusu",
            value="• Açıklama: `v!özeloda` komutuyla toplam 5 kez ses kanalı oluştur.\n• Ödül: **1,000 V-Coin**\n• Durum: 🔄 İlerleme Kaydediliyor",
            inline=False
        )
        embed.add_field(
            name="3️⃣ Zirve Yarışı",
            value="• Açıklama: `v!leaderboards` komutunda ilk 5 oyuncu arasına girmeye çalış.\n• Ödül: **2,000 V-Coin**\n• Durum: 🔄 İlerleme Kaydediliyor",
            inline=False
        )
        embed.set_footer(text="V-Tracker.gg • Haftalık Görev Sistemi")
        await interaction.response.edit_message(embed=embed, view=self)

class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CHALLENGE_FILE = "challenges.json"

    @commands.command(name="görevler", aliases=["gorevler", "challenges", "challenge"])
    async def gorevler(self, ctx):
        """Günlük ve haftalık görev menüsünü açar."""
        embed = discord.Embed(
            title="🎯 V-TRACKER.GG | GÖREV MERKEZİ",
            description=f"Selam **{ctx.author.display_name}**!\nGünlük ve haftalık görevleri tamamlayarak ekstra V-Coin kazanabilirsin.\n\nLütfen incelemek istediğin kategori seç:",
            color=discord.Color.from_rgb(0, 240, 255)
        )
        embed.set_footer(text="Aşağıdaki butonları kullanarak görevler arasında geçiş yapabilirsin.")
        
        view = ChallengesView(ctx, self)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Challenges(bot))