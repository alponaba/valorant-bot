import discord
from discord.ext import commands
import asyncio
from collections import defaultdict

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        # BURAYA KENDİ DISCORD USER ID'Nİ YAZ
        self.BOT_OWNER_ID = 760034004199407626 
        
        # Şüpheli işlem takibi için sayaçlar
        self.deletion_tracker = defaultdict(list)
        self.ban_tracker = defaultdict(list)

    def is_owner(self, ctx):
        return ctx.author.id == self.BOT_OWNER_ID

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Kanal silindiğinde çalışan koruma mekanizması."""
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.CHANNEL_DELETE):
            executor = entry.user
            if executor.id == self.BOT_OWNER_ID or executor.id == self.bot.user.id:
                return

            now = asyncio.get_event_loop().time()
            self.deletion_tracker[executor.id].append(now)
            
            # Son 10 saniyede 3'ten fazla kanal silindiye müdahale et (Anti-Nuke)
            recent_deletions = [t for t in self.deletion_tracker[executor.id] if now - t < 10]
            if len(recent_deletions) >= 3:
                # Kullanıcının rollerini alarak yetkisini kısıtla
                member = guild.get_member(executor.id)
                if member and member.top_role < guild.me.top_role:
                    try:
                        await member.edit(roles=[], reason="[Anti-Nuke] Hızlı kanal silme tespiti!")
                    except Exception:
                        pass

    @commands.command(name="lockdown", aliases=["kilit"])
    async def lockdown(self, ctx):
        """Sadece Bot Sahibinin kullanabileceği Acil Durum Sunucu Kilidi."""
        if not self.is_owner(ctx):
            await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir.")
            return

        embed = discord.Embed(
            title="🚨 ACİL DURUM KİLİDİ AKTİF!",
            description="Sunucu güvenlik sebebiyle geçici olarak mesaj gönderimine kapatılıyor.",
            color=0xFF0055
        )
        await ctx.send(embed=embed)

        for channel in ctx.guild.text_channels:
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            except Exception:
                continue

    @commands.command(name="unlock")
    async def unlock(self, ctx):
        """Acil durum kilidini kaldırır."""
        if not self.is_owner(ctx):
            await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir.")
            return

        for channel in ctx.guild.text_channels:
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=None)
            except Exception:
                continue

        await ctx.send("✅ Sunucu kilidi başarıyla kaldırıldı.")

async def setup(bot):
    await bot.add_cog(Security(bot))