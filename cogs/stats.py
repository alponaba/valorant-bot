from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands

from database import db
from theme import error, info
from valorant_api import api


def _player_from_match(match: dict, puuid: str) -> Optional[dict]:
    players = match.get("players") or {}
    candidates = []
    if isinstance(players, dict):
        for key in ("all_players", "red", "blue"):
            if isinstance(players.get(key), list):
                candidates.extend(players[key])
    elif isinstance(players, list):
        candidates = players
    for p in candidates:
        if isinstance(p, dict) and (p.get("puuid") == puuid or p.get("subject") == puuid):
            return p
    return None


def analyze(matches: List[dict], puuid: str) -> Dict[str, Any]:
    kills = deaths = assists = hs = body = leg = 0
    score_sum = damage = rounds = wins = losses = 0
    agents = Counter(); maps = defaultdict(lambda: {"played": 0, "won": 0}); weapons = Counter()
    valid = 0

    for m in matches:
        if not isinstance(m, dict):
            continue
        p = _player_from_match(m, puuid)
        if not p:
            continue
        valid += 1
        st = p.get("stats") or p
        kills += int(st.get("kills") or 0); deaths += int(st.get("deaths") or 0); assists += int(st.get("assists") or 0)
        score_sum += int(st.get("score") or 0)
        hs += int(st.get("headshots") or 0); body += int(st.get("bodyshots") or 0); leg += int(st.get("legshots") or 0)
        char = p.get("character") or p.get("agent") or "Bilinmiyor"; agents[char] += 1
        meta = m.get("metadata") or {}
        map_name = meta.get("map") or meta.get("map_name") or "Bilinmiyor"; maps[map_name]["played"] += 1
        team = str(p.get("team") or "").lower()
        teams = m.get("teams") or {}
        won = False
        if isinstance(teams, dict):
            t = teams.get(team) or teams.get(team.capitalize()) or {}
            won = bool(t.get("has_won") or t.get("won")) if isinstance(t, dict) else False
        if won: wins += 1; maps[map_name]["won"] += 1
        else: losses += 1
        rounds += int(meta.get("rounds_played") or m.get("rounds_played") or 0)
        dmg = p.get("damage_made") or p.get("damage") or 0
        if isinstance(dmg, dict): dmg = dmg.get("made") or dmg.get("damage_made") or 0
        damage += int(dmg or 0)
        for k in m.get("kills", []) if isinstance(m.get("kills"), list) else []:
            if isinstance(k, dict) and (k.get("killer_puuid") == puuid or k.get("killer") == puuid):
                w = k.get("damage_weapon_name") or k.get("weapon") or ""; weapons[w] += 1 if w else 0

    rounds = max(rounds, 1)
    shots = hs + body + leg
    kd = round(kills / deaths, 2) if deaths else float(kills)
    return {
        "matches": valid, "kills": kills, "deaths": deaths, "assists": assists, "kd": kd,
        "hs": hs, "body": body, "leg": leg, "hs_rate": round(hs / shots * 100, 1) if shots else 0,
        "adr": round(damage / rounds, 1), "acs": round(score_sum / rounds, 1), "damage": damage,
        "rounds": rounds, "wins": wins, "losses": losses,
        "winrate": round(wins / valid * 100, 1) if valid else 0,
        "main_agent": agents.most_common(1)[0][0] if agents else "Bilinmiyor",
        "agents": agents.most_common(5), "maps": sorted(maps.items(), key=lambda x: x[1]["played"], reverse=True)[:5],
        "weapons": weapons.most_common(5),
    }


