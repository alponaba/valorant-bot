from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands

from database import db
from theme import add_metric_grid, error, info, panel
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
    agents = Counter()
    maps = defaultdict(lambda: {"played": 0, "won": 0})
    weapons = Counter()
    recent_kd = []
    valid = 0

    for m in matches:
        if not isinstance(m, dict):
            continue
        p = _player_from_match(m, puuid)
        if not p:
            continue
        valid += 1
        st = p.get("stats") or p
        k = int(st.get("kills") or 0)
        d = int(st.get("deaths") or 0)
        a = int(st.get("assists") or 0)
        kills += k
        deaths += d
        assists += a
        recent_kd.append(round(k / d, 2) if d else float(k))
        score_sum += int(st.get("score") or 0)
        hs += int(st.get("headshots") or 0)
        body += int(st.get("bodyshots") or 0)
        leg += int(st.get("legshots") or 0)
        char = p.get("character") or p.get("agent") or "Bilinmiyor"
        agents[char] += 1
        meta = m.get("metadata") or {}
        map_name = meta.get("map") or meta.get("map_name") or "Bilinmiyor"
        maps[map_name]["played"] += 1
        team = str(p.get("team") or "").lower()
        teams = m.get("teams") or {}
        won = False
        if isinstance(teams, dict):
            t = teams.get(team) or teams.get(team.capitalize()) or {}
            won = bool(t.get("has_won") or t.get("won")) if isinstance(t, dict) else False
        if won:
            wins += 1
            maps[map_name]["won"] += 1
        else:
            losses += 1
        rounds += int(meta.get("rounds_played") or m.get("rounds_played") or 0)
        dmg = p.get("damage_made") or p.get("damage") or 0
        if isinstance(dmg, dict):
            dmg = dmg.get("made") or dmg.get("damage_made") or 0
        damage += int(dmg or 0)
        kills_arr = m.get("kills")
        if isinstance(kills_arr, list):
            for kill in kills_arr:
                if isinstance(kill, dict) and (kill.get("killer_puuid") == puuid or kill.get("killer") == puuid):
                    w = kill.get("damage_weapon_name") or kill.get("weapon") or ""
                    if w:
                        weapons[w] += 1

    rounds = max(rounds, 1)
    shots = hs + body + leg
    kd = round(kills / deaths, 2) if deaths else float(kills)
    return {
        "matches": valid,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kd": kd,
        "hs": hs,
        "body": body,
        "leg": leg,
        "hs_rate": round(hs / shots * 100, 1) if shots else 0,
        "adr": round(damage / rounds, 1),
        "acs": round(score_sum / rounds, 1),
        "damage": damage,
        "rounds": rounds,
        "wins": wins,
        "losses": losses,
        "winrate": round(wins / valid * 100, 1) if valid else 0,
        "main_agent": agents.most_common(1)[0][0] if agents else "Bilinmiyor",
        "agents": agents.most_common(5),
        "maps": sorted(maps.items(), key=lambda x: x[1]["played"], reverse=True)[:5],
        "weapons": weapons.most_common(5),
        "recent_kd": recent_kd[:10],
        "avg_recent_kd": round(mean(recent_kd), 2) if recent_kd else 0,
    }


def rank_from_mmr(mmr: dict | None) -> tuple[str, int]:
    rank, rr = "Derecesiz", 0
    md = (mmr or {}).get("data") if isinstance(mmr, dict) else None
    if isinstance(md, dict):
        cur = md.get("current_data") or md.get("current") or md
        if isinstance(cur, dict):
            tier_obj = cur.get("tier")
            rank = cur.get("currenttierpatched") or (tier_obj.get("name") if isinstance(tier_obj, dict) else None) or "Derecesiz"
            rr = int(cur.get("ranking_in_tier") or cur.get("rr") or 0)
    return rank, rr


def compute_vscore(s: Dict[str, Any], rank: str) -> int:
    kd_score = min(240, int(s["kd"] * 130))
    hs_score = min(180, int(s["hs_rate"] * 5.5))
    adr_score = min(220, int(s["adr"] * 1.45))
    wr_score = min(180, int(s["winrate"] * 2.2))
    acs_score = min(180, int(s["acs"] * 0.8))
    rank_bonus_map = {
        "iron": 10, "bronze": 25, "silver": 40, "gold": 60, "platinum": 90,
        "diamond": 120, "ascendant": 150, "immortal": 180, "radiant": 220,
    }
    rank_bonus = 0
    low = rank.lower()
    for key, value in rank_bonus_map.items():
        if key in low:
            rank_bonus = value
            break
    return max(0, min(1000, kd_score + hs_score + adr_score + wr_score + acs_score + rank_bonus))


