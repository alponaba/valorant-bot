from __future__ import annotations

import re
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from config import VERIFICATION_CHANNEL_ID
from database import db
from theme import error, info, success, warning
from valorant_api import api

RIOT_ID_RE = re.compile(r"^(.{3,16})#(.{2,8})$")


def parse_riot_id(value: str) -> Optional[tuple[str, str]]:
    value = (value or "").strip()
    m = RIOT_ID_RE.match(value)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


class RegisterModal(discord.ui.Modal, title="V-Tracker • Riot Hesabı Bağla"):
    riot_id = discord.ui.TextInput(
        label="Riot ID",
        placeholder="OyuncuAdi#TAG",
        min_length=6,
        max_length=26,
    )

    def __init__(self, cog: "Registration"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.begin_registration(interaction, str(self.riot_id.value), followup=True)


class RegisterStartView(discord.ui.View):
    def __init__(self, cog: "Registration", author_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu kayıt paneli sana ait değil.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Riot Hesabımı Bağla", emoji="🔗", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(RegisterModal(self.cog))


class RegistrationConfirmView(discord.ui.View):
    def __init__(self, cog: "Registration", author_id: int, account: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id
        self.account = account
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu doğrulama başka bir kullanıcıya ait.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Evet, bu hesap benim", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return await interaction.response.send_message("Bu işlem zaten tamamlandı.", ephemeral=True)
        self.finished = True
        a = self.account
        ok, reason, existing = await db.register_once(
            discord_id=interaction.user.id,
            puuid=a["puuid"],
            game_name=a["name"],
            tag_line=a["tag"],
            region=a["region"],
            dc_name=str(interaction.user),
        )
        if ok:
            e = success("Hesap kilitlendi", f"**{a['name']}#{a['tag']}** hesabı Discord hesabına bağlandı.")
            e.add_field(name="Tek kayıt kuralı", value="Bu Discord hesabı artık farklı bir Riot hesabıyla tekrar kayıt olamaz.", inline=False)
            e.add_field(name="Riot ID değişirse", value="Yeni hesaba kayıt olma. `v!sync` kullan; sistem aynı PUUID üzerinden yeni Riot adını günceller.", inline=False)
            e.add_field(name="Doğrulama seviyesi", value="Riot API profil doğrulaması + benzersiz PUUID kilidi", inline=False)
            await interaction.response.edit_message(embed=e, view=None)
            return

        self.finished = False
        if reason == "discord_locked":
            name = f"{existing['game_name']}#{existing['tag_line']}" if existing else "mevcut hesap"
            e = error("Kayıt kilidi aktif", f"Bu Discord hesabı daha önce **{name}** hesabına kilitlenmiş. Farklı bir Riot hesabına geçiş engellendi.")
        elif reason == "riot_locked":
            e = error("Riot hesabı kullanımda", "Bu Riot hesabının PUUID'si başka bir Discord hesabına zaten kilitli.")
        else:
            e = info("Zaten kayıtlısın", "Bu Riot hesabı zaten Discord hesabına bağlı.")
        await interaction.response.edit_message(embed=e, view=None)

    @discord.ui.button(label="İptal", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.finished = True
        await interaction.response.edit_message(embed=warning("Kayıt iptal edildi", "Hiçbir kayıt değişikliği yapılmadı."), view=None)


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="register", aliases=["kayit", "kayıt"], description="Riot hesabını bir kez Discord hesabına kilitler.")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def register(self, ctx: commands.Context, *, riot_id: str = None):
        existing = await db.get_user(ctx.author.id)
        if existing:
            return await ctx.send(embed=info(
                "Zaten kayıtlısın",
                f"Kayıtlı hesap: **{existing['game_name']}#{existing['tag_line']}**\n\n"
                "Tek-kayıt sistemi nedeniyle farklı hesaba tekrar kayıt açılamaz. Riot ID'ni değiştirdiysen `v!sync` kullan."
            ), ephemeral=True if ctx.interaction else False)

        if riot_id:
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            return await self.begin_registration(ctx.interaction or ctx, riot_id, followup=bool(ctx.interaction))

        e = info(
            "Riot hesabını bağla",
            "Her Discord hesabı **yalnızca bir Riot hesabına** kalıcı olarak bağlanabilir.\n\n"
            "Kayıt sırasında Riot ID API üzerinden kontrol edilir, hesabın sabit **PUUID** kimliği alınır ve kayıt bu PUUID'ye kilitlenir."
        )
        e.add_field(name="1 • Riot ID", value="Örnek: `OyuncuAdi#TR1`", inline=False)
        e.add_field(name="2 • Profil kontrolü", value="Bot Riot profilini bulur ve kartını/hesap bilgilerini gösterir.", inline=False)
        e.add_field(name="3 • Onay", value="Hesabı onayladığında farklı Riot hesabına yeniden kayıt engellenir.", inline=False)
        e.add_field(name="Not", value="Bu akış Riot profilinin varlığını doğrular. Resmî RSO sahiplik doğrulaması değildir; şifre istemez ve saklamaz.", inline=False)
        await ctx.send(embed=e, view=RegisterStartView(self, ctx.author.id), ephemeral=True if ctx.interaction else False)

    async def begin_registration(self, target, riot_id: str, *, followup: bool = False):
        parsed = parse_riot_id(riot_id)
        sender = target.followup.send if isinstance(target, discord.Interaction) and followup else target.send
        if not parsed:
            return await sender(embed=error("Riot ID formatı hatalı", "Doğru biçim: `OyuncuAdi#TAG`"), ephemeral=True if isinstance(target, discord.Interaction) else False)
        name, tag = parsed
        user = target.user if isinstance(target, discord.Interaction) else target.author
        existing = await db.get_user(user.id)
        if existing:
            return await sender(embed=error("Tek kayıt kuralı", f"Zaten **{existing['game_name']}#{existing['tag_line']}** hesabına kilitlisin."), ephemeral=True if isinstance(target, discord.Interaction) else False)

        async with aiohttp.ClientSession() as session:
            payload = await api.account(session, name, tag)
        account = api.account_data(payload)
        if not account:
            return await sender(embed=error("Riot hesabı bulunamadı", "Riot ID'yi kontrol et veya Henrik API'nin erişilebilir olduğundan emin ol."), ephemeral=True if isinstance(target, discord.Interaction) else False)

        owner = await db.get_user_by_puuid(account["puuid"])
        if owner and str(owner["discord_id"]) != str(user.id):
            return await sender(embed=error("Bu hesap daha önce kaydedilmiş", "Aynı Riot hesabı iki farklı Discord hesabına bağlanamaz."), ephemeral=True if isinstance(target, discord.Interaction) else False)

        e = info("Hesabı doğrula", f"Bulunan Riot hesabı: **{account['name']}#{account['tag']}**")
        e.add_field(name="Bölge", value=account["region"].upper(), inline=True)
        e.add_field(name="Seviye", value=str(account["level"]), inline=True)
        e.add_field(name="Kimlik", value=f"`{account['puuid'][:8]}…{account['puuid'][-6:]}`", inline=True)
        if account.get("title"):
            e.add_field(name="Unvan", value=account["title"], inline=False)
        card = account.get("card") or {}
        if isinstance(card, dict) and card.get("small"):
            e.set_thumbnail(url=card["small"])
        e.add_field(name="Kalıcı kilit", value="Onaydan sonra bu Discord hesabına farklı Riot hesabı bağlanamaz. Bu kural yanlışlıkla hesap değiştirmeyi ve sahte kayıtları önler.", inline=False)
        kwargs = {"embed": e, "view": RegistrationConfirmView(self, user.id, account)}
        if isinstance(target, discord.Interaction):
            kwargs["ephemeral"] = True
        await sender(**kwargs)

    @commands.hybrid_command(name="sync", aliases=["senkronize"], description="Riot ID değiştiyse aynı PUUID üzerinden isim/tag bilgisini günceller.")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def sync(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` ile kayıt ol."), ephemeral=True if ctx.interaction else False)
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        async with aiohttp.ClientSession() as session:
            payload = await api.account_by_puuid(session, user["puuid"])
        account = api.account_data(payload)
        if not account:
            return await ctx.send(embed=error("Senkronizasyon başarısız", "Riot API şu anda PUUID üzerinden hesap bilgisini döndürmedi."), ephemeral=True if ctx.interaction else False)
        old = f"{user['game_name']}#{user['tag_line']}"
        new = f"{account['name']}#{account['tag']}"
        await db.sync_identity(ctx.author.id, game_name=account["name"], tag_line=account["tag"], region=account["region"])
        await ctx.send(embed=success("Profil güncellendi", f"`{old}` → **{new}**\n\nHesap aynı PUUID'ye kilitli kalmaya devam ediyor."), ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="verification", aliases=["dogrulama", "verify"], description="Kayıt ve doğrulama durumunu gösterir.")
    async def verification(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."), ephemeral=True if ctx.interaction else False)
        level = user["verification_level"]
        text = "✅ Riot API profil doğrulaması + PUUID kilidi" if level == "api_profile" else "✅ Manuel sahiplik incelemesi tamamlandı"
        e = info("Doğrulama durumu", f"**{user['game_name']}#{user['tag_line']}**\n{text}")
        e.add_field(name="Güvenlik", value="Bot Riot şifreni istemez veya saklamaz.", inline=False)
        if level == "api_profile":
            e.add_field(name="Sahiplik notu", value="API doğrulaması hesabın varlığını doğrular; resmî Riot RSO sahiplik doğrulaması değildir.", inline=False)
        await ctx.send(embed=e, ephemeral=True if ctx.interaction else False)

    @commands.hybrid_command(name="registration_reset", description="[Bot sahibi] Bir kullanıcının kalıcı kayıt kilidini sıfırlar.")
    @commands.is_owner()
    async def registration_reset(self, ctx: commands.Context, member: discord.Member, *, reason: str = "owner reset"):
        ok = await db.owner_reset_registration(member.id, reason)
        await ctx.send(embed=success("Kayıt sıfırlandı", f"{member.mention} yeniden kayıt olabilir.") if ok else error("Kayıt bulunamadı", "Bu kullanıcı için kayıt yok."), ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
