from __future__ import annotations

from discord.ext import commands

from response_variants import unique_variant
from theme import panel

AGENTS = {
    "jett": ("Duelist", "Agresif entry, ilk temas ve güvenli kaçış.", [
        "Dash'i ikinci düello için saklamak yerine ilk temastan canlı çıkacağın rota ile birlikte planla.",
        "Entry öncesi takımının flash/info zamanını bekle; dash tek başına alan açmaz, sadece riski yeniden konumlandırır.",
        "Aynı site girişinde her round aynı dash çizgisini kullanma; savunmanın crosshair hazırlığını bozacak iki alternatif giriş hazırla.",
    ]),
    "omen": ("Controller", "Esnek smoke, paranoia ve teleport ile tempo kontrolü.", [
        "Paranoia'yı takım girişinden hemen önce kullan; çok erken atılan paranoia savunmaya toparlanma süresi verir.",
        "İki smoke'u round başında tüketme; retake veya site sonrası için en az bir görüş kesme planı bırak.",
        "Teleport'u sadece kaçış değil, rakibin crosshair yönünü değiştiren ses baskısı olarak da kullan.",
    ]),
    "sova": ("Initiator", "Bilgi toplama ve duvar arkası baskı.", [
        "Recon'u ezber lineup olduğu için değil, takımın gerçekten gireceği bölgeyi açmak için zamanla.",
        "Drone sonrası takım mesafesini kontrol et; bilgi geldiğinde kimse trade mesafesinde değilse utility değeri boşa gider.",
        "Aynı recon noktasını arka arkaya tekrarlama; savunmanın kırma zamanını öğrendiği anda bilgi kalitesi düşer.",
    ]),
    "killjoy": ("Sentinel", "Site tutuşu, flank kontrolü ve post-plant.", [
        "Utility'yi tek noktaya yığmak yerine erken bilgi + geciktirme şeklinde iki katmana böl.",
        "Setup'ı her round birebir tekrar etme; rakibin ilk utility temizleme rotasını cezalandıracak varyasyon kullan.",
        "Post-plant için tüm utility'yi saklamak yerine round başında en az bir bilgi değeri üretmeye çalış.",
    ]),
    "raze": ("Duelist", "Dar alan temizleme ve patlayıcı entry.", [
        "Satchel hızını takımın flash/info penceresiyle eşleştir; tek başına hızlı girmek trade ihtimalini düşürür.",
        "Boom Bot'u sadece hasar için değil, crosshair'i aşağı çektirip ilk düelloyu kolaylaştırmak için kullan.",
        "Grenade'i alışkanlık noktasına değil, rakibin kaçış rotasını daraltacak ikinci bölgeye atmayı dene.",
    ]),
    "breach": ("Initiator", "Stun/flash ile duvar arkası baskı.", [
        "Yetenek sonrası kendi peek'inden önce takım arkadaşının çıkış zamanını düşün; Breach değeri senkronizasyondan gelir.",
        "Flash sayısını artırmak yerine rakibin kaçabileceği açıyı stun ile kapatıp tek düelloya zorla.",
        "Retake'te utility'yi aynı koridora yığma; bir yetenek görüşü, diğerini hareket alanını sınırlamak için kullan.",
    ]),
    "cypher": ("Sentinel", "Bilgi, flank ve trap kontrolü.", [
        "Trap'leri her round aynı yere koyma; rakibin utility temizleme alışkanlığını ikinci varyasyonla cezalandır.",
        "Camera'yı yalnız info için değil, rakibi crosshair çevirmeye zorlayacak zamanlamada kullan.",
        "Flank kontrolün varken gereksiz geri bakışları azalt; takımın ön taraftaki sayı avantajına daha hızlı katıl.",
    ]),
    "viper": ("Controller", "Uzun görüş kesme ve alan reddi.", [
        "Yakıtı round başında tüketme; retake veya post-plant için ikinci kullanım penceresi bırak.",
        "Wall'u sadece site girişini kapatmak için değil, rakibin rotasyon bilgisini geciktirmek için açılandır.",
        "Molly'yi alışkanlık post-plant noktasına saklamak yerine gerektiğinde erken alan kazanımı için kullan.",
    ]),
}

MAPS = {
    "haven": ("Jett • Omen • Sova • Killjoy • Breach", "Garaj kontrolü B/C baskısını kolaylaştırır; üç site nedeniyle rotasyon bilgisini erken topla."),
    "ascent": ("Jett • Omen • Sova • Killjoy • KAY/O", "Mid kontrolü Market/Tree rotasyonlarını ikiye böler; kapı kontrolü değerli."),
    "bind": ("Raze • Brimstone • Skye • Cypher • Viper", "Teleport tehdidini kullan; Hookah ve Lamps gibi dar alanları util ile temizle."),
    "lotus": ("Raze • Omen • Fade • Killjoy • Viper", "A Rubble ve C Mound erken bilgi noktalarıdır; döner kapılar tempo değiştirir."),
    "sunset": ("Raze • Omen • Sova • Cypher • Breach", "Mid kontrolü B Market ve A bağlantılarını etkiler; Cypher flank bilgisi kritik."),
}