def form_label(s: Dict[str, Any]) -> str:
    if s["winrate"] >= 60 and s["avg_recent_kd"] >= 1.15:
        return "Yükseliyor"
    if s["winrate"] <= 45 and s["avg_recent_kd"] < 1.0:
        return "Düşüşte"
    return "Dengeli"


def performance_bars(s: Dict[str, Any]) -> Dict[str, int]:
    return {
        "Aim": max(0, min(100, int((s["hs_rate"] * 1.9) + (s["acs"] * 0.08)))),
        "Impact": max(0, min(100, int((s["adr"] * 0.55) + (s["acs"] * 0.12)))),
        "Survival": max(0, min(100, int(max(0.0, 2.0 - min(2.0, s["deaths"] / max(1, s["matches"] * 15))) * 50))),
        "Consistency": max(0, min(100, int((s["winrate"] * 0.8) + (s["kd"] * 18)))),
        "Clutch": max(0, min(100, int((s["kd"] * 28) + (s["hs_rate"] * 0.9)))),
    }


def build_achievements(s: Dict[str, Any], rank: str) -> List[str]:
    out = []
    if s["hs_rate"] >= 25:
        out.append("🎯 Sharpshooter — %25+ HS")
    if s["kd"] >= 1.2:
        out.append("⚔️ Duel Winner — 1.20+ K/D")
    if s["adr"] >= 140:
        out.append("💥 Impact Dealer — 140+ ADR")
    if s["winrate"] >= 60:
        out.append("🔥 Climber — %60+ WR")
    if "diamond" in rank.lower() or "ascendant" in rank.lower() or "immortal" in rank.lower() or "radiant" in rank.lower():
        out.append(f"🏅 Ranked Up — {rank}")
    return out or ["Henüz eşik tabanlı achievement açılmadı."]


def training_plan(s: Dict[str, Any]) -> List[str]:
    notes = []
    if s["hs_rate"] < 20:
        notes.append("Crosshair placement ve head-level pre-aim için 10–15 dk aim routine ekle.")
    else:
        notes.append("HS oranı iyi; hareketli hedefte burst discipline ve counter-strafe koru.")
    if s["adr"] < 120:
        notes.append("Round başına hasar düşük. Temas öncesi utility ile avantaj üret ve her round en az bir trade hedefle.")
    elif s["adr"] >= 150:
        notes.append("Hasar üretimin güçlü. Sayı üstünlüğü sonrası gereksiz re-peek azaltılırsa maç taşıma oranı artar.")
    if s["kd"] < 1.0:
        notes.append("İlk temastan sonra ikinci düelloya zorlama. Takım arkadaşına trade mesafesinde oyna.")
    if s["winrate"] < 50:
        notes.append("Macro kararları geliştir: retake, rotasyon ve spike temposu kill sayısından daha fazla round kazandırır.")
    if s["main_agent"] != "Bilinmiyor":
        notes.append(f"Ana ajanın **{s['main_agent']}**. Bu ajan için entry/anchor rolüne uygun utility rutini çalış.")
    return notes[:4]


