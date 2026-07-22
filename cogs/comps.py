import discord
from discord.ext import commands

class Comp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF

        # Dev Taktiksel Harita Veritabanı
        self.map_data = {
            "haven": {
                "name": "HAVEN (3 Alanlı Taktik Haritası)",
                "meta": "👑 Jett • Omen • Sova • Killjoy • Breach",
                "double_initiator": "⚡ Fade • Breach • Jett • Omen • Killjoy",
                "double_controller": "💨 Omen • Viper • Jett • Sova • Killjoy",
                "roles": (
                    "• **Duelist (Jett):** C Long ve A Long ilk kan baskısı.\n"
                    "• **Controller (Omen):** B ve C Garaj hakimiyeti için One-Way smoke'lar.\n"
                    "• **Initiator (Sova/Breach):** A Long ve Garaj alanlarını yetenekle temizleme.\n"
                    "• **Sentinel (Killjoy):** C Site ve B Garaj alanını tek başına kilitleme."
                ),
                "attack": "Garaj alanını kontrol etmek C ve B alanlarına baskıyı kolaylaştırır. A Long alanına Flash + Recon kombosuyla giriş yapın.",
                "defense": "3 site olduğu için Killjoy'u C alanında yalnız bırakıp 2-1-2 veya Garaj odaklı tutuş yapın.",
                "combo": "🔥 **Breach Fault Line + Jett Dash** (A Long hızlı giriş) / **Sova Recon + Omen Paranoia** (Garaj temizleme)"
            },
            "ascent": {
                "name": "ASCENT (Orta Alan Dominasyonu)",
                "meta": "👑 Jett • Omen • Sova • Killjoy • KAY/O",
                "double_initiator": "⚡ Sova • KAY/O • Jett • Omen • Cypher",
                "double_controller": "💨 Omen • Viper • Jett • Sova • Killjoy",
                "roles": (
                    "• **Duelist (Jett):** Mid kontrolü ve A Short/B Main Dash girişleri.\n"
                    "• **Initiator (Sova & KAY/O):** B Main dikey duvar arkası yetenekler ve Mid bilgi toplama.\n"
                    "• **Sentinel (Killjoy):** B Site kapı ve pencere tutuşu, A Tree trap yerleşimi."
                ),
                "attack": "Mid kontrolü almadan alanlara girmeyin. Mid Catwalk ve Mid Cubby kontrolü kapıları kapatmayı kolaylaştırır.",
                "defense": "A Tree ve B Market kapılarını erken kapatıp bilgi yetenekleriyle retake (yeniden alma) oynayın.",
                "combo": "🔥 **KAY/O Flash + Jett Entry** (A Short) / **Sova Dart + Omen Wall Bang** (B Main)"
            },
            "bind": {
                "name": "BIND (Işınlayıcı ve Dar Koridorlar)",
                "meta": "👑 Raze • Brimstone • Skye • Cypher • Viper",
                "double_initiator": "⚡ Skye • Fade • Raze • Brimstone • Viper",
                "double_controller": "💨 Brimstone • Viper • Raze • Skye • Cypher",
                "roles": (
                    "• **Duelist (Raze):** Hookah ve B Short alanlarına Satchel bombaları.\n"
                    "• **Controller (Brimstone/Viper):** TP çıkışları ve hızlı site kapatma smoke'ları.\n"
                    "• **Sentinel (Cypher):** B Long ve A Lamps kameralı kilit alanlar."
                ),
                "attack": "Işınlayıcıları kullanarak rakip rotasyonunu şaşırtın. Hookah kontrolü A ve B geçişi için şarttır.",
                "defense": "A Lamps ve B Long alanlarına erken yetenek bırakarak dar alandaki rakipleri cezalandırın.",
                "combo": "🔥 **Skye Flash + Raze Paint Shells** (Hookah Temizliği) / **Viper Molly + Cypher Trap** (B Site)"
            },
            "lotus": {
                "name": "LOTUS (Döner Kapılar ve 3 Bölge)",
                "meta": "👑 Raze • Omen • Fade • Killjoy • Viper",
                "double_initiator": "⚡ Breach • Fade • Raze • Omen • Killjoy",
                "double_controller": "💨 Omen • Astra • Raze • Breach • Killjoy",
                "roles": (
                    "• **Duelist (Raze):** A Rubble ve C Mound alanlarında alan daraltma.\n"
                    "• **Initiator (Fade/Breach):** Döner kapı arkası sarsıntı ve gölge yetenekleri.\n"
                    "• **Sentinel (Killjoy):** B Site ve C Site arasına gizli taret/alarm botu kurma."
                ),
                "attack": "A Rubble kontrolünü erken alıp döner kapı baskısı kurun. B alanını hızlı plant noktası olarak kullanın.",
                "defense": "C Mound ve A Main alanlarına agresif girip erken bilgi alın, dar alanlarda rotasyonu hızlı yapın.",
                "combo": "🔥 **Breach Stun + Raze Grenade** (A Rubble) / **Fade Haunt + Omen Paranoia** (C Site)"
            }
        }

    @commands.command(name="comp", aliases=["kadro", "kompozisyon"])
    async def comp(self, ctx, map_name: str = None):
        if not map_name:
            embed = discord.Embed(
                title="⚠️ EKSİK PARAMETRE!",
                description="Lütfen bir harita ismi belirtin!\n**Kullanım:** `v!comp [Harita İsmi]`\n**Örnek:** `v!comp haven` veya `v!comp ascent`",
                color=0xFF0055
            )
            await ctx.send(embed=embed)
            return

        key = map_name.lower().strip()
        data = self.map_data.get(key)

        # Eğer veritabanında özel detaylandırılmamış bir haritaysa genel detaylı şablon
        if not data:
            embed = discord.Embed(
                title=f"📋 AI STRATEJİ & KADRO REHBERİ | {map_name.upper()}",
                description="**V-TRACKER.GG Taktik Motoru Raporu**\n------------------------------------------------",
                color=self.V_CYAN
            )
            embed.add_field(name="👑 1. Standart Meta Kadro", value="`Jett` • `Omen` • `Sova` • `Killjoy` • `Viper`", inline=False)
            embed.add_field(name="⚡ 2. Çift Öncü Aggressive Kadro", value="`Fade` • `Breach` • `Raze` • `Omen` • `Killjoy`", inline=False)
            embed.add_field(name="💨 3. Çift Kontrolör Alan Baskı Kadrosu", value="`Omen` • `Viper` • `Jett` • `Skye` • `Cypher`", inline=False)
            embed.add_field(
                name="🎯 Taktiksel Rol Dağılımı",
                value="• **Duelist:** İlk kan alma ve alana Dash/Satchel ile alan açma.\n• **Controller:** Dar görüş açılarını kapatıp One-Way smoke kullanma.\n• **Initiator:** Görüş ve sarsıntı yetenekleriyle site arkasını temizleme.",
                inline=False
            )
            embed.set_footer(text="V-Tracker.gg • Takım Strateji Kurucusu • v5.3 Ultimate")
            await ctx.send(embed=embed)
            return

        # Haritaya Özel Devasa Zengin Embed
        embed = discord.Embed(
            title=f"📋 AI STRATEJİ & KADRO REHBERİ | {data['name']}",
            description="**V-TRACKER.GG Taktik Motoru ve Taktiksel Alan Raporu**\n------------------------------------------------",
            color=self.V_CYAN
        )

        embed.add_field(name="🥇 1. Standart PRO Meta Kadro", value=f"```{data['meta']}```", inline=False)
        embed.add_field(name="⚡ 2. Çift Öncü Aggressive Kadro", value=f"`{data['double_initiator']}`", inline=True)
        embed.add_field(name="💨 3. Çift Kontrolör Alan Baskı Kadrosu", value=f"`{data['double_controller']}`", inline=True)

        embed.add_field(name="🎭 Ajan Bazlı Görev & Pozisyon Dağılımı", value=data['roles'], inline=False)
        embed.add_field(name="⚔️ Saldırı (Attack) Taktik Planı", value=f"```{data['attack']}```", inline=False)
        embed.add_field(name="🛡️ Savunma (Defense) Taktik Planı", value=f"```{data['defense']}```", inline=False)
        embed.add_field(name="💥 Ölümcül Yetenek Komboları", value=data['combo'], inline=False)

        embed.set_footer(text="V-Tracker.gg • Takım Strateji Kurucusu • v5.3 Ultimate")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Comp(bot))