from __future__ import annotations

import re
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from config import VERIFICATION_CHANNEL_ID, VERIFIER_ROLE_ID
from database import db
from security import DISCORD_ALLOWED_MENTIONS, masked_puuid, sanitize_text
from theme import error, info, success, warning
from valorant_api import api

RIOT_ID_RE = re.compile(r"^(.{3,16})#(.{2,8})$")


def parse_riot_id(value: str) -> Optional[tuple[str, str]]:
    value = (value or "").strip()
    m = RIOT_ID_RE.match(value)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


async def verifier_allowed(cog: "Registration", member: discord.Member | discord.User) -> bool:
    if await cog.bot.is_owner(member):
        return True
    if isinstance(member, discord.Member):
        if VERIFIER_ROLE_ID and any(r.id == VERIFIER_ROLE_ID for r in member.roles):
            return True
        if member.guild_permissions.manage_guild:
            return True
    return False


class RegisterModal(discord.ui.Modal, title="V-Tracker • Riot Hesabı Bağla"):
    riot_id = discord.ui.TextInput(label="Riot ID", placeholder="OyuncuAdi#TAG", min_length=6, max_length=26)

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

    @discord.ui.button(label="Riot Hesabımı Bul", emoji="🔎", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(RegisterModal(self.cog))


class VerificationReviewView(discord.ui.View):
    def __init__(self, cog: "Registration", target_id: int, riot_name: str):
        super().__init__(timeout=86400)
        self.cog = cog
        self.target_id = target_id
        self.riot_name = riot_name

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed = await verifier_allowed(self.cog, interaction.user)
        if not allowed:
            await interaction.response.send_message("Bu panel yalnızca doğrulayıcı rol / yetkili içindir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Onayla", emoji="✅", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        ok, reason, user = await db.approve_pending_verification(self.target_id, interaction.user.id, "button approve")
        if not ok:
            return await interaction.response.send_message(embed=error("Onaylanamadı", f"Durum: `{reason}`"), ephemeral=True)
        await db.log_admin_action(interaction.guild_id or "", interaction.user.id, self.target_id, "VERIFY_APPROVE", self.riot_name)
        member = interaction.guild.get_member(self.target_id) if interaction.guild else None
        if member:
            try:
                await member.send(embed=success("V-Tracker hesabın doğrulandı", f"**{user['game_name']}#{user['tag_line']}** hesabın onaylandı."))
            except discord.HTTPException:
                pass
        await interaction.response.edit_message(embed=success("Hesap doğrulandı", f"<@{self.target_id}> → **{user['game_name']}#{user['tag_line']}**"), view=None)

    @discord.ui.button(label="Reddet", emoji="🛑", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        ok = await db.reject_pending_verification(self.target_id, interaction.user.id, "kanıt yetersiz / manuel reddedildi")
        if not ok:
            return await interaction.response.send_message(embed=error("Talep bulunamadı", "Bu kullanıcı için bekleyen doğrulama yok."), ephemeral=True)
        await db.log_admin_action(interaction.guild_id or "", interaction.user.id, self.target_id, "VERIFY_REJECT", self.riot_name)
        member = interaction.guild.get_member(self.target_id) if interaction.guild else None
        if member:
            try:
                await member.send(embed=warning("V-Tracker doğrulaması reddedildi", "Kanıt yetersiz veya doğrulama tamamlanamadı. Tekrar `v!register` ile başvurabilirsin."))
            except discord.HTTPException:
                pass
        await interaction.response.edit_message(embed=warning("Doğrulama reddedildi", f"<@{self.target_id}> başvurusu reddedildi."), view=None)


class ManualRequestView(discord.ui.View):
    def __init__(self, cog: "Registration", author_id: int, account: dict):
        super().__init__(timeout=180)
        self.cog = cog
        self.author_id = author_id
        self.account = account

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu işlem başka bir kullanıcıya ait.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Doğrulama Talebi Gönder", emoji="🛡️", style=discord.ButtonStyle.success)
    async def request(self, interaction: discord.Interaction, _: discord.ui.Button):
        a = self.account
        ok, reason = await db.create_pending_verification(
            discord_id=interaction.user.id,
            puuid=a["puuid"],
            game_name=a["name"],
            tag_line=a["tag"],
            region=a["region"],
            dc_name=str(interaction.user),
        )
        if not ok:
            texts = {
                "already_registered": "Zaten kayıtlısın.",
                "riot_locked": "Bu Riot hesabı başka bir Discord hesabına zaten bağlı.",
                "riot_pending": "Bu Riot hesabı için başka bir doğrulama talebi bekliyor.",
            }
            return await interaction.response.edit_message(embed=error("Talep oluşturulamadı", texts.get(reason, reason)), view=None)

        posted = False
        if VERIFICATION_CHANNEL_ID:
            channel = self.cog.bot.get_channel(VERIFICATION_CHANNEL_ID)
            if channel:
                e = warning("Yeni Riot hesap doğrulama talebi", f"Kullanıcı: <@{interaction.user.id}>\nRiot: **{a['name']}#{a['tag']}**")
                e.add_field(name="PUUID", value=f"`{masked_puuid(a['puuid'])}`", inline=False)
                e.add_field(name="İstenen kanıt", value="Riot istemcisinde hesabın açık olduğunu gösteren ekran görüntüsü / kısa ekran kaydı.", inline=False)
                e.add_field(name="Gizlilik", value="Şifre, 2FA kodu veya giriş bilgisi istenmez. Kanıtlar yalnızca doğrulama kanalında paylaşılmalıdır.", inline=False)
                await channel.send(embed=e, view=VerificationReviewView(self.cog, interaction.user.id, f"{a['name']}#{a['tag']}"), allowed_mentions=DISCORD_ALLOWED_MENTIONS)
                posted = True

        msg = "Talebin admin onayına gönderildi."
        if posted:
            msg += " Doğrulama kanalında kanıtını paylaş; yetkili butondan onaylayabilir veya reddedebilir."
        else:
            msg += " Sunucuda doğrulama kanalı ayarlı değil; yetkili `v!verify @kullanıcı` komutuyla onaylayabilir."
        await interaction.response.edit_message(embed=info("Doğrulama bekleniyor", msg), view=None)

    @discord.ui.button(label="İptal", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(embed=warning("İptal edildi", "Hiçbir hesap kaydı yapılmadı."), view=None)


class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="register", aliases=["kayit", "kayıt"], description="Riot hesabın için manuel sahiplik doğrulama talebi oluşturur.")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def register(self, ctx: commands.Context, *, riot_id: str = None):
        existing = await db.get_user(ctx.author.id)
        if existing:
            return await ctx.send(embed=info("Zaten kayıtlısın", f"Kayıtlı hesap: **{existing['game_name']}#{existing['tag_line']}**\nDoğrulama: **{existing['verification_level']}**\nRiot ID değiştiyse `v!sync` kullan."), ephemeral=True if ctx.interaction else False)
        pending = await db.get_pending_verification(ctx.author.id)
        if pending and pending.get("status") == "pending":
            return await ctx.send(embed=info("Doğrulama bekliyor", f"**{pending['game_name']}#{pending['tag_line']}** için admin onayı bekleniyor. `v!verification` ile durumu görebilirsin."), ephemeral=True if ctx.interaction else False)
        if riot_id:
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            return await self.begin_registration(ctx.interaction or ctx, riot_id, followup=bool(ctx.interaction))
        e = info("Riot hesabını bağla", "Önce Riot ID API üzerinden bulunur. Ardından **manuel sahiplik doğrulaması** yapılır. Admin onayı olmadan hesap Discord hesabına kilitlenmez.")
        e.add_field(name="1 • Riot ID", value="Örnek: `OyuncuAdi#TR1`", inline=False)
        e.add_field(name="2 • API kontrolü", value="Hesabın varlığı ve sabit PUUID kimliği alınır.", inline=False)
        e.add_field(name="3 • Sahiplik kanıtı", value="Doğrulama kanalına Riot istemcisinde hesabın açık olduğunu gösteren ekran görüntüsü/kısa kayıt gönderilir. **Şifre istenmez.**", inline=False)
        e.add_field(name="4 • Yetkili onayı", value="Onaydan sonra Discord ID ↔ Riot PUUID kalıcı kilidi oluşur.", inline=False)
        await ctx.send(embed=e, view=RegisterStartView(self, ctx.author.id), ephemeral=True if ctx.interaction else False)

    async def begin_registration(self, target, riot_id: str, *, followup: bool = False):
        parsed = parse_riot_id(riot_id)
        sender = target.followup.send if isinstance(target, discord.Interaction) and followup else target.send
        if not parsed:
            return await sender(embed=error("Riot ID formatı hatalı", "Doğru biçim: `OyuncuAdi#TAG`"), ephemeral=True if isinstance(target, discord.Interaction) else False)
        name, tag = parsed
        user = target.user if isinstance(target, discord.Interaction) else target.author
        if await db.get_user(user.id):
            return await sender(embed=error("Tek kayıt kuralı", "Bu Discord hesabı zaten bir Riot hesabına kilitli."), ephemeral=True if isinstance(target, discord.Interaction) else False)
        async with aiohttp.ClientSession() as session:
            payload = await api.account(session, name, tag)
        account = api.account_data(payload)
        if not account:
            return await sender(embed=error("Riot hesabı bulunamadı", "Riot ID'yi veya Henrik API erişimini kontrol et."), ephemeral=True if isinstance(target, discord.Interaction) else False)
        owner = await db.get_user_by_puuid(account["puuid"])
        if owner and str(owner["discord_id"]) != str(user.id):
            return await sender(embed=error("Hesap kullanımda", "Bu Riot hesabı başka bir Discord hesabına zaten bağlı."), ephemeral=True if isinstance(target, discord.Interaction) else False)
        e = info("Hesap bulundu", f"Riot profili: **{account['name']}#{account['tag']}**")
        e.add_field(name="Bölge", value=account["region"].upper(), inline=True)
        e.add_field(name="Seviye", value=str(account["level"]), inline=True)
        e.add_field(name="PUUID", value=f"`{masked_puuid(account['puuid'])}`", inline=True)
        e.add_field(name="Önemli", value="Bu ekran sadece hesabın varlığını doğrular. Sahiplik için **Doğrulama Talebi Gönder** ve admin kontrolü gerekir.", inline=False)
        card = account.get("card") or {}
        if isinstance(card, dict) and card.get("small"):
            e.set_thumbnail(url=card["small"])
        kwargs = {"embed": e, "view": ManualRequestView(self, user.id, account)}
        if isinstance(target, discord.Interaction):
            kwargs["ephemeral"] = True
        await sender(**kwargs)

    @commands.hybrid_command(name="verification", aliases=["dogrulama", "doğrulama"], description="Hesap doğrulama durumunu gösterir.")
    async def verification(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if user:
            return await ctx.send(embed=success("Doğrulandı", f"**{user['game_name']}#{user['tag_line']}**\nSeviye: `{user['verification_level']}`"), ephemeral=True if ctx.interaction else False)
        pending = await db.get_pending_verification(ctx.author.id)
        if not pending:
            return await ctx.send(embed=info("Doğrulama yok", "Önce `v!register` kullan."), ephemeral=True if ctx.interaction else False)
        status = pending.get("status", "pending")
        if status == "pending":
            text = "Admin incelemesi bekleniyor."
        elif status == "rejected":
            text = f"Reddedildi. Not: {pending.get('review_note') or 'belirtilmedi'}"
        else:
            text = status
        await ctx.send(embed=info("Doğrulama durumu", f"**{pending['game_name']}#{pending['tag_line']}**\nDurum: **{text}**"), ephemeral=True if ctx.interaction else False)

    @commands.command(name="verify")
    async def verify_member(self, ctx: commands.Context, member: discord.Member, *, note: str = "manuel kanıt kontrol edildi"):
        if not await verifier_allowed(self, ctx.author):
            return await ctx.send(embed=error("Yetki yok", "Bu komut yalnızca doğrulayıcı rol / yetkili içindir."))
        ok, reason, user = await db.approve_pending_verification(member.id, ctx.author.id, sanitize_text(note, 500))
        if not ok:
            return await ctx.send(embed=error("Onaylanamadı", f"Durum: `{reason}`"))
        await db.log_admin_action(ctx.guild.id if ctx.guild else "", ctx.author.id, member.id, "VERIFY_APPROVE", note)
        await ctx.send(embed=success("Hesap doğrulandı", f"{member.mention} → **{user['game_name']}#{user['tag_line']}**\nPUUID kalıcı olarak bu Discord hesabına kilitlendi."))
        try:
            await member.send(embed=success("V-Tracker hesabın doğrulandı", f"**{user['game_name']}#{user['tag_line']}** hesabın admin tarafından onaylandı."))
        except discord.HTTPException:
            pass

    @commands.command(name="rejectverify")
    async def reject_member(self, ctx: commands.Context, member: discord.Member, *, reason: str = "kanıt yetersiz"):
        if not await verifier_allowed(self, ctx.author):
            return await ctx.send(embed=error("Yetki yok", "Bu komut yalnızca doğrulayıcı rol / yetkili içindir."))
        reason = sanitize_text(reason, 500)
        ok = await db.reject_pending_verification(member.id, ctx.author.id, reason)
        if not ok:
            return await ctx.send(embed=error("Talep bulunamadı", "Bu kullanıcı için bekleyen doğrulama yok."))
        await db.log_admin_action(ctx.guild.id if ctx.guild else "", ctx.author.id, member.id, "VERIFY_REJECT", reason)
        await ctx.send(embed=warning("Doğrulama reddedildi", f"{member.mention}\nNeden: {reason}"))
        try:
            await member.send(embed=warning("V-Tracker doğrulaması reddedildi", f"Neden: {reason}\nTekrar `v!register` ile talep oluşturabilirsin."))
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="sync", aliases=["senkronize"], description="Doğrulanmış hesabın Riot ID değiştiyse aynı PUUID üzerinden günceller.")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def sync(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` ile doğrulama tamamla."), ephemeral=True if ctx.interaction else False)
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        async with aiohttp.ClientSession() as session:
            payload = await api.account_by_puuid(session, user["puuid"])
        account = api.account_data(payload)
        if not account:
            return await ctx.send(embed=error("Senkronize edilemedi", "Riot hesabı PUUID üzerinden bulunamadı."), ephemeral=True if ctx.interaction else False)
        await db.sync_identity(ctx.author.id, game_name=account["name"], tag_line=account["tag"], region=account["region"])
        await ctx.send(embed=success("Kimlik güncellendi", f"Güncel Riot ID: **{account['name']}#{account['tag']}**"), ephemeral=True if ctx.interaction else False)


async def setup(bot):
    await bot.add_cog(Registration(bot))
