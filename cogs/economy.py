from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re

import discord
from discord.ext import commands

from database import db
from security import sanitize_text, trusted_banner_url
from theme import error, info, panel, success, warning


def parse_iso(v):
    try:
        return datetime.fromisoformat(v) if v else None
    except Exception:
        return None


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bakiye", "bal", "para"], description="V-Coin bakiyeni gösterir.")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        u = await db.get_user(member.id)
        if not u:
            return await ctx.send(embed=error("Kayıt yok", "Ekonomi sistemi için önce kayıt olmalısın."))
        unlocked = json.loads(u.get("unlocked_json") or "[]")
        e = panel("💰 V-Coin Cüzdanı", f"**{member.display_name}** için ekonomi özeti")
        e.add_field(name="Bakiye", value=f"**{u['v_coins']:,} V-Coin**", inline=True)
        e.add_field(name="Açık kozmetik", value=str(len(unlocked)), inline=True)
        e.add_field(name="Aktif renk", value=f"`#{int(u['profile_color'] or 0):06X}`", inline=True)
        await ctx.send(embed=e)

    async def _claim(self, ctx, kind, seconds, amount):
        u = await db.get_user(ctx.author.id)
        if not u:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        last = parse_iso(await db.get_claim_time(ctx.author.id, kind))
        now = datetime.now(timezone.utc)
        if last and now - last < timedelta(seconds=seconds):
            remain = timedelta(seconds=seconds) - (now - last)
            hrs = int(remain.total_seconds() // 3600)
            mins = int((remain.total_seconds() % 3600) // 60)
            return await ctx.send(embed=warning("Ödül hazır değil", f"Yaklaşık **{hrs} sa {mins} dk** sonra tekrar deneyebilirsin."))
        ok, _, bal = await db.claim_reward_atomic(ctx.author.id, kind, amount, now.isoformat())
        if not ok:
            return await ctx.send(embed=error("İşlem başarısız", "Kullanıcı kaydı bulunamadı."))
        await ctx.send(embed=success("Ödül alındı", f"+**{amount:,} V-Coin**\nYeni bakiye: **{bal:,}**"))

    @commands.hybrid_command(name="daily", aliases=["gunluk", "günlük"], description="24 saatte bir V-Coin alırsın.")
    async def daily(self, ctx):
        await self._claim(ctx, "daily", 86400, 250)

    @commands.hybrid_command(name="weekly", aliases=["haftalik", "haftalık"], description="7 günde bir haftalık V-Coin alırsın.")
    async def weekly(self, ctx):
        await self._claim(ctx, "weekly", 604800, 1500)

    @commands.hybrid_command(name="transfer", aliases=["gonder", "gönder", "give"], description="Kayıtlı bir kullanıcıya V-Coin gönderir.")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        ok, reason = await db.transfer_coins(ctx.author.id, member.id, amount)
        messages = {
            "invalid": "Miktar 0'dan büyük olmalı.",
            "self": "Kendine transfer yapamazsın.",
            "not_registered": "İki kullanıcı da kayıtlı olmalı.",
            "insufficient": "Bakiyen yetersiz.",
        }
        await ctx.send(embed=success("Transfer tamamlandı", f"{member.mention} kullanıcısına **{amount:,} V-Coin** gönderildi.") if ok else error("Transfer başarısız", messages.get(reason, "İşlem tamamlanamadı.")))

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top", "zenginler"], description="V-Coin sıralamasını gösterir.")
    async def leaderboard(self, ctx):
        users = await db.list_users(10)
        e = panel("🏦 V-Coin Leaderboard", "Sunucudan bağımsız global kayıt tablosu")
        if not users:
            e.description = "Henüz kayıtlı kullanıcı yok."
        else:
            lines = []
            for i, u in enumerate(users, 1):
                lines.append(f"`{i}.` **{u['dc_name'] or u['game_name']}** — {u['game_name']}#{u['tag_line']} • 💰 `{u['v_coins']:,}`")
            e.add_field(name="Top 10", value="\n".join(lines), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="shop", aliases=["magaza", "mağaza"], description="Profil özelleştirme mağazasını gösterir.")
    async def shop(self, ctx):
        e = panel("🛍️ V-Tracker Mağaza", "Açık sarı + turkuaz tasarım çizgisine uygun profil kozmetikleri")
        e.add_field(name="🎨 Renk • 2.500", value="Profil kartı ana rengini değiştirir.\n`v!buy renk`", inline=False)
        e.add_field(name="✨ Emoji • 5.000", value="Profil başlığına özel emoji ekler.\n`v!buy emoji`", inline=False)
        e.add_field(name="🖼️ Banner • 10.000", value="Güvenilen HTTPS kaynaktan banner kullanır.\n`v!buy banner`", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="buy", aliases=["satinal", "satınal"], description="Profil özelliğinin kilidini açar.")
    async def buy(self, ctx, item: str):
        prices = {"renk": 2500, "emoji": 5000, "banner": 10000}
        item = item.lower().strip()
        if item not in prices:
            return await ctx.send(embed=error("Ürün yok", "Seçenekler: `renk`, `emoji`, `banner`"))
        ok, reason, balance = await db.purchase_item(ctx.author.id, item, prices[item])
        if not ok:
            messages = {
                "not_registered": "Önce kayıt ol.",
                "already": f"**{item}** zaten hesabında açık.",
                "insufficient": f"Gerekli: **{prices[item]:,} V-Coin** • Mevcut: **{balance or 0:,}**",
            }
            return await ctx.send(embed=error("Satın alma başarısız", messages.get(reason, "İşlem tamamlanamadı.")))
        await ctx.send(embed=success("Satın alındı", f"**{item}** özelliği açıldı. Yeni bakiye: **{balance:,} V-Coin**"))

    @commands.hybrid_command(name="customize", aliases=["profil_ayarla"], description="Satın alınan profil görünümünü ayarlar.")
    async def customize(self, ctx, kind: str, *, value: str):
        u = await db.get_user(ctx.author.id)
        if not u:
            return await ctx.send(embed=error("Kayıt yok", "Önce kayıt ol."))
        kind = kind.lower().strip()
        unlocked = set(json.loads(u.get("unlocked_json") or "[]"))
        if kind not in unlocked:
            return await ctx.send(embed=error("Kilitli", f"Önce `v!buy {kind}` kullan."))
        if kind == "renk":
            v = value.strip().replace("#", "").replace("0x", "")
            if not re.fullmatch(r"[0-9a-fA-F]{6}", v):
                return await ctx.send(embed=error("Renk hatalı", "Örnek: `v!customize renk 2FD6C4`"))
            await db.set_profile(ctx.author.id, color=int(v, 16))
        elif kind == "emoji":
            await db.set_profile(ctx.author.id, emoji=sanitize_text(value, 16))
        elif kind == "banner":
            ok, result = trusted_banner_url(value)
            if not ok:
                return await ctx.send(embed=error("Banner URL reddedildi", result))
            await db.set_profile(ctx.author.id, banner=result)
        else:
            return await ctx.send(embed=error("Tür hatalı", "`renk`, `emoji` veya `banner` kullan."))
        await ctx.send(embed=success("Profil güncellendi", f"**{kind}** ayarı kaydedildi."))

    @commands.hybrid_command(name="challenges", aliases=["gorevler", "görevler"], description="Günlük ve haftalık görev önerilerini gösterir.")
    async def challenges(self, ctx):
        u = await db.get_user(ctx.author.id)
        if not u:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        e = panel("🎯 Mission Board", "V-Coin kazanmak ve profili büyütmek için görevler")
        e.add_field(name="Günlük görevler", value="✅ `v!daily` ödülünü al\n⬜ `v!stats` ile paneli görüntüle\n⬜ `v!coach` ile koç analizini aç\n⬜ Bir kullanıcıyla `v!compare @üye` yap", inline=False)
        e.add_field(name="Haftalık görevler", value="⬜ `v!weekly` ödülünü al\n⬜ `v!shop` mağazasını incele\n⬜ Profil kozmetiği satın al\n⬜ Sunucuda bir öneri gönder", inline=False)
        e.add_field(name="Pro ipucu", value=f"Mevcut bakiye: **{u['v_coins']:,} V-Coin**\nİlk hedef için öneri: **Renk** özelliğini aç.", inline=False)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Economy(bot))
