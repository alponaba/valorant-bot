# V-Tracker Rebuild 2.0

Bu paket, yüklenen eski Valorant Discord botunun temizlenmiş ve yeniden düzenlenmiş sürümüdür.

## Ana değişiklikler

- Tek Discord hesabı = tek Riot hesabı.
- Kayıt, Riot ID'nin API'de varlığını kontrol eder ve sabit PUUID kimliğine kilitler.
- Aynı Riot hesabı ikinci Discord hesabına kaydedilemez.
- Kullanıcı kendi kaydını silip başka hesaba geçemez. Sadece bot sahibi `registration_reset` ile istisna oluşturabilir.
- Riot oyuncu adı değişirse `sync` aynı PUUID üzerinden yeni adı günceller.
- Eski JSON karmaşası yerine SQLite kullanılır.
- Eski projedeki sabit API anahtarları kaldırıldı; bütün sırlar environment variable oldu.
- Kayıt ekranı buton/modal + profil önizleme + onay akışıyla yenilendi.
- Stats, son maç, kıyaslama, koç, V-Coin, profil özelleştirme, taktik, moderasyon ve sunucu araçları tek tasarım diline getirildi.

## Doğrulama ne kadar güçlü?

`register` akışı Riot ID'nin gerçekten var olduğunu Henrik API üzerinden doğrular ve PUUID'yi alır. Bu, başka isim yazarak rastgele/geçersiz kayıt açılmasını önler ve hesabı sabit PUUID'ye kilitler.

**Bu, resmî Riot Sign-On (RSO) sahiplik doğrulaması değildir.** Bot Riot şifresi istemez. Gerçek RSO entegrasyonu Riot tarafından onaylanmış ürün/client bilgileri gerektirir. Bu paket sahte bir "resmî OAuth" ekranı göstermemek için eski placeholder RSO kodunu kaldırır.

## Kurulum

1. Python 3.11+ kur.
2. `pip install -r requirements.txt`
3. Hosting panelinde `DISCORD_TOKEN` ve `HENRIK_API_KEY` environment variable olarak ekle.
4. Discord Developer Portal'da Message Content Intent ve Server Members Intent aç.
5. `python main.py`

## Kayıt akışı

- `/register` veya `v!register`
- Riot ID gir: `OyuncuAdi#TAG`
- Bot API'den hesabı bulur ve profil önizlemesi gösterir.
- `Evet, bu hesap benim` onayı verilir.
- Discord ID ve Riot PUUID kalıcı kilitlenir.
- Riot ID sonradan değişirse `/sync` kullanılır; başka hesap kaydı açılmaz.

## Bot sahibi için kayıt sıfırlama

`/registration_reset @kullanici sebep`

Bu komut yalnız Discord uygulamasının/botun sahibi tarafından kullanılabilir.

## Önemli güvenlik notu

Yüklenen eski projede kaynak içine yazılmış Henrik API anahtarları vardı. Bu yeni ZIP'e hiçbir anahtar taşınmadı. Eski anahtarları Henrik panelinden iptal edip yeni anahtar üretmen önerilir. `.git` klasörü de eski sırları geçmişte saklayabileceği için yeni pakete dahil edilmedi.


## 2.1 Manuel Riot hesap sahiplik doğrulaması

`v!register` artık yalnızca Riot profilinin API'de bulunmasını kayıt için yeterli saymaz. Kullanıcı doğrulama talebi oluşturur; admin kanıtı kontrol ettikten sonra `v!verify @kullanıcı` ile onaylar veya `v!rejectverify @kullanıcı neden` ile reddeder. Onaydan sonra Discord ID ile Riot PUUID kalıcı olarak eşleştirilir.

Önerilen Render değişkeni:

- `VERIFICATION_CHANNEL_ID`: doğrulama taleplerinin gönderileceği Discord kanal ID'si. Ayarlanmazsa talep veritabanında bekler ve admin komutla onaylayabilir.

Kanıt olarak Riot istemcisinde ilgili hesabın açık olduğunu gösteren ekran görüntüsü/kısa ekran kaydı kullanılabilir. Bot hiçbir zaman Riot şifresi veya giriş bilgisi istememelidir. Bu manuel yöntem resmi Riot RSO/OAuth değildir.
