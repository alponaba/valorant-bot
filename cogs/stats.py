from __future__ import annotations

import asyncio
import hashlib
from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Dict, List, Optional

import aiohttp
import discord
from discord.ext import commands

from database import db
from theme import add_metric_grid, error, panel
from v4_store import store
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


def match_key(match: dict) -> str:
    meta = match.get("metadata") or {}
    for key in ("matchid", "match_id", "game_id", "gameid", "id"):
        if meta.get(key):
            return str(meta[key])
        if match.get(key):
            return str(match[key])
    raw = "|".join(str(x) for x in (
        meta.get("map") or meta.get("map_name") or "?",
        meta.get("game_start") or meta.get("game_start_patched") or meta.get("started_at") or "?",
        meta.get("rounds_played") or match.get("rounds_played") or "?",
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def analyze(matches: List[dict], puuid: str) -> Dict[str, Any]:
    kills = deaths = assists = hs = body = leg = 0
    score_sum = damage = rounds = wins = losses = 0
    agents = Counter()
    maps = defaultdict(lambda: {"played": 0, "won": 0})
    weapons = Counter()
    recent_kd: list[float] = []
    per_match: list[dict] = []
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
        kd_one = round(k / d, 2) if d else float(k)
        kills += k
        deaths += d
        assists += a
        recent_kd.append(kd_one)
        score_sum += int(st.get("score") or 0)
        phs = int(st.get("headshots") or 0)
        pbody = int(st.get("bodyshots") or 0)
        pleg = int(st.get("legshots") or 0)
        hs += phs
        body += pbody
        leg += pleg
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
        mrounds = int(meta.get("rounds_played") or m.get("rounds_played") or 0)
        rounds += mrounds
        dmg = p.get("damage_made") or p.get("damage") or 0
        if isinstance(dmg, dict):
            dmg = dmg.get("made") or dmg.get("damage_made") or 0
        dmg = int(dmg or 0)
        damage += dmg
        shots_one = phs + pbody + pleg
        per_match.append({
            "key": match_key(m), "map": map_name, "agent": char, "won": won,
            "kills": k, "deaths": d, "assists": a, "kd": kd_one,
            "hs_rate": round(phs / shots_one * 100, 1) if shots_one else 0,
            "adr": round(dmg / max(1, mrounds), 1),
        })
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
        "matches": valid, "kills": kills, "deaths": deaths, "assists": assists, "kd": kd,
        "hs": hs, "body": body, "leg": leg, "hs_rate": round(hs / shots * 100, 1) if shots else 0,
        "adr": round(damage / rounds, 1), "acs": round(score_sum / rounds, 1), "damage": damage,
        "rounds": rounds, "wins": wins, "losses": losses,
        "winrate": round(wins / valid * 100, 1) if valid else 0,
        "main_agent": agents.most_common(1)[0][0] if agents else "Bilinmiyor",
        "agents": agents.most_common(5), "maps": sorted(maps.items(), key=lambda x: x[1]["played"], reverse=True)[:5],
        "weapons": weapons.most_common(5), "recent_kd": recent_kd[:10],
        "avg_recent_kd": round(mean(recent_kd), 2) if recent_kd else 0, "per_match": per_match,
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
    return str(rank), rr


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
    rank_bonus = next((value for key, value in rank_bonus_map.items() if key in rank.lower()), 0)
    return max(0, min(1000, kd_score + hs_score + adr_score + wr_score + acs_score + rank_bonus))


def form_label(s: Dict[str, Any]) -> str:
    if s["winrate"] >= 60 and s["avg_recent_kd"] >= 1.15:
        return "Yükseliyor"
    if s["winrate"] <= 45 and s["avg_recent_kd"] < 1.0:
        return "Düşüşte"
    return "Dengeli"


def tilt_score(s: Dict[str, Any]) -> int:
    recent = s.get("per_match", [])
    score = 0
    if s["winrate"] < 45:
        score += int((45 - s["winrate"]) * 1.4)
    if s["kd"] < 1.0:
        score += int((1.0 - s["kd"]) * 55)
    if len(recent) >= 6:
        newest = mean(x["kd"] for x in recent[:3])
        older = mean(x["kd"] for x in recent[-3:])
        if newest < older:
            score += min(30, int((older - newest) * 35))
    streak = 0
    for m in recent:
        if m["won"]:
            break
        streak += 1
    score += min(35, streak * 9)
    return max(0, min(100, score))


def performance_bars(s: Dict[str, Any]) -> Dict[str, int]:
    return {
        "Aim": max(0, min(100, int((s["hs_rate"] * 1.9) + (s["acs"] * 0.08)))),
        "Impact": max(0, min(100, int((s["adr"] * 0.55) + (s["acs"] * 0.12)))),
        "Survival": max(0, min(100, int(45 + (s["kd"] - 1.0) * 35))),
        "Consistency": max(0, min(100, int((s["winrate"] * 0.75) + (s["kd"] * 22)))),
        "Clutch": max(0, min(100, int((s["kd"] * 28) + (s["hs_rate"] * 0.9)))),
    }


def player_dna(s: Dict[str, Any]) -> tuple[str, Dict[str, int]]:
    bars = performance_bars(s)
    if bars["Impact"] >= 78 and s["kd"] >= 1.15:
        style = "Aggressive Carry" if bars["Survival"] < 70 else "Controlled Fragger"
    elif bars["Aim"] >= 75 and s["hs_rate"] >= 24:
        style = "Precision Duelist"
    elif bars["Consistency"] >= 72 and s["winrate"] >= 52:
        style = "Stable Team Player"
    elif s["adr"] < 120 and s["kd"] >= 1.0:
        style = "Low-Risk Finisher"
    else:
        style = "Flexible Hybrid"
    return style, bars


def build_achievements(s: Dict[str, Any], rank: str) -> List[str]:
    out = []
    if s["hs_rate"] >= 25: out.append("Sharpshooter — %25+ HS")
    if s["kd"] >= 1.2: out.append("Duel Winner — 1.20+ K/D")
    if s["adr"] >= 140: out.append("Impact Dealer — 140+ ADR")
    if s["winrate"] >= 60: out.append("Climber — %60+ WR")
    if any(x in rank.lower() for x in ("diamond", "ascendant", "immortal", "radiant")): out.append(f"Rank Milestone — {rank}")
    return out or ["Henüz eşik tabanlı achievement açılmadı."]


def _pick(options: list[str], seed: str) -> str:
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(options)
    return options[idx]


def personalized_plan(s: Dict[str, Any], user_id: int | str, variation: int) -> list[str]:
    uid = str(user_id)
    notes: list[str] = []
    if s["hs_rate"] < 18:
        notes.append(_pick([
            "Head-level hizanı maç başlamadan önce 8–10 dakika yalnızca pre-aim çizgilerine ayır; şu an en büyük mekanik kaybın crosshair yüksekliği tarafında görünüyor.",
            "Spray'i uzatmak yerine ilk 4–6 mermilik burstlere dön. HS yüzden düşük olduğu için antrenmanda skor yerine kafa hizasını sabit tutmayı ölç.",
            "Deathmatch'te ses kovalamadan köşe temizleme çalış. Hedefin kill sayısı değil, her açıya crosshair hazır girmek olsun.",
        ], f"aim-low:{uid}:{variation}"))
    elif s["hs_rate"] < 27:
        notes.append(_pick([
            "HS yüzden orta-iyi bantta. Bundan sonra kazanç crosshair'den çok ilk mermi sonrası hareket disiplininden gelir; burst sonrası yeniden konumlan.",
            "Aim tarafında temel sorun görünmüyor. Tek mermi doğruluğunu korurken gereksiz crouch-spray sayısını azaltmaya odaklan.",
            "Pre-aim seviyen yeterli görünüyor; şimdi mikro düzeltmelerde fazla mouse hareketini azaltmak daha fazla değer üretir.",
        ], f"aim-mid:{uid}:{variation}"))
    else:
        notes.append(_pick([
            "HS yüzden güçlü; aim çalışmasını uzatmak yerine bu avantajı ilk temas seçimlerine taşı. Her round aynı açıdan kuru peek atma.",
            "Mekanik doğruluğun yüksek. Gelişim alanın artık daha çok hangi düelloyu aldığın: düşük değerli re-peekleri keserek aynı aim ile daha fazla round kazanabilirsin.",
            "Kafa vuruş oranı yüksek olduğu için ekstra aim grind yerine movement + angle isolation çalışman daha verimli olur.",
        ], f"aim-high:{uid}:{variation}"))

    if s["adr"] < 115:
        notes.append(_pick([
            "ADR düşük. Ölmeden önce rounda somut hasar bırakmak için utility sonrası temas kur; özellikle takım girişinden kopuk oynamamaya dikkat et.",
            "Hasar üretimin kill sayısından daha zayıf. Temas öncesi boş bekleme süresini azaltıp takımın info/flash penceresine aynı anda çık.",
            "Round etkisini artırmak için ilk çatışmaya çok geç kalma. Güvenli oynamak ile rounddan kopmak arasındaki çizgiyi kontrol et.",
        ], f"adr-low:{uid}:{variation}"))
    elif s["adr"] >= 150:
        notes.append(_pick([
            "ADR güçlü. Burada amaç daha fazla çatışma değil; ilk avantajdan sonra hayatta kalarak hasarı round kazanımına çevirmek.",
            "Hasar üretimin taşıyıcı seviyede. Sayı üstünlüğü oluşunca ikinci solo düelloyu azaltırsan WR tarafında daha net karşılık alırsın.",
            "Impact yüksek; aynı etkiyi daha az ölümle üretmeye odaklan. Özellikle avantajlı roundlarda trade edilebilir mesafeden ayrılma.",
        ], f"adr-high:{uid}:{variation}"))

    if s["kd"] < .9:
        notes.append(_pick([
            "K/D tarafında ana hedef ekstra kill değil, ilk ölüm sayısını azaltmak. Temastan sonra aynı açıya tekrar çıkmadan önce takım bilgisini bekle.",
            "Ölüm maliyetin yüksek görünüyor. Entry değilsen ilk teması zorlamak yerine trade mesafesi kur; entry isen kaçış rotanı peekten önce belirle.",
            "Düello seçimin şu an mekanikten daha kritik. Rakibin hazır olduğu uzun açıları kuru peeklemek yerine utility veya çapraz ateş kullan.",
        ], f"kd-low:{uid}:{variation}"))
    elif s["kd"] >= 1.25:
        notes.append(_pick([
            "K/D güçlü. Skoru büyütmek yerine üstünlüğü korumaya odaklan; ilk kill sonrası 5v4'ü 4v4'e çevirecek gereksiz düellolardan kaçın.",
            "Bireysel düellolarda avantajlısın. Sonraki seviye, frag sonrası takımın alan kazanmasını hızlandırmak ve kendi ölümünü geciktirmek.",
            "Frag üretimin iyi; seni daha değerli yapacak şey round kapanış disiplini. Spike zamanı ve sayı üstünlüğünde risk katsayını düşür.",
        ], f"kd-high:{uid}:{variation}"))

    if s["winrate"] < 48:
        notes.append(_pick([
            "Kişisel statların round sonucuna tam dönüşmüyor. Rotasyon kararını kill feed yerine bilgi + spike konumuna bağlamayı dene.",
            "WR düşük kaldığı için bu blokta mekanik yerine macro hedef koy: her kaybedilen roundda karar hatasını 'tempo, rotasyon, sayı üstünlüğü' diye etiketle.",
            "Maç kazanımında sorun var. Özellikle avantajlı roundların kaç tanesini verdiğini takip et; ekonomi ve spike kararları burada daha önemli olabilir.",
        ], f"wr-low:{uid}:{variation}"))

    agent = s.get("main_agent") or "Bilinmiyor"
    if agent != "Bilinmiyor":
        notes.append(_pick([
            f"Ana ajanın {agent}. Bir sonraki maçta tek bir ajan hedefi seç: utility kullanımını round başına en az bir takım avantajına dönüştür.",
            f"{agent} üzerinde tekrar sayın yüksek. Mekanikten bağımsız olarak iki standart açılış ve iki retake rutini belirlemek tutarlılığı artırır.",
            f"{agent} ile oynarken her ölümden sonra 'yeteneğim elde mi kaldı?' kontrolü yap. Kullanılmadan kalan utility, görünmeyen round kaybı yaratabilir.",
        ], f"agent:{agent}:{uid}:{variation}"))

    risk = tilt_score(s)
    if risk >= 65:
        notes.append(_pick([
            f"Tilt riski {risk}/100. Son seri düşüş gösteriyor; sıradaki ranked yerine kısa ara + tek warm-up maçı daha mantıklı.",
            f"Form riski {risk}/100 seviyesinde. Hedefi RR'dan çıkarıp bir sonraki maç için tek davranış metriğine indir: ilk ölüm ve re-peek sayısı.",
            f"Tilt göstergesi {risk}/100. Arka arkaya queue atmak yerine reset süresi koy; performans düşüşü şu an karar kalitesini etkileyebilir.",
        ], f"tilt:{uid}:{variation}"))
    return notes[:5]


class DashboardView(discord.ui.View):
    def __init__(self, embeds: Dict[str, discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.embeds, self.author_id, self.current = embeds, author_id, "overview"
        self._update_styles()

    def _update_styles(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.style = discord.ButtonStyle.primary if child.custom_id == self.current else discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Bu panel sana ait değil.", ephemeral=True)
            return False
        return True

    async def _switch(self, interaction: discord.Interaction, key: str):
        self.current = key; self._update_styles()
        await interaction.response.edit_message(embed=self.embeds[key], view=self)

    @discord.ui.button(label="Genel", custom_id="overview")
    async def overview(self, interaction: discord.Interaction, _: discord.ui.Button): await self._switch(interaction, "overview")
    @discord.ui.button(label="Performans", custom_id="performance")
    async def performance(self, interaction: discord.Interaction, _: discord.ui.Button): await self._switch(interaction, "performance")
    @discord.ui.button(label="Ajan ve Harita", custom_id="maps")
    async def maps_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self._switch(interaction, "maps")
    @discord.ui.button(label="Koç", custom_id="coach")
    async def coach_btn(self, interaction: discord.Interaction, _: discord.ui.Button): await self._switch(interaction, "coach")


class Stats(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def _fetch(self, user: dict, match_size: int = 15):
        async with aiohttp.ClientSession() as session:
            account_p, mmr_p, matches_p = await asyncio.gather(
                api.account_by_puuid(session, user["puuid"]), api.mmr(session, user["region"], user["puuid"]),
                api.matches(session, user["region"], user["puuid"], match_size),
            )
        return api.account_data(account_p), mmr_p, (matches_p or {}).get("data", [])

    async def _snapshot(self, user: dict, rank: str, rr: int, s: Dict[str, Any], matches: list[dict]):
        key = match_key(matches[0]) if matches else ""
        latest = await store.latest_snapshot(user["discord_id"])
        # Avoid filling the DB with identical snapshots from repeated button/command use.
        if not latest or latest.get("match_key") != key or latest.get("rank") != rank or int(latest.get("rr") or 0) != rr:
            await store.add_snapshot(user["discord_id"], rank=rank, rr=rr, vscore=compute_vscore(s, rank), stats=s, match_key=key)

    async def _unique_coach_plan(self, user_id: int, s: Dict[str, Any]) -> list[str]:
        old_hashes = set(await store.recent_coach_hashes(user_id, 30))
        count = await store.coach_count(user_id)
        for attempt in range(20):
            plan = personalized_plan(s, user_id, count + attempt)
            text = "\n".join(plan)
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
            if h not in old_hashes:
                await store.save_coach_response(user_id, text)
                return plan
        plan = personalized_plan(s, user_id, count + 97)
        plan.append(f"Bu analiz varyasyonu #{count + 1}; sonraki koç çağrısında önceki öneri geçmişi yeniden hesaba katılacak.")
        await store.save_coach_response(user_id, "\n".join(plan))
        return plan

    def _build_dashboard_embeds(self, user: dict, account: dict, rank: str, rr: int, s: Dict[str, Any], coach_plan: list[str]) -> Dict[str, discord.Embed]:
        color = int(user.get("profile_color") or 0x2FD6C4)
        title = f"{account['name']}#{account['tag']}"
        vscore, bars, achievements, form = compute_vscore(s, rank), performance_bars(s), build_achievements(s, rank), form_label(s)
        style, _ = player_dna(s)

        e1 = panel(title, f"Son **{s['matches']}** maç üzerinden oluşturulan oyuncu özeti")
        e1.color = color
        add_metric_grid(e1, [("Rank", f"**{rank}**\n`{rr} RR`"), ("V-Score", f"`{vscore} / 1000`"), ("Player DNA", f"`{style}`"),
                             ("K/D", f"`{s['kd']}`"), ("HS", f"`%{s['hs_rate']}`"), ("WR", f"`%{s['winrate']}`")])
        e1.add_field(name="Form", value=f"{form} • Tilt riski `{tilt_score(s)}/100`", inline=False)
        e1.add_field(name="K/D/A", value=f"`{s['kills']} / {s['deaths']} / {s['assists']}`", inline=True)
        e1.add_field(name="Ana ajan", value=s["main_agent"], inline=True)
        e1.add_field(name="ADR / ACS", value=f"`{s['adr']} / {s['acs']}`", inline=True)
        e1.add_field(name="Achievement", value="\n".join(f"• {x}" for x in achievements[:4]), inline=False)

        e2 = panel(f"{title} — Performans", "Segment skorları, çatışma üretimi ve son maç akışı")
        e2.color = color
        e2.add_field(name="Player DNA", value="\n".join(f"**{k}**  `{v}/100`" for k, v in bars.items()), inline=False)
        e2.add_field(name="Combat", value=f"Hasar `{s['damage']:,}`\nTur `{s['rounds']}`\nW/L `{s['wins']}/{s['losses']}`", inline=True)
        e2.add_field(name="Son K/D akışı", value=" • ".join(str(v) for v in s["recent_kd"][:6]) or "Veri yok", inline=True)
        e2.add_field(name="Öne çıkan silahlar", value="\n".join(f"• **{w}** — {n} kill" for w, n in s["weapons"]) or "Veri yok", inline=False)

        e3 = panel(f"{title} — Ajan ve Harita", "Kullanım oranları ve kazanma eğilimleri")
        e3.color = color
        e3.add_field(name="Ajan kullanımı", value="\n".join(f"• **{a}** — {n} maç" for a, n in s["agents"]) or "Veri yok", inline=False)
        map_lines = [f"• **{name}** — {data['played']} maç / %{round(data['won']/max(1,data['played'])*100,1)} WR" for name, data in s["maps"]]
        e3.add_field(name="Harita zekâsı", value="\n".join(map_lines) or "Veri yok", inline=False)
        if user.get("profile_banner"): e3.set_image(url=user["profile_banner"])

        e4 = panel(f"{title} — Kişisel Koç", "Bu metin oyuncunun güncel verisi ve önceki koç mesajları dikkate alınarak seçildi")
        e4.color = color
        e4.add_field(name="Bugünkü çalışma planı", value="\n".join(f"• {x}" for x in coach_plan), inline=False)
        e4.add_field(name="Profil", value=f"V-Score `{vscore}` • {style} • Tilt `{tilt_score(s)}/100`", inline=False)
        card = account.get("card") or {}
        if isinstance(card, dict) and card.get("small"):
            for emb in (e1, e2, e3, e4): emb.set_thumbnail(url=card["small"])
        return {"overview": e1, "performance": e2, "maps": e3, "coach": e4}

    @commands.hybrid_command(name="stats", aliases=["profil", "istatistik", "profile", "hub"], description="Detaylı V-Tracker oyuncu panelini gösterir.")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def stats(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = await db.get_user(member.id)
        if not user: return await ctx.send(embed=error("Kayıt bulunamadı", f"{member.display_name} için kayıt yok. `v!register` kullan."))
        if ctx.interaction: await ctx.defer()
        account, mmr, matches = await self._fetch(user, 15)
        if not matches: return await ctx.send(embed=error("Maç verisi alınamadı", "API yanıt vermedi veya son maç verisi yok."))
        s = analyze(matches, user["puuid"]); rank, rr = rank_from_mmr(mmr)
        account = account or {"name": user["game_name"], "tag": user["tag_line"], "card": {}}
        await self._snapshot(user, rank, rr, s, matches)
        # Panelin koç sekmesi de her açılışta yeni metin üretmesin; burada varyasyon oluşturup tek panel boyunca sabit tutuyoruz.
        coach_plan = await self._unique_coach_plan(member.id, s)
        embeds = self._build_dashboard_embeds(user, account, rank, rr, s, coach_plan)
        await ctx.send(embed=embeds["overview"], view=DashboardView(embeds, ctx.author.id))

    @commands.hybrid_command(name="coach", aliases=["koc", "koç", "analiz"], description="Oyuncuya özel, tekrarsız çalışma önerisi üretir.")
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def coach(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user: return await ctx.send(embed=error("Kayıt bulunamadı", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session, user["region"], user["puuid"], 15)
        matches = (payload or {}).get("data", []); s = analyze(matches, user["puuid"])
        if not s["matches"]: return await ctx.send(embed=error("Analiz oluşturulamadı", "Yeterli maç verisi alınamadı."))
        plan = await self._unique_coach_plan(ctx.author.id, s)
        style, bars = player_dna(s)
        e = panel("Kişisel Koç Analizi", f"**{user['game_name']}#{user['tag_line']}** • {s['matches']} maçlık veri • {style}")
        e.add_field(name="Güncel profil", value=f"K/D `{s['kd']}` • HS `%{s['hs_rate']}` • ADR `{s['adr']}` • WR `%{s['winrate']}` • Tilt `{tilt_score(s)}/100`", inline=False)
        e.add_field(name="Sana özel öneriler", value="\n\n".join(f"**{i}.** {x}" for i, x in enumerate(plan, 1)), inline=False)
        e.add_field(name="DNA skorları", value=" • ".join(f"{k} `{v}`" for k, v in bars.items()), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="playerdna", aliases=["dna", "oyuncudna"], description="Oyuncunun oyun tarzı DNA profilini çıkarır.")
    async def playerdna_cmd(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author; user = await db.get_user(member.id)
        if not user: return await ctx.send(embed=error("Kayıt bulunamadı", "Bu kullanıcı kayıtlı değil."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session, user["region"], user["puuid"], 15)
        s = analyze((payload or {}).get("data", []), user["puuid"]); style, bars = player_dna(s)
        e = panel("Player DNA", f"**{user['game_name']}#{user['tag_line']}** için oyun tarzı profili")
        e.add_field(name="Arketip", value=f"**{style}**", inline=False)
        e.add_field(name="Skorlar", value="\n".join(f"**{k}** — `{v}/100`" for k, v in bars.items()), inline=False)
        e.add_field(name="Form riski", value=f"Tilt `{tilt_score(s)}/100` • Ana ajan **{s['main_agent']}**", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="intelligence", aliases=["zeka", "zekâ", "mapintel"], description="Ajan ve harita eğilimlerini yorumlar.")
    async def intelligence(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user: return await ctx.send(embed=error("Kayıt bulunamadı", "Önce kayıt ol."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session, user["region"], user["puuid"], 20)
        s = analyze((payload or {}).get("data", []), user["puuid"])
        maps = []
        for name, data in s["maps"]:
            wr = round(data["won"] / max(1, data["played"]) * 100, 1); maps.append((wr, name, data["played"]))
        maps.sort(reverse=True)
        e = panel("Ajan ve Harita Intelligence", f"**{user['game_name']}#{user['tag_line']}** için son {s['matches']} maç")
        if maps:
            e.add_field(name="En güçlü harita", value=f"**{maps[0][1]}** • %{maps[0][0]} WR • {maps[0][2]} maç", inline=True)
            e.add_field(name="Gelişim haritası", value=f"**{maps[-1][1]}** • %{maps[-1][0]} WR • {maps[-1][2]} maç", inline=True)
        e.add_field(name="Ajan havuzu", value="\n".join(f"• **{a}** — {n} maç" for a,n in s["agents"]) or "Veri yok", inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="lastmatch", aliases=["sonmac", "sonmaç"], description="Son maçı detaylı kart olarak gösterir.")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def lastmatch(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id)
        if not user: return await ctx.send(embed=error("Kayıt bulunamadı", "Önce `v!register` kullan."))
        async with aiohttp.ClientSession() as session: payload = await api.matches(session, user["region"], user["puuid"], 1)
        matches = (payload or {}).get("data", [])
        if not matches: return await ctx.send(embed=error("Maç bulunamadı", "Son maç verisi alınamadı."))
        s = analyze(matches, user["puuid"]); m = matches[0]; meta = m.get("metadata") or {}; p = _player_from_match(m, user["puuid"]) or {}
        won = bool(s["wins"]); agent = p.get("character") or p.get("agent") or s["main_agent"]; rating = compute_vscore(s, "Derecesiz")
        e = panel("Match Card", f"**{'VICTORY' if won else 'DEFEAT'}** • {meta.get('map') or meta.get('map_name') or 'Bilinmiyor'}")
        e.add_field(name="Oyuncu", value=f"**{user['game_name']}#{user['tag_line']}**", inline=False)
        add_metric_grid(e, [("Ajan", agent), ("K/D/A", f"`{s['kills']} / {s['deaths']} / {s['assists']}`"), ("K/D", f"`{s['kd']}`"),
                             ("HS", f"`%{s['hs_rate']}`"), ("ADR", f"`{s['adr']}`"), ("V-Rating", f"`{rating/100:.1f}/10`")])
        records = []
        for key, val, label in (("kills", s["kills"], "Kill"), ("kd", s["kd"], "K/D"), ("hs", s["hs_rate"], "HS"), ("adr", s["adr"], "ADR")):
            changed, old = await store.update_record(ctx.author.id, key, float(val), str(val))
            if changed and old != float('-inf'): records.append(f"Yeni {label} rekoru: `{val}`")
        if records: e.add_field(name="Yeni kişisel rekor", value="\n".join(records), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="records", aliases=["rekor", "rekorlar"], description="Kişisel rekorlarını gösterir.")
    async def records_cmd(self, ctx: commands.Context):
        rows = await store.records(ctx.author.id)
        if not rows: return await ctx.send(embed=error("Rekor verisi yok", "Önce birkaç kez `v!lastmatch` kullan veya otomatik takip açık kalsın."))
        names = {"kills":"En yüksek kill", "kd":"En yüksek K/D", "hs":"En yüksek HS", "adr":"En yüksek ADR", "vscore":"En yüksek V-Score", "rr":"En yüksek RR"}
        e = panel("Personal Records", "V-Tracker tarafından kaydedilen kişisel zirveler")
        e.add_field(name="Rekorlar", value="\n".join(f"**{names.get(r['record_key'], r['record_key'])}** — `{r['numeric_value']:g}`" for r in rows[:12]), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="trend", aliases=["gelisim", "gelişim"], description="Kaydedilmiş performans snapshot'larının değişimini gösterir.")
    async def trend(self, ctx: commands.Context):
        rows = await store.snapshots(ctx.author.id, 12)
        if len(rows) < 2: return await ctx.send(embed=error("Trend verisi yetersiz", "En az iki performans snapshot'ı gerekiyor."))
        newest, oldest = rows[0], rows[-1]
        e = panel("Performance Trend", f"Son **{len(rows)}** kayıt üzerinden değişim")
        e.add_field(name="Rank", value=f"{oldest['rank']} `{oldest['rr']} RR` → **{newest['rank']}** `{newest['rr']} RR`", inline=False)
        for key, label in (("vscore","V-Score"),("kd","K/D"),("hs_rate","HS"),("adr","ADR"),("winrate","WR")):
            diff = float(newest[key]) - float(oldest[key]); suffix = "%" if key in {"hs_rate","winrate"} else ""
            e.add_field(name=label, value=f"`{oldest[key]}{suffix}` → `{newest[key]}{suffix}`  ({diff:+.1f})", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="compare", aliases=["karsilastir", "kıyasla"], description="İki kayıtlı oyuncuyu karşılaştırır.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def compare(self, ctx: commands.Context, member: discord.Member):
        u1, u2 = await db.get_user(ctx.author.id), await db.get_user(member.id)
        if not u1 or not u2: return await ctx.send(embed=error("Kayıt eksik", "İki kullanıcının da kayıtlı olması gerekiyor."))
        async with aiohttp.ClientSession() as session:
            p1,p2 = await asyncio.gather(api.matches(session,u1["region"],u1["puuid"],10), api.matches(session,u2["region"],u2["puuid"],10))
        s1,s2 = analyze((p1 or {}).get("data",[]),u1["puuid"]), analyze((p2 or {}).get("data",[]),u2["puuid"])
        a,b = compute_vscore(s1,"Derecesiz"), compute_vscore(s2,"Derecesiz")
        e=panel("Oyuncu Karşılaştırması",f"Son 10 maç • **{ctx.author.display_name}** vs **{member.display_name}**")
        e.add_field(name=f"{u1['game_name']}#{u1['tag_line']}",value=f"V-Score `{a}`\nK/D `{s1['kd']}`\nHS `%{s1['hs_rate']}`\nADR `{s1['adr']}`\nWR `%{s1['winrate']}`",inline=True)
        e.add_field(name="Öne çıkan",value=ctx.author.mention if a>=b else member.mention,inline=True)
        e.add_field(name=f"{u2['game_name']}#{u2['tag_line']}",value=f"V-Score `{b}`\nK/D `{s2['kd']}`\nHS `%{s2['hs_rate']}`\nADR `{s2['adr']}`\nWR `%{s2['winrate']}`",inline=True)
        await ctx.send(embed=e)


async def setup(bot): await bot.add_cog(Stats(bot))