class DashboardView(discord.ui.View):
    def __init__(self, embeds: Dict[str, discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.author_id = author_id
        self.current = "overview"
        self._update_styles()

    def _update_styles(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.secondary
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == self.current:
                child.style = discord.ButtonStyle.primary
                break

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu panel sana ait değil.", ephemeral=True)
            return False
        return True

    async def _switch(self, interaction: discord.Interaction, key: str):
        self.current = key
        self._update_styles()
        await interaction.response.edit_message(embed=self.embeds[key], view=self)

    @discord.ui.button(label="Genel", emoji="🏠", custom_id="overview")
    async def overview(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._switch(interaction, "overview")

    @discord.ui.button(label="Performans", emoji="📈", custom_id="performance")
    async def performance(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._switch(interaction, "performance")

    @discord.ui.button(label="Ajan & Harita", emoji="🗺️", custom_id="maps")
    async def maps_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._switch(interaction, "maps")

    @discord.ui.button(label="Koç", emoji="🧠", custom_id="coach")
    async def coach(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._switch(interaction, "coach")


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _fetch(self, user: dict, match_size: int = 15):
        async with aiohttp.ClientSession() as session:
            account_p, mmr_p, matches_p = await asyncio.gather(
                api.account_by_puuid(session, user["puuid"]),
                api.mmr(session, user["region"], user["puuid"]),
                api.matches(session, user["region"], user["puuid"], match_size),
            )
        return api.account_data(account_p), mmr_p, (matches_p or {}).get("data", [])

    def _build_dashboard_embeds(self, user: dict, account: dict, rank: str, rr: int, s: Dict[str, Any]) -> Dict[str, discord.Embed]:
        color = int(user.get("profile_color") or 0x2FD6C4)
        title = f"{user.get('profile_emoji') or '🎯'} {account['name']}#{account['tag']}"
        vscore = compute_vscore(s, rank)
        bars = performance_bars(s)
        achievements = build_achievements(s, rank)
        form = form_label(s)

        e1 = panel(title, f"Son **{s['matches']}** maç üzerinden oluşturulan V-Tracker Player Hub")
        e1.color = color
        add_metric_grid(e1, [
            ("Rank", f"**{rank}**\n`{rr} RR`"),
            ("V-Score", f"`{vscore} / 1000`"),
            ("Form", f"`{form}`"),
            ("K/D", f"`{s['kd']}`"),
            ("HS", f"`%{s['hs_rate']}`"),
            ("WR", f"`%{s['winrate']}`"),
        ])
        e1.add_field(name="K/D/A", value=f"`{s['kills']} / {s['deaths']} / {s['assists']}`", inline=False)
        e1.add_field(name="Ana ajan", value=s["main_agent"], inline=True)
        e1.add_field(name="ADR / ACS", value=f"`{s['adr']} / {s['acs']}`", inline=True)
        e1.add_field(name="Açılan achievement'lar", value="\n".join(f"• {x}" for x in achievements[:4]), inline=False)

        e2 = panel(f"{title} • Performans", "V-Tracker segment skoru + ham metrikler")
        e2.color = color
        e2.add_field(name="Segmentler", value="\n".join(f"**{k}** — `{v}`" for k, v in bars.items()), inline=False)
        e2.add_field(name="Combat", value=f"Hasar: `{s['damage']:,}`\nTurlar: `{s['rounds']}`\nWin/Loss: `{s['wins']}/{s['losses']}`", inline=True)
        recent = " • ".join(str(v) for v in s["recent_kd"][:5]) or "Veri yok"
        e2.add_field(name="Son K/D akışı", value=recent, inline=True)
        e2.add_field(name="Silahlar", value="\n".join(f"• **{w}** — {n} kill" for w, n in s["weapons"]) or "Veri yok", inline=False)

        e3 = panel(f"{title} • Ajan & Harita", "Oyun alışkanlıklarını hızlı okumak için özet")
        e3.color = color
        e3.add_field(name="Ajan kullanımı", value="\n".join(f"• **{a}** — {n} maç" for a, n in s["agents"]) or "Veri yok", inline=False)
        map_lines = []
        for name, data in s["maps"]:
            wr = round((data["won"] / max(1, data["played"])) * 100, 1)
            map_lines.append(f"• **{name}** — {data['played']} maç / %{wr} WR")
        e3.add_field(name="Haritalar", value="\n".join(map_lines) or "Veri yok", inline=False)
        if user.get("profile_banner"):
            e3.set_image(url=user["profile_banner"])

        e4 = panel(f"{title} • V-Coach 2.0", "Veriden üretilmiş kısa çalışma planı")
        e4.color = color
        e4.add_field(name="Odak alanları", value="\n".join(f"• {x}" for x in training_plan(s)), inline=False)
        e4.add_field(name="Özet", value=f"Rank: **{rank}**\nV-Score: `{vscore}`\nForm: `{form}`", inline=True)
        e4.add_field(name="Ana ajan", value=s["main_agent"], inline=True)
        card = account.get("card") or {}
        if isinstance(card, dict) and card.get("small"):
            for emb in (e1, e2, e3, e4):
                emb.set_thumbnail(url=card["small"])
        return {"overview": e1, "performance": e2, "maps": e3, "coach": e4}

    @commands.hybrid_command(name="stats", aliases=["profil", "istatistik", "profile", "hub"], description="Kayıtlı oyuncunun detaylı V-Tracker panelini gösterir.")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def stats(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = await db.get_user(member.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", f"{member.display_name} için kayıt bulunamadı. `v!register` kullan."))
        if ctx.interaction:
            await ctx.defer()
        account, mmr, matches = await self._fetch(user, 15)
        if not matches:
            return await ctx.send(embed=error("Maç verisi alınamadı", "API yanıt vermedi veya son maç verisi yok."))
        s = analyze(matches, user["puuid"])
        account = account or {"name": user["game_name"], "tag": user["tag_line"], "level": 0, "card": {}, "title": ""}
        rank, rr = rank_from_mmr(mmr)
        embeds = self._build_dashboard_embeds(user, account, rank, rr, s)
        await ctx.send(embed=embeds["overview"], view=DashboardView(embeds, ctx.author.id))

    @commands.hybrid_command(name="lastmatch", aliases=["sonmac", "sonmaç"], description="Son maçını profesyonel kart olarak gösterir.")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def lastmatch(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session:
            payload = await api.matches(session, user["region"], user["puuid"], 1)
        matches = (payload or {}).get("data", [])
        if not matches:
            return await ctx.send(embed=error("Maç bulunamadı", "Son maç verisi alınamadı."))
        s = analyze(matches, user["puuid"])
        m = matches[0]
        meta = m.get("metadata") or {}
        teams = m.get("teams") or {}
        p = _player_from_match(m, user["puuid"]) or {}
        team = str(p.get("team") or "").lower()
        won = False
        if isinstance(teams, dict):
            t = teams.get(team) or teams.get(team.capitalize()) or {}
            won = bool(t.get("has_won") or t.get("won")) if isinstance(t, dict) else False
        agent = p.get("character") or p.get("agent") or s["main_agent"]
        e = panel("📋 Match Card", f"**{'VICTORY' if won else 'DEFEAT'}** • {meta.get('map') or 'Bilinmiyor'}")
        e.add_field(name="Oyuncu", value=f"**{user['game_name']}#{user['tag_line']}**", inline=False)
        add_metric_grid(e, [
            ("Ajan", agent),
            ("K/D/A", f"`{s['kills']} / {s['deaths']} / {s['assists']}`"),
            ("K/D", f"`{s['kd']}`"),
            ("HS", f"`%{s['hs_rate']}`"),
            ("ADR", f"`{s['adr']}`"),
            ("ACS", f"`{s['acs']}`"),
        ])
        e.add_field(name="V-Tracker Rating", value=f"`{compute_vscore(s, 'Derecesiz') / 100:.1f} / 10`", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="compare", aliases=["karsilastir", "kıyasla"], description="İki kayıtlı Discord kullanıcısını gelişmiş karşılaştırır.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def compare(self, ctx: commands.Context, member: discord.Member):
        u1, u2 = await db.get_user(ctx.author.id), await db.get_user(member.id)
        if not u1 or not u2:
            return await ctx.send(embed=error("Kayıt eksik", "Karşılaştırmadaki iki kullanıcının da kayıtlı olması gerekiyor."))
        async with aiohttp.ClientSession() as session:
            p1, p2 = await asyncio.gather(
                api.matches(session, u1["region"], u1["puuid"], 10),
                api.matches(session, u2["region"], u2["puuid"], 10),
            )
        s1 = analyze((p1 or {}).get("data", []), u1["puuid"])
        s2 = analyze((p2 or {}).get("data", []), u2["puuid"])
        e = panel("⚔️ Oyuncu Karşılaştırması", f"Son 10 maç örneklemi • **{ctx.author.display_name}** vs **{member.display_name}**")
        left_score = compute_vscore(s1, "Derecesiz")
        right_score = compute_vscore(s2, "Derecesiz")
        e.add_field(name=f"{u1['game_name']}#{u1['tag_line']}", value=f"V-Score `{left_score}`\nK/D `{s1['kd']}`\nHS `%{s1['hs_rate']}`\nADR `{s1['adr']}`\nWR `%{s1['winrate']}`", inline=True)
        e.add_field(name="Kazanan", value=(ctx.author.mention if left_score >= right_score else member.mention), inline=True)
        e.add_field(name=f"{u2['game_name']}#{u2['tag_line']}", value=f"V-Score `{right_score}`\nK/D `{s2['kd']}`\nHS `%{s2['hs_rate']}`\nADR `{s2['adr']}`\nWR `%{s2['winrate']}`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="coach", aliases=["koc", "koç", "analiz"], description="Son maç verilerinden kişisel çalışma önerisi üretir.")
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def coach(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user:
            return await ctx.send(embed=error("Kayıt yok", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session:
            payload = await api.matches(session, user["region"], user["puuid"], 15)
        s = analyze((payload or {}).get("data", []), user["puuid"])
        if not s["matches"]:
            return await ctx.send(embed=error("Analiz yok", "Yeterli maç verisi alınamadı."))
        e = panel("🧠 V-Coach Analizi", f"**{user['game_name']}#{user['tag_line']}** • {s['matches']} maçlık örnek")
        e.add_field(name="Özet", value=f"K/D `{s['kd']}` • HS `%{s['hs_rate']}` • ADR `{s['adr']}` • WR `%{s['winrate']}`", inline=False)
        e.add_field(name="Çalışma planı", value="\n".join(f"• {x}" for x in training_plan(s)), inline=False)
        e.add_field(name="Performans çubukları", value="\n".join(f"**{k}** — `{v}`" for k, v in performance_bars(s).items()), inline=False)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Stats(bot))
