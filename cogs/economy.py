from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

import discord
from discord.ext import commands

from database import db, utc_now
from theme import error, info, success, warning


def parse_iso(v):
    try: return datetime.fromisoformat(v) if v else None
    except Exception: return None


class Economy(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @commands.hybrid_command(name="balance", aliases=["bakiye", "bal", "para"], description="V-Coin bakiyeni gösterir.")
    async def balance(self, ctx, member: discord.Member=None):
        member=member or ctx.author; u=await db.get_user(member.id)
        if not u: return await ctx.send(embed=error("Kayıt yok", "Ekonomi sistemi için önce kayıt olmalısın."))
        await ctx.send(embed=info("V-Coin Cüzdanı", f"{member.mention}\n💰 **{u['v_coins']:,} V-Coin**"))

    async def _claim(self, ctx, kind, seconds, amount):
        u=await db.get_user(ctx.author.id)
        if not u: return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        last=parse_iso(await db.get_claim_time(ctx.author.id, kind)); now=datetime.now(timezone.utc)
        if last and now-last < timedelta(seconds=seconds):
            remain=timedelta(seconds=seconds)-(now-last); hrs=int(remain.total_seconds()//3600); mins=int((remain.total_seconds()%3600)//60)
            return await ctx.send(embed=warning("Ödül hazır değil", f"Yaklaşık **{hrs} sa {mins} dk** sonra tekrar deneyebilirsin."))
        await db.set_claim_time(ctx.author.id,kind,now.isoformat()); bal=await db.add_coins(ctx.author.id,amount,f"{kind}_claim")
        await ctx.send(embed=success("Ödül alındı", f"+**{amount:,} V-Coin**\nYeni bakiye: **{bal:,}**"))

    @commands.hybrid_command(name="daily", aliases=["gunluk", "günlük"], description="24 saatte bir V-Coin alırsın.")
    async def daily(self, ctx): await self._claim(ctx,"daily",86400,250)

    @commands.hybrid_command(name="weekly", aliases=["haftalik", "haftalık"], description="7 günde bir haftalık V-Coin alırsın.")
    async def weekly(self, ctx): await self._claim(ctx,"weekly",604800,1500)

    @commands.hybrid_command(name="transfer", aliases=["gonder", "gönder", "give"], description="Kayıtlı bir kullanıcıya V-Coin gönderir.")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        ok,reason=await db.transfer_coins(ctx.author.id,member.id,amount)
        messages={"invalid":"Miktar 0'dan büyük olmalı.","self":"Kendine transfer yapamazsın.","not_registered":"İki kullanıcı da kayıtlı olmalı.","insufficient":"Bakiyen yetersiz."}
        await ctx.send(embed=success("Transfer tamamlandı",f"{member.mention} kullanıcısına **{amount:,} V-Coin** gönderildi.") if ok else error("Transfer başarısız",messages.get(reason,"İşlem tamamlanamadı.")))

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top", "zenginler"], description="V-Coin sıralamasını gösterir.")
    async def leaderboard(self, ctx):
        users=await db.list_users(10); e=info("V-Coin Sıralaması", "Sunucudan bağımsız global kayıt tablosu")
        if not users: e.description="Henüz kayıtlı kullanıcı yok."
        else:
            e.add_field(name="Top 10", value="\n".join(f"`{i}.` **{u['dc_name']}** — {u['game_name']}#{u['tag_line']} • 💰 `{u['v_coins']:,}`" for i,u in enumerate(users,1)), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="shop", aliases=["magaza", "mağaza"], description="Profil özelleştirme mağazasını gösterir.")
    async def shop(self, ctx):
        e=info("V-Tracker Mağaza", "Profilini V-Coin ile özelleştir.")
        e.add_field(name="🎨 Renk • 2.500", value="`v!buy renk`", inline=False)
        e.add_field(name="✨ Emoji • 5.000", value="`v!buy emoji`", inline=False)
        e.add_field(name="🖼️ Banner • 10.000", value="`v!buy banner`", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="buy", aliases=["satinal", "satınal"], description="Profil özelliğinin kilidini açar.")
    async def buy(self, ctx, item: str):
        prices={"renk":2500,"emoji":5000,"banner":10000}; item=item.lower().strip(); u=await db.get_user(ctx.author.id)
        if not u: return await ctx.send(embed=error("Kayıt yok","Önce kayıt ol."))
        if item not in prices: return await ctx.send(embed=error("Ürün yok","Seçenekler: `renk`, `emoji`, `banner`"))
        import json
        unlocked=set(json.loads(u.get('unlocked_json') or '[]'))
        if item in unlocked: return await ctx.send(embed=info("Zaten açık",f"**{item}** zaten hesabında açık."))
        if u['v_coins']<prices[item]: return await ctx.send(embed=error("Bakiye yetersiz",f"Gerekli: **{prices[item]:,} V-Coin**"))
        # Atomic enough for single process: subtract then update unlocked directly.
        await db.add_coins(ctx.author.id,-prices[item],f"shop:{item}")
        unlocked.add(item)
        async with db._lock:
            with db._connect() as conn:
                conn.execute("UPDATE users SET unlocked_json=?, updated_at=? WHERE discord_id=?",(json.dumps(sorted(unlocked)),utc_now(),str(ctx.author.id)))
        await ctx.send(embed=success("Satın alındı",f"**{item}** özelliği açıldı."))

    @commands.hybrid_command(name="customize", aliases=["profil_ayarla"], description="Satın alınan profil görünümünü ayarlar.")
    async def customize(self, ctx, kind: str, *, value: str):
        import json
        u=await db.get_user(ctx.author.id)
        if not u: return await ctx.send(embed=error("Kayıt yok","Önce kayıt ol."))
        kind=kind.lower().strip(); unlocked=set(json.loads(u.get('unlocked_json') or '[]'))
        if kind not in unlocked: return await ctx.send(embed=error("Kilitli",f"Önce `v!buy {kind}` kullan."))
        if kind=="renk":
            v=value.strip().replace('#','').replace('0x','')
            if not re.fullmatch(r'[0-9a-fA-F]{6}',v): return await ctx.send(embed=error("Renk hatalı","Örnek: `v!customize renk FF4655`"))
            await db.set_profile(ctx.author.id,color=int(v,16))
        elif kind=="emoji": await db.set_profile(ctx.author.id,emoji=value.strip())
        elif kind=="banner":
            if not re.match(r'^https://',value.strip(),re.I): return await ctx.send(embed=error("URL hatalı","Banner HTTPS bağlantısı olmalı."))
            await db.set_profile(ctx.author.id,banner=value.strip())
        else: return await ctx.send(embed=error("Tür hatalı","`renk`, `emoji` veya `banner` kullan."))
        await ctx.send(embed=success("Profil güncellendi",f"**{kind}** ayarı kaydedildi."))

    @commands.hybrid_command(name="challenges", aliases=["gorevler", "görevler"], description="Günlük ve haftalık görev önerilerini gösterir.")
    async def challenges(self,ctx):
        e=info("Görev Merkezi","V-Coin kazanmak için basit görevler")
        e.add_field(name="Günlük",value="• `v!daily` ödülünü al\n• `v!stats` ile analiz yap\n• `v!coach` önerisini görüntüle",inline=False)
        e.add_field(name="Haftalık",value="• `v!weekly` ödülünü al\n• Bir arkadaşınla `v!compare @üye` yap\n• Profilini özelleştir",inline=False)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Economy(bot))