class Tactical(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.hybrid_command(name="agents", aliases=["ajan", "ajanlar"], description="Ajan rolü ve kısa taktik rehberi.")
    async def agents(self, ctx, agent: str = None):
        if not agent:
            return await ctx.send(embed=panel("Ajan Rehberi", "Mevcut kısa rehberler: " + ", ".join(f"`{x}`" for x in AGENTS)))
        d = AGENTS.get(agent.lower())
        if not d:
            return await ctx.send(embed=panel("Genel Ajan Rehberi", "Duelist alan açar • Initiator bilgi/tempo üretir • Controller görüş yönetir • Sentinel alan ve flank kontrol eder."))
        tip = await unique_variant(ctx.author.id, f"agent:{agent.lower()}", d[2], salt=agent.lower())
        e = panel(f"{agent.title()} Rehberi", f"**Rol:** {d[0]}\n**Oyun tarzı:** {d[1]}")
        e.add_field(name="Bu kullanım için ipucu", value=tip, inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="comp", aliases=["kadro", "kompozisyon"], description="Harita için örnek takım kompozisyonu.")
    async def comp(self, ctx, map_name: str):
        d = MAPS.get(map_name.lower())
        if not d:
            return await ctx.send(embed=panel("Harita bulunamadı", "Mevcut: " + ", ".join(f"`{x}`" for x in MAPS)))
        e = panel(f"{map_name.title()} Kompozisyon", f"**Örnek kadro:** {d[0]}")
        e.add_field(name="Oyun planı", value=d[1], inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="counterstrat", aliases=["counter", "strat"], description="Rakip oyun tarzına karşı değişken strateji üretir.")
    async def counterstrat(self, ctx, style: str):
        s = style.lower()
        if any(x in s for x in ["rush", "hizli", "hızlı"]):
            kind = "rush"
            options = [
                "İlk 5–8 saniyede tüm utility'yi tüketme. İlk teması geciktir, ikinci dalgaya sakladığın smoke/stun ile rakibin trade zincirini kır.",
                "Rush'a karşı ilk hedef kill değil tempo kesmek. Dar girişte alan reddi kurup crossfire'a geri çekil; rotasyon bilgi geldikten sonra gelsin.",
                "Rakip sürekli hızlı giriyorsa bir round erken utility, sonraki round pasif crossfire kullan. Aynı savunma ritmini tekrarlama.",
                "Entry oyuncusunu durdurmaya odaklan; ikinci oyuncu trade mesafesini kaybettiğinde rush yapısı kendi kendine parçalanır.",
            ]
        elif any(x in s for x in ["operator", " op", "op "]):
            kind = "operator"
            options = [
                "Operator açısına kuru peek verme. Önce smoke/flash/drone ile crosshair'i yerinden oynat, sonra aynı koridoru iki farklı yükseklikten zorla.",
                "OP oyuncusunu killlemek zorunda değilsin; görüşünü kapatıp onu retake'e zorlamak çoğu roundda daha güvenli değer üretir.",
                "İlk temasta Operator görüldüyse aynı açıyı tekrar test etme. Harita kontrolünü başka koridordan alıp OP'yi rotasyona zorla.",
                "Jump-spot veya info utility ile atışını boşa çıkardıktan sonra tempo değiştir; reload/yeniden pozisyon penceresini kullan.",
            ]
        elif any(x in s for x in ["default", "yavas", "yavaş"]):
            kind = "default"
            options = [
                "Bilgi utility'sini zamana yay. Default'a karşı ilk 20 saniyede tüm kaynakları harcarsan 40 saniye bandında kör kalırsın.",
                "Tek başına agresif info arama; rakibin default düzenini bozmak için iki kişilik kontrollü alan geri alma planla.",
                "Default oynayan takım tekrar eden küçük temaslar arar. İlk bilgi sonrası hemen rotasyon yapmak yerine ikinci sinyali bekle.",
                "Harita alanını sessizce daralt; 45 saniye civarında hangi site baskısının gerçek olduğunu anlamaya çalış ve rotasyonu o zaman hızlandır.",
            ]
        else:
            kind = "generic"
            options = [
                "Rakibin ilk temas, rotasyon ve utility zamanını 3–4 round boyunca not et; karşı stratejiyi tek roundluk sonuca göre değiştirme.",
                "Önce tekrar eden davranışı bul: aynı entry, aynı lurk veya aynı retake rotası. Bir sonraki round sadece o örüntüyü cezalandır.",
                "Karşı stratejiyi kill hedefinden çıkarıp alan ve zaman hedefi olarak kur; rakibin güçlü olduğu düelloyu oynamamak da avantajdır.",
                "Bir round pasif bilgi, bir round kontrollü agresyon kullanarak rakibin okuma yapmasını zorlaştır; savunma ritmini sabitleme.",
            ]
        text = await unique_variant(ctx.author.id, f"counter:{kind}", options, salt=style)
        await ctx.send(embed=panel("Counter-Strat", text))


async def setup(bot): await bot.add_cog(Tactical(bot))
