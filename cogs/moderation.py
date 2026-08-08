from __future__ import annotations

from datetime import timedelta

import discord
from discord.ext import commands

from database import db
from security import sanitize_text
from theme import error, panel, success


def can_act(moderator: discord.Member, target: discord.Member, bot_member: discord.Member) -> tuple[bool, str]:
    if target.id == moderator.id:
        return False, "Kendine işlem uygulayamazsın."
    if target == target.guild.owner:
        return False, "Sunucu sahibine işlem uygulanamaz."
    if target.top_role >= moderator.top_role and moderator != target.guild.owner:
        return False, "Hedef kullanıcının rolü senden eşit veya yüksek."
    if target.top_role >= bot_member.top_role:
        return False, "Botun rolü hedef kullanıcıdan yüksek değil."
    return True, "ok"


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="clear", aliases=["sil", "purge"], description="Mesaj temizler.")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10):
        if not ctx.guild:
            return await ctx.send(embed=error("Sunucu gerekli", "Bu komut DM'de kullanılamaz."))
        amount = max(1, min(amount, 100))
        deleted = await ctx.channel.purge(limit=amount)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, 0, "CLEAR", f"channel={ctx.channel.id} amount={len(deleted)}")
        await ctx.send(embed=success("Temizlendi", f"**{len(deleted)}** mesaj silindi."), delete_after=4)

    @commands.hybrid_command(name="warn", aliases=["uyar"], description="Kullanıcıya uyarı kaydı ekler.")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
        if not ctx.guild:
            return await ctx.send(embed=error("Sunucu gerekli", "Bu komut DM'de kullanılamaz."))
        ok, msg = can_act(ctx.author, member, ctx.guild.me)
        if not ok:
            return await ctx.send(embed=error("İşlem engellendi", msg))
        reason = sanitize_text(reason)
        wid = await db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, member.id, "WARN", reason)
        await ctx.send(embed=success("Uyarı kaydedildi", f"{member.mention} • #{wid}\n{reason}"))

    @commands.hybrid_command(name="warnings", aliases=["uyarilar", "uyarılar"], description="Kullanıcının son uyarılarını listeler.")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx, member: discord.Member):
        rows = await db.get_warnings(ctx.guild.id, member.id)
        e = panel("📒 Uyarı geçmişi", member.mention)
        e.add_field(name="Son kayıtlar", value="\n".join(f"`#{r['id']}` {r['reason']}" for r in rows) or "Uyarı yok", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="timeout", aliases=["mute"], description="Kullanıcıya geçici timeout uygular.")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int = 10, *, reason: str = "Moderatör işlemi"):
        minutes = max(1, min(minutes, 10080))
        ok, msg = can_act(ctx.author, member, ctx.guild.me)
        if not ok:
            return await ctx.send(embed=error("İşlem engellendi", msg))
        reason = sanitize_text(reason)
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, member.id, "TIMEOUT", f"{minutes}m | {reason}")
        await ctx.send(embed=success("Timeout", f"{member.mention} • {minutes} dakika"))

    @commands.hybrid_command(name="untimeout", aliases=["unmute"], description="Timeout'u kaldırır.")
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        ok, msg = can_act(ctx.author, member, ctx.guild.me)
        if not ok:
            return await ctx.send(embed=error("İşlem engellendi", msg))
        await member.timeout(None)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, member.id, "UNTIMEOUT", "timeout removed")
        await ctx.send(embed=success("Timeout kaldırıldı", member.mention))

    @commands.hybrid_command(name="kick", description="Kullanıcıyı sunucudan atar.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Moderatör işlemi"):
        ok, msg = can_act(ctx.author, member, ctx.guild.me)
        if not ok:
            return await ctx.send(embed=error("İşlem engellendi", msg))
        reason = sanitize_text(reason)
        await member.kick(reason=reason)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, member.id, "KICK", reason)
        await ctx.send(embed=success("Kullanıcı atıldı", str(member)))

    @commands.hybrid_command(name="ban", description="Kullanıcıyı yasaklar.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Moderatör işlemi"):
        ok, msg = can_act(ctx.author, member, ctx.guild.me)
        if not ok:
            return await ctx.send(embed=error("İşlem engellendi", msg))
        reason = sanitize_text(reason)
        await member.ban(reason=reason)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, member.id, "BAN", reason)
        await ctx.send(embed=success("Kullanıcı yasaklandı", str(member)))

    @commands.hybrid_command(name="lockdown", aliases=["kilit"], description="Bulunduğun kanalı yazmaya kapatır.")
    @commands.has_permissions(manage_channels=True)
    async def lockdown(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, 0, "LOCKDOWN", f"channel={ctx.channel.id}")
        await ctx.send(embed=success("Kanal kilitlendi", "@everyone mesaj gönderemez."))

    @commands.hybrid_command(name="unlock", description="Kanal yazma kilidini kaldırır.")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await db.log_admin_action(ctx.guild.id, ctx.author.id, 0, "UNLOCK", f"channel={ctx.channel.id}")
        await ctx.send(embed=success("Kanal açıldı", "Varsayılan mesaj izni geri getirildi."))

    @commands.hybrid_command(name="auditlog", aliases=["modlog"], description="Son moderasyon işlemlerini gösterir.")
    @commands.has_permissions(view_audit_log=True)
    async def auditlog(self, ctx):
        rows = await db.list_admin_audit(ctx.guild.id, 12)
        e = panel("🧾 Admin Audit Log", "Son kaydedilen moderasyon ve doğrulama işlemleri")
        if not rows:
            e.description = "Henüz kayıt yok."
        else:
            lines = []
            for row in rows:
                lines.append(f"`#{row['id']}` **{row['action']}** • actor `{row['actor_id']}` • target `{row['target_id']}`\n{row['detail']}")
            e.add_field(name="Kayıtlar", value="\n\n".join(lines), inline=False)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
