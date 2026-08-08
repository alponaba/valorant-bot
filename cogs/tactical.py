import discord
from discord.ext import commands
from theme import info

AGENTS = {
    "jett": ("Duelist", "Agresif entry, ilk temas ve güvenli kaçış.", "Dash'i ikinci düello için değil; ilk temastan canlı çıkmak için planla."),
    "omen": ("Controller", "Esnek smoke, paranoia ve teleport ile tempo kontrolü.", "Paranoia'yı takım girişinden 1-2 saniye önce kullan; smoke'ları rotasyona sakla."),
    "sova": ("Initiator", "Bilgi toplama ve duvar arkası baskı.", "Recon'u ezber lineup yerine takımın gerçekten gireceği alana göre zamanla."),
    "killjoy": ("Sentinel", "Site tutuşu, flank kontrolü ve post-plant.", "Utility'yi tek noktaya yığmak yerine erken bilgi + geciktirme şeklinde böl."),
    "raze": ("Duelist", "Dar alan temizleme ve patlayıcı entry.", "Satchel hızını takım flash/info yeteneğiyle eşleştir."),
    "breach": ("Initiator", "Stun/flash ile duvar arkası baskı.", "Yetenek sonrası kendi peek'inden çok takım arkadaşının peek zamanını düşün."),
    "cypher": ("Sentinel", "Bilgi, flank ve trap kontrolü.", "Trap'leri her round aynı yere koyma; bilgi toplama amacıyla varyasyon kullan."),
    "viper": ("Controller", "Uzun görüş kesme ve alan reddi.", "Yakıtı round başında tüketme; retake/post-plant için rezerv bırak."),
}

MAPS = {
    "haven": ("Jett • Omen • Sova • Killjoy • Breach", "Garaj kontrolü B/C baskısını kolaylaştırır; 3 site nedeniyle rotasyon bilgisini erken topla."),
    "ascent": ("Jett • Omen • Sova • Killjoy • KAY/O", "Mid kontrolü Market/Tree rotasyonlarını ikiye böler; kapı kontrolü değerli."),
    "bind": ("Raze • Brimstone • Skye • Cypher • Viper", "Teleport tehdidini kullan; Hookah ve Lamps gibi dar alanları util ile temizle."),
    "lotus": ("Raze • Omen • Fade • Killjoy • Viper", "A Rubble ve C Mound erken bilgi noktalarıdır; döner kapılar tempo değiştirir."),
    "sunset": ("Raze • Omen • Sova • Cypher • Breach", "Mid kontrolü B Market ve A bağlantılarını etkiler; Cypher flank bilgisi kritik."),
}

class Tactical(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.hybrid_command(name="agents",aliases=["ajan","ajanlar"],description="Ajan rolü ve kısa taktik rehberi.")
    async def agents(self,ctx,agent: str=None):
        if not agent:
            return await ctx.send(embed=info("Ajan Rehberi","Mevcut kısa rehberler: "+", ".join(f"`{x}`" for x in AGENTS)))
        d=AGENTS.get(agent.lower())
        if not d: return await ctx.send(embed=info("Genel Ajan Rehberi","Duelist: alan açar • Initiator: bilgi/tempo • Controller: görüş yönetir • Sentinel: alan ve flank kontrol eder."))
        e=info(f"{agent.title()} Rehberi",f"**Rol:** {d[0]}\n**Oyun tarzı:** {d[1]}")
        e.add_field(name="Pratik ipucu",value=d[2],inline=False); await ctx.send(embed=e)
    @commands.hybrid_command(name="comp",aliases=["kadro","kompozisyon"],description="Harita için örnek takım kompozisyonu.")
    async def comp(self,ctx,map_name: str):
        d=MAPS.get(map_name.lower());
        if not d: return await ctx.send(embed=info("Harita bulunamadı","Mevcut: "+", ".join(f"`{x}`" for x in MAPS)))
        e=info(f"{map_name.title()} • Kompozisyon",f"**Örnek kadro:** {d[0]}"); e.add_field(name="Oyun planı",value=d[1],inline=False); await ctx.send(embed=e)
    @commands.hybrid_command(name="counterstrat",aliases=["counter","strat"],description="Rakip oyun tarzına karşı kısa strateji üretir.")
    async def counterstrat(self,ctx,style: str):
        s=style.lower();
        if any(x in s for x in ["rush","hizli","hızlı"]): text="Erken util harcayıp ölmek yerine ilk teması geciktir, crossfire kur ve rotasyonu bilgi geldikten sonra yap."
        elif any(x in s for x in ["operator","op"]): text="Kuru peek yerine flash/drone/smoke ile açıyı kapat; aynı uzun koridoru tekrar zorlama."
        elif any(x in s for x in ["default","yavas","yavaş"]): text="Bilgi util'ini zamana yay; tek başına agresif info aramak yerine alanı daraltıp 40–50 saniye bandında karar ver."
        else: text="Rakibin tekrar eden ilk temasını, rotasyon zamanını ve util kullanımını gözle; karşı stratejiyi tek bir round değil 3–4 round örüntüsüne göre kur."
        await ctx.send(embed=info("Counter-Strat",text))

async def setup(bot): await bot.add_cog(Tactical(bot))
