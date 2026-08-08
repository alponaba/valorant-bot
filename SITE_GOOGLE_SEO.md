# V-Tracker Website + Google Search Setup

Bu paket, mevcut Flask bot servisinin içine çok sayfalı V-Tracker sitesini ekler.

## Yeni sayfalar
- `/` — ana ürün sayfası
- `/commands` — 56 komutluk aranabilir komut kütüphanesi
- `/status` — canlı health durum ekranı
- `/privacy` — veri/gizlilik özeti
- `/robots.txt` — crawler kuralları
- `/sitemap.xml` — Google/Bing için sitemap
- `/manifest.webmanifest` — web uygulama manifesti
- `/.well-known/security.txt` — güvenlik politikası yönlendirmesi

## Render environment variables
Mevcut değişkenlerine ek olarak:

```env
PUBLIC_SITE_URL=https://valorant-bot-x6tv.onrender.com
GOOGLE_SITE_VERIFICATION=
DISCORD_BOT_INVITE_URL=
SUPPORT_SERVER_URL=
```

`PUBLIC_SITE_URL` aynı Render adresinde kalacaksan yukarıdaki değer olabilir. Daha sonra özel domain alırsan bunu yeni domain ile değiştir.

## Google Search Console'a ekleme
1. Yeni site sürümünü Render'a deploy et.
2. Şunların açıldığını kontrol et:
   - `https://valorant-bot-x6tv.onrender.com/`
   - `https://valorant-bot-x6tv.onrender.com/commands`
   - `https://valorant-bot-x6tv.onrender.com/robots.txt`
   - `https://valorant-bot-x6tv.onrender.com/sitemap.xml`
3. Google Search Console'u aç.
4. Onrender alt alan adı için **URL-prefix** property kullan:
   `https://valorant-bot-x6tv.onrender.com/`
5. Doğrulama yönteminde HTML meta tag seçebilirsin.
6. Google'ın verdiği meta tag içindeki yalnızca `content="..."` değerini kopyala.
7. Render → Environment bölümünde `GOOGLE_SITE_VERIFICATION` değerine bunu yaz ve yeniden deploy et.
8. Search Console'a dön ve Verify yap.
9. Search Console → Sitemaps → `sitemap.xml` gönder.
10. URL Inspection ile önce ana sayfayı, sonra `/commands` sayfasını kontrol et ve gerekirse Request Indexing kullan.
11. Bir süre sonra Google'da şu sorguyla kontrol edebilirsin:
   `site:valorant-bot-x6tv.onrender.com`

Google crawling/indexing süresi garanti değildir. Sitemap Google'ın URL'leri keşfetmesine yardımcı olur ama indeks veya ranking garantisi değildir.

## Daha iyi sıralama için
- Mümkünse ileride kısa bir özel domain kullan (örn. `vtracker.gg` benzeri uygun ve müsait bir alan adı).
- Discord sunucusu, GitHub README ve sosyal profillerden siteye doğal bağlantı ver.
- Ana sayfada gerçek ve güncel özellik metinleri bulunsun.
- Komut sayfasını güncel tut.
- Yeni büyük sürümlerde bir changelog / updates sayfası eklemek yararlı olur.
- Mobil performansı koru; ağır video ve gereksiz üçüncü taraf script ekleme.
- Başlık/description'ları sayfaya özel tut.
- Sahte review/rating structured-data ekleme.

## Site tasarım notları
Tasarım V-Tracker için özgün tutuldu: koyu arka plan, turkuaz ana vurgu ve açık sarı ikincil vurgu. Harici UI framework veya CDN gerektirmediği için hızlı yüklenir.