class Pages(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed], author_id: int):
        super().__init__(timeout=120)
        self.embeds = embeds; self.index = 0; self.author_id = author_id; self._update()
    def _update(self):
        self.prev.disabled = self.index == 0; self.next.disabled = self.index >= len(self.embeds)-1
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu panel sana ait değil.", ephemeral=True); return False
        return True
    @discord.ui.button(label="Geri", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = max(0, self.index-1); self._update(); await interaction.response.edit_message(embed=self.embeds[self.index], view=self)
    @discord.ui.button(label="İleri", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = min(len(self.embeds)-1, self.index+1); self._update(); await interaction.response.edit_message(embed=self.embeds[self.index], view=self)


class Stats(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def _fetch(self, user: dict):
        async with aiohttp.ClientSession() as session:
            account_p, mmr_p, matches_p = await __import__('asyncio').gather(
                api.account_by_puuid(session, user['puuid']),
                api.mmr(session, user['region'], user['puuid']),
                api.matches(session, user['region'], user['puuid'], 15),
            )
        return api.account_data(account_p), mmr_p, (matches_p or {}).get('data', [])

    @commands.hybrid_command(name="stats", aliases=["profil", "istatistik"], description="Kayıtlı oyuncunun Valorant performans analizini gösterir.")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def stats(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = await db.get_user(member.id)
        if not user: return await ctx.send(embed=error("Kayıt yok", f"{member.display_name} için kayıt bulunamadı. `v!register` kullan."))
        if ctx.interaction: await ctx.defer()
        account, mmr, matches = await self._fetch(user)
        if not matches: return await ctx.send(embed=error("Maç verisi alınamadı", "API yanıt vermedi veya son maç verisi yok."))
        s = analyze(matches, user['puuid'])
        account = account or {"name": user['game_name'], "tag": user['tag_line'], "level": 0, "card": {}, "title": ""}
        rank, rr = "Derecesiz", 0
        md = (mmr or {}).get('data') if isinstance(mmr, dict) else None
        if isinstance(md, dict):
            cur = md.get('current_data') or md.get('current') or md
            if isinstance(cur, dict):
                tier_obj = cur.get('tier')
                rank = cur.get('currenttierpatched') or (tier_obj.get('name') if isinstance(tier_obj, dict) else None) or 'Derecesiz'
                rr = cur.get('ranking_in_tier') or cur.get('rr') or 0
        color = int(user.get('profile_color') or 0xFF4655)
        title = f"{user.get('profile_emoji') or '🎯'} {account['name']}#{account['tag']}"
        e1 = discord.Embed(title=title, description=f"Son **{s['matches']}** maçın performans özeti", color=color)
        e1.add_field(name="Rank", value=f"**{rank}**\n`{rr} RR`", inline=True)
        e1.add_field(name="K/D", value=f"`{s['kd']}`", inline=True)
        e1.add_field(name="Win Rate", value=f"`%{s['winrate']}`", inline=True)
        e1.add_field(name="K / D / A", value=f"`{s['kills']} / {s['deaths']} / {s['assists']}`", inline=False)
        e1.add_field(name="Ana Ajan", value=s['main_agent'], inline=True)
        e1.add_field(name="HS", value=f"`%{s['hs_rate']}`", inline=True)
        e1.add_field(name="ADR / ACS", value=f"`{s['adr']} / {s['acs']}`", inline=True)
        card = account.get('card') or {}
        if isinstance(card, dict) and card.get('small'): e1.set_thumbnail(url=card['small'])
        if user.get('profile_banner'): e1.set_image(url=user['profile_banner'])
        e1.set_footer(text="V-Tracker • Sayfa 1/3 • Genel Bakış")
        e2 = discord.Embed(title=title, description="Çatışma ve isabet analizi", color=color)
        e2.add_field(name="Toplam hasar", value=f"`{s['damage']:,}`", inline=True)
        e2.add_field(name="Analiz edilen tur", value=f"`{s['rounds']}`", inline=True)
        e2.add_field(name="ADR", value=f"`{s['adr']}`", inline=True)
        e2.add_field(name="Vuruş dağılımı", value=f"Head: `{s['hs']}`\nBody: `{s['body']}`\nLeg: `{s['leg']}`", inline=False)
        e2.add_field(name="Ajan kullanımı", value="\n".join(f"• **{a}** — {n} maç" for a,n in s['agents']) or "Veri yok", inline=False)
        e2.set_footer(text="V-Tracker • Sayfa 2/3 • Combat")
        e3 = discord.Embed(title=title, description="Harita ve silah özeti", color=color)
        e3.add_field(name="Haritalar", value="\n".join(f"• **{m}** — {d['played']} maç / {d['won']} galibiyet" for m,d in s['maps']) or "Veri yok", inline=False)
        e3.add_field(name="Öne çıkan silahlar", value="\n".join(f"• **{w}** — {n} kill" for w,n in s['weapons']) or "Veri yok", inline=False)
        e3.set_footer(text="V-Tracker • Sayfa 3/3 • Harita/Silah")
        await ctx.send(embed=e1, view=Pages([e1,e2,e3], ctx.author.id))

    @commands.hybrid_command(name="lastmatch", aliases=["sonmac", "sonmaç"], description="Son maçını hızlı özetler.")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def lastmatch(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user: return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session, user['region'], user['puuid'], 1)
        matches = (payload or {}).get('data', [])
        if not matches: return await ctx.send(embed=error("Maç bulunamadı", "Son maç verisi alınamadı."))
        s = analyze(matches, user['puuid']); m = matches[0]; meta = m.get('metadata') or {}
        e = info("Son maç", f"**{user['game_name']}#{user['tag_line']}**")
        e.add_field(name="Harita", value=str(meta.get('map') or 'Bilinmiyor'), inline=True)
        e.add_field(name="K/D/A", value=f"`{s['kills']} / {s['deaths']} / {s['assists']}`", inline=True)
        e.add_field(name="K/D", value=str(s['kd']), inline=True)
        e.add_field(name="HS", value=f"%{s['hs_rate']}", inline=True)
        e.add_field(name="ADR", value=str(s['adr']), inline=True)
        e.add_field(name="Ajan", value=s['main_agent'], inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="compare", aliases=["karsilastir", "kıyasla"], description="İki kayıtlı Discord kullanıcısının son maç performansını karşılaştırır.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def compare(self, ctx: commands.Context, member: discord.Member):
        u1, u2 = await db.get_user(ctx.author.id), await db.get_user(member.id)
        if not u1 or not u2: return await ctx.send(embed=error("Kayıt eksik", "Karşılaştırmadaki iki kullanıcının da kayıtlı olması gerekiyor."))
        async with aiohttp.ClientSession() as session:
            p1, p2 = await __import__('asyncio').gather(api.matches(session,u1['region'],u1['puuid'],10), api.matches(session,u2['region'],u2['puuid'],10))
        s1 = analyze((p1 or {}).get('data',[]), u1['puuid']); s2 = analyze((p2 or {}).get('data',[]), u2['puuid'])
        e = info("Oyuncu karşılaştırması", f"Son maç örneklemi üzerinden **{ctx.author.display_name}** vs **{member.display_name}**")
        e.add_field(name=f"{u1['game_name']}#{u1['tag_line']}", value=f"K/D `{s1['kd']}`\nHS `%{s1['hs_rate']}`\nADR `{s1['adr']}`\nWR `%{s1['winrate']}`", inline=True)
        e.add_field(name="VS", value="⚔️", inline=True)
        e.add_field(name=f"{u2['game_name']}#{u2['tag_line']}", value=f"K/D `{s2['kd']}`\nHS `%{s2['hs_rate']}`\nADR `{s2['adr']}`\nWR `%{s2['winrate']}`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="coach", aliases=["koc", "koç", "analiz"], description="Son maç verilerinden kişisel çalışma önerisi üretir.")
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def coach(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user: return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session,user['region'],user['puuid'],15)
        s = analyze((payload or {}).get('data',[]),user['puuid'])
        if not s['matches']: return await ctx.send(embed=error("Analiz yok", "Yeterli maç verisi alınamadı."))
        notes=[]
        if s['kd'] < .9: notes.append("• **Hayatta kalma / trade:** ilk temastan sonra tekrar peek sayısını azalt; takım arkadaşına trade mesafesinde oyna.")
        elif s['kd'] >= 1.2: notes.append("• **Mekanik güçlü:** ilk temas avantajını koru; gereksiz ikinci düellolar yerine sayı üstünlüğünü oyna.")
        else: notes.append("• **K/D dengeli:** round etkisini artırmak için ilk ölüm oranını azaltmaya odaklan.")
        if s['hs_rate'] < 20: notes.append("• **Crosshair placement:** 10–15 dk head-level pre-aim ve kısa burst rutini ekle.")
        else: notes.append("• **İsabet:** HS oranı iyi; hareket halinde ateş ve recoil disiplinini koru.")
        if s['adr'] < 120: notes.append("• **Hasar üretimi:** util ile temas öncesi avantaj yarat; boş ölmek yerine en az bir trade/hasar hedefle.")
        if s['winrate'] < 50: notes.append("• **Round kazanımı:** kill yerine spike, rotasyon ve sayı üstünlüğü kararlarını öne çıkar.")
        e=info("V-Coach Analizi", f"**{user['game_name']}#{user['tag_line']}** • {s['matches']} maçlık örnek")
        e.add_field(name="Özet", value=f"K/D `{s['kd']}` • HS `%{s['hs_rate']}` • ADR `{s['adr']}` • WR `%{s['winrate']}`", inline=False)
        e.add_field(name="Çalışma planı", value="\n".join(notes), inline=False)
        e.add_field(name="Ana ajan", value=s['main_agent'], inline=True)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Stats(bot))
