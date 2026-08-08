from __future__ import annotations

from datetime import datetime, timezone, timedelta

import aiohttp
from discord.ext import commands

from cogs.stats import analyze, compute_vscore, form_label, tilt_score, rank_from_mmr
from database import db
from response_variants import unique_variant
from theme import error, panel
from v4_store import store
from valorant_api import api


class Reports(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def _live(self, discord_id: int):
        user = await db.get_user(discord_id)
        if not user: return None
        async with aiohttp.ClientSession() as session:
            mmr = await api.mmr(session, user['region'], user['puuid'])
            payload = await api.matches(session, user['region'], user['puuid'], 15)
        s = analyze((payload or {}).get('data', []), user['puuid'])
        rank, rr = rank_from_mmr(mmr)
        return user, s, rank, rr

    @commands.hybrid_command(name='dailyreport', aliases=['gunlukrapor','günlükrapor'], description='Güncel oyuncu gün raporunu oluşturur.')
    async def dailyreport(self, ctx):
        data = await self._live(ctx.author.id)
        if not data: return await ctx.send(embed=error('Kayıt bulunamadı','Önce `v!register` kullan.'))
        user,s,rank,rr=data
        if not s['matches']: return await ctx.send(embed=error('Rapor oluşturulamadı','Maç verisi yok.'))
        v=compute_vscore(s,rank); recent=s['per_match'][:6]; wins=sum(1 for x in recent if x['won']); losses=len(recent)-wins
        e=panel('Daily Player Report',f"**{user['game_name']}#{user['tag_line']}** için güncel performans özeti")
        e.add_field(name='Rank',value=f'**{rank}** • `{rr} RR`',inline=True)
        e.add_field(name='V-Score',value=f'`{v}/1000`',inline=True)
        e.add_field(name='Form',value=f'{form_label(s)} • Tilt `{tilt_score(s)}/100`',inline=True)
        e.add_field(name='Son maç bloğu',value=f'`{wins}W / {losses}L` • K/D `{s["kd"]}` • HS `%{s["hs_rate"]}` • ADR `{s["adr"]}`',inline=False)
        if recent:
            e.add_field(name='Son maçlar',value='\n'.join(f"• **{x['map']}** — {'W' if x['won'] else 'L'} — {x['kills']}/{x['deaths']}/{x['assists']} — {x['agent']}" for x in recent),inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name='weeklyreport', aliases=['haftalikrapor','haftalıkrapor'], description='Son 7 günlük kayıtlı performans trendini gösterir.')
    async def weeklyreport(self, ctx):
        rows=await store.snapshots(ctx.author.id,100)
        cutoff=datetime.now(timezone.utc)-timedelta(days=7)
        rows=[r for r in rows if datetime.fromisoformat(r['captured_at'])>=cutoff]
        if len(rows)<2: return await ctx.send(embed=error('Haftalık veri yetersiz','Otomatik takip birkaç snapshot topladıktan sonra haftalık değişim hesaplanabilir.'))
        newest,oldest=rows[0],rows[-1]
        e=panel('Weekly Performance Report',f'Son 7 günde kaydedilen **{len(rows)}** snapshot üzerinden')
        e.add_field(name='Rank değişimi',value=f"{oldest['rank']} `{oldest['rr']} RR` → **{newest['rank']}** `{newest['rr']} RR`",inline=False)
        e.add_field(name='V-Score',value=f"`{oldest['vscore']}` → `{newest['vscore']}` ({int(newest['vscore'])-int(oldest['vscore']):+d})",inline=True)
        e.add_field(name='K/D',value=f"`{oldest['kd']}` → `{newest['kd']}` ({float(newest['kd'])-float(oldest['kd']):+.2f})",inline=True)
        e.add_field(name='HS',value=f"`%{oldest['hs_rate']}` → `%{newest['hs_rate']}` ({float(newest['hs_rate'])-float(oldest['hs_rate']):+.1f})",inline=True)
        e.add_field(name='ADR',value=f"`{oldest['adr']}` → `{newest['adr']}` ({float(newest['adr'])-float(oldest['adr']):+.1f})",inline=True)
        e.add_field(name='WR',value=f"`%{oldest['winrate']}` → `%{newest['winrate']}` ({float(newest['winrate'])-float(oldest['winrate']):+.1f})",inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name='weeklytop', aliases=['haftaliktop','haftalıktop'], description='Sunucudaki haftalık gelişim liderlerini gösterir.')
    async def weeklytop(self, ctx):
        if not ctx.guild: return await ctx.send(embed=error('Sunucu gerekli','Bu komut sunucuda kullanılmalı.'))
        rows=await store.weekly_leaderboard(7,25); lines=[]
        for r in rows:
            member=ctx.guild.get_member(int(r['discord_id']))
            if member: lines.append(f"`{len(lines)+1}.` **{member.display_name}** — V-Score `{r['vscore_delta']:+d}` • şimdi `{r['vscore']}`")
            if len(lines)>=10: break
        e=panel('Weekly Growth Leaderboard','Son 7 günlük V-Score gelişimine göre')
        e.add_field(name='Top 10',value='\n'.join(lines) or 'Bu sunucuda yeterli haftalık snapshot verisi yok.',inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name='streak', aliases=['seri','formseri'], description='Son maç kazanma/kaybetme serisini gösterir.')
    async def streak(self, ctx):
        data=await self._live(ctx.author.id)
        if not data: return await ctx.send(embed=error('Kayıt bulunamadı','Önce kayıt ol.'))
        user,s,rank,rr=data; recent=s['per_match']; first=recent[0]['won'] if recent else False; count=0
        for m in recent:
            if m['won']==first: count+=1
            else: break
        if not first and count>=3:
            options=[
                'Bu seride hedef RR kurtarmak değil karar kalitesini geri kazanmak. Bir sonraki queue öncesi kısa ara ver ve ilk ölüm sayısını tek metrik olarak takip et.',
                'Kayıp serisi uzamış. Sonraki maçta mekanik hedef koyma; sadece gereksiz re-peek ve yalnız düello sayısını azaltmaya çalış.',
                'Seri baskısı karar hızını bozabilir. Queue temposunu düşür, warm-up sonrası yalnız bir ranked oynayıp sonucu yeniden değerlendir.',
                'Bu noktada daha fazla maç her zaman daha fazla veri demek değil. Kısa reset sonrası ilk 5 roundda utility ve trade disiplinine odaklan.',
            ]
            advice=await unique_variant(ctx.author.id,'streak:loss',options,salt=str(count))
        else:
            options=[
                'Form dengeli görünüyor. Kazanma serisinde bile ilk avantaj sonrası gereksiz ikinci düelloyu azaltmak istikrarı korur.',
                'Mevcut seri normal aralıkta. Sonuçtan çok aynı iyi kararları tekrar edip etmediğini takip et.',
                'Tempo şu an kontrol altında. Bir sonraki maçta tek hedef seçmek, performansı seriden bağımsız tutar.',
                'Form stabil; bu aşamada antrenman hacmini artırmak yerine iyi çalışan rutinleri değiştirmemek daha değerli olabilir.',
            ]
            advice=await unique_variant(ctx.author.id,'streak:normal',options,salt=str(count))
        e=panel('Current Streak',f"**{user['game_name']}#{user['tag_line']}**")
        e.add_field(name='Seri',value=f"**{count} {'Win' if first else 'Loss'}**",inline=True)
        e.add_field(name='Tilt riski',value=f"`{tilt_score(s)}/100`",inline=True)
        e.add_field(name='Önerilen yaklaşım',value=advice,inline=False)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Reports(bot))
