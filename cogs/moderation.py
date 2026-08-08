from datetime import timedelta
import discord
from discord.ext import commands
from database import db
from theme import error, info, success

class Moderation(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.hybrid_command(name="clear",aliases=["sil","purge"],description="Mesaj temizler.")
    @commands.has_permissions(manage_messages=True)
    async def clear(self,ctx,amount:int=10):
        if not ctx.guild: return await ctx.send(embed=error("Sunucu gerekli","Bu komut DM'de kullanılamaz."))
        amount=max(1,min(amount,100)); deleted=await ctx.channel.purge(limit=amount)
        await ctx.send(embed=success("Temizlendi",f"**{len(deleted)}** mesaj silindi."),delete_after=4)
    @commands.hybrid_command(name="warn",aliases=["uyar"],description="Kullanıcıya uyarı kaydı ekler.")
    @commands.has_permissions(moderate_members=True)
    async def warn(self,ctx,member:discord.Member,*,reason:str="Sebep belirtilmedi"):
        wid=await db.add_warning(ctx.guild.id,member.id,ctx.author.id,reason); await ctx.send(embed=success("Uyarı kaydedildi",f"{member.mention} • #{wid}\n{reason}"))
    @commands.hybrid_command(name="warnings",aliases=["uyarilar","uyarılar"],description="Kullanıcının son uyarılarını listeler.")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self,ctx,member:discord.Member):
        rows=await db.get_warnings(ctx.guild.id,member.id); e=info("Uyarı geçmişi",member.mention)
        e.add_field(name="Son kayıtlar",value="\n".join(f"`#{r['id']}` {r['reason']}" for r in rows) or "Uyarı yok",inline=False); await ctx.send(embed=e)
    @commands.hybrid_command(name="timeout",aliases=["mute"],description="Kullanıcıya geçici timeout uygular.")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self,ctx,member:discord.Member,minutes:int=10,*,reason:str="Moderatör işlemi"):
        minutes=max(1,min(minutes,10080)); await member.timeout(timedelta(minutes=minutes),reason=reason); await ctx.send(embed=success("Timeout",f"{member.mention} • {minutes} dakika"))
    @commands.hybrid_command(name="untimeout",aliases=["unmute"],description="Timeout'u kaldırır.")
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self,ctx,member:discord.Member):
        await member.timeout(None); await ctx.send(embed=success("Timeout kaldırıldı",member.mention))
    @commands.hybrid_command(name="kick",description="Kullanıcıyı sunucudan atar.")
    @commands.has_permissions(kick_members=True)
    async def kick(self,ctx,member:discord.Member,*,reason:str="Moderatör işlemi"):
        await member.kick(reason=reason); await ctx.send(embed=success("Kullanıcı atıldı",str(member)))
    @commands.hybrid_command(name="ban",description="Kullanıcıyı yasaklar.")
    @commands.has_permissions(ban_members=True)
    async def ban(self,ctx,member:discord.Member,*,reason:str="Moderatör işlemi"):
        await member.ban(reason=reason); await ctx.send(embed=success("Kullanıcı yasaklandı",str(member)))
    @commands.hybrid_command(name="lockdown",aliases=["kilit"],description="Bulunduğun kanalı yazmaya kapatır.")
    @commands.has_permissions(manage_channels=True)
    async def lockdown(self,ctx):
        overwrite=ctx.channel.overwrites_for(ctx.guild.default_role); overwrite.send_messages=False; await ctx.channel.set_permissions(ctx.guild.default_role,overwrite=overwrite); await ctx.send(embed=success("Kanal kilitlendi","@everyone mesaj gönderemez."))
    @commands.hybrid_command(name="unlock",description="Kanal yazma kilidini kaldırır.")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self,ctx):
        overwrite=ctx.channel.overwrites_for(ctx.guild.default_role); overwrite.send_messages=None; await ctx.channel.set_permissions(ctx.guild.default_role,overwrite=overwrite); await ctx.send(embed=success("Kanal açıldı","Varsayılan mesaj izni geri getirildi."))

async def setup(bot): await bot.add_cog(Moderation(bot))
