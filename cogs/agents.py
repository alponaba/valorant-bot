import discord
from discord.ext import commands

class Agents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF

        self.agents_db = {
            "jett": {
                "role": "Duelist (Saldırı / Giriş)",
                "difficulty": "Yüksek (Mekanik & Refleks)",
                "playstyle": "Agresif giriş, ilk kan alma ve açı kırıp kaçma.",
                "skills": (
                    "• **Tailwind (E - Dash):** Peeking yaptıktan sonra anında kaçış veya smoke içine agresif giriş.\n"
                    "• **Cloudburst (C - Smoke):** Rapid entry için 2.5 saniyelik hızlı görüş kapatma.\n"
                    "• **Updraft (Q - Zıplama):** Beklenmedik yüksek açılardan (Off-angle) nişan alma.\n"
                    "• **Blade Storm (X - Ulti):** Hareket ederken %100 isabetli eco-round kurtarıcısı."
                ),
                "pro_tips": "Operator ile ateş ettikten hemen sonra C + E kombosu yaparak sıfır riskle görüş kapatıp kaçabilirsiniz."
            },
            "omen": {
                "role": "Controller (Alan Yönetimi)",
                "difficulty": "Orta (Harita Bilgisi & Akıl Oyunları)",
                "playstyle": "One-Way smoke'lar, dikey işınlanmalar ve harita kontrolü.",
                "skills": (
                    "• **Dark Cover (E - Smoke):** Haritanın her yerine sınırsız şarjlı görüş engeli.\n"
                    "• **Paranoia (Q - Körlük):** Duvar arkasından geniş alandaki rakipleri sağırlatıp kör etme.\n"
                    "• **Shrouded Step (C - Işınlanma):** Smoke içinden kutu üstüne şaşırtıcı geçişler.\n"
                    "• **From the Shadows (X - Ulti):** Spike kurtarma veya harita arkasına sızma."
                ),
                "pro_tips": "Paranoia attıktan hemen sonra C yeteneğiyle rakibin arkasına ışınlanarak sesiz yürüyüş tuzağı kurun."
            }
        }

    @commands.command(name="agents", aliases=["ajan", "ajanlar"])
    async def agents(self, ctx, agent_name: str = None):
        if not agent_name:
            embed = discord.Embed(
                title="🎭 V-TRACKER.GG | PRO AJAN & REHBER VERİTABANI",
                description="Lütfen detaylı rehberini görmek istediğiniz ajanı belirtin!\n**Kullanım:** `v!agents [Ajan İsmi]` (Örn: `v!agents jett` veya `v!agents omen`)",
                color=self.V_CYAN
            )
            await ctx.send(embed=embed)
            return

        key = agent_name.lower().strip()
        data = self.agents_db.get(key)

        embed = discord.Embed(
            title=f"🎭 DETAYLI AJAN REHBERİ | {agent_name.upper()}",
            description="**V-TRACKER.GG AI Ajan Analiz Protokolü**\n------------------------------------------------",
            color=self.V_CYAN
        )

        if data:
            embed.add_field(name="🏷️ Ajan Rolü", value=f"`{data['role']}`", inline=True)
            embed.add_field(name="⚡ Zorluk Seviyesi", value=f"`{data['difficulty']}`", inline=True)
            embed.add_field(name="🎯 Oynanış Tarzı", value=f"*{data['playstyle']}*", inline=False)
            embed.add_field(name="💥 Yetenek Seti & Taktiksel Kullanım", value=data['skills'], inline=False)
            embed.add_field(name="💡 Radiant Seviyesi İpucu", value=f"```text\n{data['pro_tips']}\n```", inline=False)
        else:
            embed.add_field(
                name="🎭 Genel Ajan Sınıf Tavsiyesi",
                value=(
                    "• **Duelists (Jett/Reyna/Raze):** İlk skor odaklı, giriş yapan mekanik oyuncular.\n"
                    "• **Controllers (Omen/Viper/Brim):** Görüş engelleyen ve oyun temposunu belirleyen oyuncular.\n"
                    "• **Initiators (Sova/Fade/Breach):** Bilgi toplayıp rakipleri açığa çıkaran taktiksel oyuncular.\n"
                    "• **Sentinels (Killjoy/Cypher):** Alan kilitleyen ve arka kanat (flank) tutan savunucular."
                ),
                inline=False
            )

        embed.set_footer(text="V-Tracker.gg • Ajan Uzmanı • v5.3 Ultimate")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Agents(bot))