from __future__ import annotations

import asyncio

import aiohttp
import discord
from discord.ext import commands

from cogs.stats import analyze, compute_vscore, player_dna
from config import LFG_CHANNEL_ID
from database import db
from theme import error, panel, success
from v4_store import store
from valorant_api import api


async def fetch_summary(user: dict):
    async with aiohttp.ClientSession() as session:
        payload = await api.matches(session, user["region"], user["puuid"], 10)
    s = analyze((payload or {}).get("data", []), user["puuid"])
    return s, compute_vscore(s, "Derecesiz")


class LFGJoinView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=3600)
        self.owner_id = owner_id

    @discord.ui.button(label="Takıma Katıl", style=discord.ButtonStyle.primary)
    async def join(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id == self.owner_id:
            return await interaction.response.send_message("Kendi ilanına katılamazsın.", ephemeral=True)
        owner = interaction.guild.get_member(self.owner_id) if interaction.guild else None
        if not owner:
            return await interaction.response.send_message("İlan sahibi artık sunucuda değil.", ephemeral=True)
        try:
            await owner.send(f"{interaction.user} LFG ilanına katılmak istiyor. Discord: {interaction.user.mention}")
        except discord.HTTPException:
            pass
        await interaction.response.send_message("İlan sahibine katılım isteğin iletildi.", ephemeral=True)


class Community(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.hybrid_command(name="rival", aliases=["rakip"], description="Bir kullanıcıyı kalıcı rival olarak seçer.")
    async def rival(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send(embed=error("Geçersiz rakip", "Kendini rival seçemezsin."))
        if not await db.get_user(member.id) or not await db.get_user(ctx.author.id):
            return await ctx.send(embed=error("Kayıt eksik", "İki kullanıcının da V-Tracker hesabı olmalı."))
        await store.set_rival(ctx.author.id, member.id)
        await ctx.send(embed=success("Rival ayarlandı", f"Artık rivalın **{member.display_name}**. `v!rivalstats` ile kıyaslayabilirsin."))

    @commands.hybrid_command(name="rivalstats", aliases=["rakipstats"], description="Rivalınla güncel karşılaştırma yapar.")
    async def rivalstats(self, ctx: commands.Context):
        rid = await store.get_rival(ctx.author.id)
        if not rid:
            return await ctx.send(embed=error("Rival yok", "Önce `v!rival @kullanıcı` kullan."))
        member = ctx.guild.get_member(int(rid)) if ctx.guild else None
        if not member:
            return await ctx.send(embed=error("Rival bulunamadı", "Seçili rival bu sunucuda görünmüyor."))
        u1, u2 = await db.get_user(ctx.author.id), await db.get_user(member.id)
        s1, s2 = await asyncio.gather(fetch_summary(u1), fetch_summary(u2))
        a, av = s1; b, bv = s2
        e = panel("Rival Board", f"**{ctx.author.display_name}** vs **{member.display_name}**")
        e.add_field(name=ctx.author.display_name, value=f"V-Score `{av}`\nK/D `{a['kd']}`\nHS `%{a['hs_rate']}`\nWR `%{a['winrate']}`", inline=True)
        e.add_field(name="Weekly Edge", value=ctx.author.mention if av >= bv else member.mention, inline=True)
        e.add_field(name=member.display_name, value=f"V-Score `{bv}`\nK/D `{b['kd']}`\nHS `%{b['hs_rate']}`\nWR `%{b['winrate']}`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="duo", aliases=["duoscore", "uyum"], description="İki oyuncunun duo uyumunu hesaplar.")
    async def duo(self, ctx: commands.Context, member: discord.Member):
        u1, u2 = await db.get_user(ctx.author.id), await db.get_user(member.id)
        if not u1 or not u2:
            return await ctx.send(embed=error("Kayıt eksik", "İki oyuncu da kayıtlı olmalı."))
        (s1, v1), (s2, v2) = await asyncio.gather(fetch_summary(u1), fetch_summary(u2))
        style1, dna1 = player_dna(s1); style2, dna2 = player_dna(s2)
        role_diversity = 15 if s1["main_agent"] != s2["main_agent"] else 5
        stability = max(0, 25 - abs(dna1["Consistency"] - dna2["Consistency"]) // 3)
        impact = min(30, int((dna1["Impact"] + dna2["Impact"]) / 7))
        aim_balance = max(0, 20 - int(abs(dna1["Aim"] - dna2["Aim"]) / 5))
        score = max(0, min(100, role_diversity + stability + impact + aim_balance + 10))
        notes = []
        if role_diversity >= 15: notes.append("Ajan tercihleri birbirini tekrar etmiyor; rol çatışması düşük.")
        else: notes.append("Ajan havuzunuz benzer; aynı role kilitlenmemek için flex seçimi gerekebilir.")
        if stability >= 18: notes.append("Tutarlılık seviyeleriniz birbirine yakın.")
        if abs(v1-v2) > 180: notes.append("Bireysel performans farkı belirgin; tempo kararlarında daha güçlü oyuncunun entry çağrılarını sade tutun.")
        e = panel("Duo Compatibility", f"**{ctx.author.display_name} + {member.display_name}**")
        e.add_field(name="Uyum skoru", value=f"**{score} / 100**", inline=True)
        e.add_field(name="Player DNA", value=f"{ctx.author.display_name}: `{style1}`\n{member.display_name}: `{style2}`", inline=True)
        e.add_field(name="Analiz", value="\n".join(f"• {x}" for x in notes), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="lfg", aliases=["takimbul", "takım bul"], description="Takım arkadaşı arama ilanı oluşturur.")
    async def lfg(self, ctx: commands.Context, role: str = "Flex", mic: bool = True, mode: str = "Competitive"):
        if not ctx.guild:
            return await ctx.send(embed=error("Sunucu gerekli", "LFG sadece sunucuda kullanılabilir."))
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt bulunamadı", "Önce `v!register` kullan."))
        snap = await store.latest_snapshot(ctx.author.id)
        rank = snap["rank"] if snap else "Bilinmiyor"
        await store.upsert_lfg(ctx.author.id, ctx.guild.id, rank=rank, role=role, region=user["region"], mic=mic, mode=mode)
        candidates = await store.find_lfg(ctx.guild.id, ctx.author.id, role=role, limit=5)
        e = panel("Looking For Group", f"**{ctx.author.display_name}** takım arkadaşı arıyor")
        e.add_field(name="Profil", value=f"Rank **{rank}**\nRol **{role}**\nMod **{mode}**\nMic **{'Var' if mic else 'Yok'}**", inline=True)
        if candidates:
            lines=[]
            for c in candidates:
                m=ctx.guild.get_member(int(c['discord_id']))
                if m: lines.append(f"• **{m.display_name}** — {c['rank']} — {c['role']}")
            if lines: e.add_field(name="Yakın ilanlar", value="\n".join(lines), inline=False)
        target = self.bot.get_channel(LFG_CHANNEL_ID) if LFG_CHANNEL_ID else None
        if target and target.id != ctx.channel.id:
            await target.send(embed=e, view=LFGJoinView(ctx.author.id))
            await ctx.send(embed=success("LFG yayınlandı", f"İlanın {target.mention} kanalına gönderildi."), ephemeral=True if ctx.interaction else False)
        else:
            await ctx.send(embed=e, view=LFGJoinView(ctx.author.id))

    @commands.hybrid_command(name="lfgclose", aliases=["lfgkapat"], description="Aktif LFG ilanını kapatır.")
    async def lfgclose(self, ctx: commands.Context):
        await store.close_lfg(ctx.author.id)
        await ctx.send(embed=success("LFG kapatıldı", "Aktif takım arama ilanın kapatıldı."))


    @commands.hybrid_command(name="friendcard", aliases=["arkadas","arkadaş"], description="İki oyuncu için ortak performans kartı oluşturur.")
    async def friendcard(self, ctx: commands.Context, member: discord.Member):
        u1,u2=await db.get_user(ctx.author.id),await db.get_user(member.id)
        if not u1 or not u2:
            return await ctx.send(embed=error("Kayıt eksik","İki oyuncu da kayıtlı olmalı."))
        (s1,v1),(s2,v2)=await asyncio.gather(fetch_summary(u1),fetch_summary(u2))
        avg_kd=round((s1['kd']+s2['kd'])/2,2); avg_wr=round((s1['winrate']+s2['winrate'])/2,1); avg_hs=round((s1['hs_rate']+s2['hs_rate'])/2,1)
        e=panel("Friend Card",f"**{ctx.author.display_name} + {member.display_name}** için ortak profil")
        e.add_field(name="Combined",value=f"K/D `{avg_kd}`\nHS `%{avg_hs}`\nWR `%{avg_wr}`",inline=True)
        e.add_field(name="V-Score",value=f"{ctx.author.display_name} `{v1}`\n{member.display_name} `{v2}`",inline=True)
        e.add_field(name="Ana ajanlar",value=f"{ctx.author.display_name}: **{s1['main_agent']}**\n{member.display_name}: **{s2['main_agent']}**",inline=False)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Community(bot))
