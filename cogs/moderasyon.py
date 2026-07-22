import discord
from discord.ext import commands
import datetime
import json
import os
import asyncio  # <-- Hatanın çözümü için bu kütüphane eklendi

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.warns_file = "warns.json"

    def load_warns(self):
        if not os.path.exists(self.warns_file):
            return {}
        try:
            with open(self.warns_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_warns(self, data):
        with open(self.warns_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi."):
        """Kullanıcıyı sunucudan yasaklar."""
        if member.top_role >= ctx.author.top_role:
            await ctx.send("❌ Sizinle aynı veya daha yüksek roldeki birini yasaklayamazsınız!")
            return

        await member.ban(reason=f"{ctx.author} tarafından: {reason}")
        
        embed = discord.Embed(
            title="🔨 KULLANICI YASAKLANDI (BAN)",
            description=f"**Yasaklanan:** {member.mention}\n**Yetkili:** {ctx.author.mention}\n**Sebep:** `{reason}`",
            color=0xFF0055
        )
        await ctx.send(embed=embed)

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi."):
        """Kullanıcıyı sunucudan atar."""
        if member.top_role >= ctx.author.top_role:
            await ctx.send("❌ Sizinle aynı veya daha yüksek roldeki birini sunucudan atamazsınız!")
            return

        await member.kick(reason=f"{ctx.author} tarafından: {reason}")

        embed = discord.Embed(
            title="👢 KULLANICI ATILDI (KICK)",
            description=f"**Atılan:** {member.mention}\n**Yetkili:** {ctx.author.mention}\n**Sebep:** `{reason}`",
            color=0xFFAA00
        )
        await ctx.send(embed=embed)

    @commands.command(name="mute", aliases=["timeout"])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, minutes: int, *, reason: str = "Sebep belirtilmedi."):
        """Kullanıcıya süreli susturma (Timeout) uygular."""
        if member.top_role >= ctx.author.top_role:
            await ctx.send("❌ Sizinle aynı veya daha yüksek roldeki birini susturamazsınız!")
            return

        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"{ctx.author} tarafından: {reason}")

        embed = discord.Embed(
            title="🔇 KULLANICI SUSTURULDU (MUTE)",
            description=f"**Susturulan:** {member.mention}\n**Süre:** `{minutes} Dakika`\n**Yetkili:** {ctx.author.mention}\n**Sebep:** `{reason}`",
            color=0xFFAA00
        )
        await ctx.send(embed=embed)

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        """Kullanıcının susturmasını kaldırır."""
        await member.timeout(None)
        await ctx.send(f"🔊 {member.mention} kullanıcısının susturması kaldırıldı.")

    @commands.command(name="clear", aliases=["sil", "purge"])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        """Sohbet kanalındaki mesajları toplu siler."""
        if amount > 100:
            await ctx.send("⚠️ Tek seferde en fazla 100 mesaj silebilirsiniz.")
            return

        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"🧹 `{len(deleted) - 1}` adet mesaj başarıyla silindi.")
        await asyncio.sleep(3)
        await msg.delete()

    @commands.command(name="warn", aliases=["uyar"])
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi."):
        """Kullanıcıya uyarı ekler."""
        warns = self.load_warns()
        user_id = str(member.id)

        if user_id not in warns:
            warns[user_id] = []

        warns[user_id].append({
            "reason": reason,
            "by": str(ctx.author),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        self.save_warns(warns)

        total_warns = len(warns[user_id])
        embed = discord.Embed(
            title="⚠️ UYARI EKLENDİ",
            description=f"**Kullanıcı:** {member.mention}\n**Toplam Uyarı:** `{total_warns}`\n**Sebep:** `{reason}`",
            color=0xFFAA00
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))