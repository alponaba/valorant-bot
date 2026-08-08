# V-Tracker 4.0

V-Tracker; Valorant oyuncu analizi, otomatik rank/maç takibi, topluluk araçları, V-Coin ekonomisi ve Discord güvenlik/moderasyon sistemini tek botta birleştirir.

## Öne çıkan sistemler

### Oyuncu Intelligence
- Butonlu Player Hub (`stats`, `profile`, `hub`)
- V-Score (0–1000)
- Player DNA: Aim, Impact, Survival, Consistency, Clutch
- Tilt risk skoru ve form analizi
- Tekrarsız kişisel koçluk; önceki koç mesajları SQLite'ta tutulur
- Son maç kartı, kişisel rekorlar, performans trendi
- Ajan/harita/weapon intelligence
- Daily / Weekly report, streak ve weekly growth leaderboard

### Otomasyon
- Rank + RR değişim takibi
- Yeni maç algılama
- Rank rolü otomatik senkronizasyonu
- Kişisel rekor kaydı/bildirimi
- İlk otomasyon taraması sessiz baseline'dır; deploy olur olmaz eski maçı yeni maç diye spamlamaz
- Snapshot DB büyümesini azaltmak için yalnız değişiklikte veya 6 saatte bir sağlık snapshot'ı
- Bildirim tercihleri (`notifications`)

### Topluluk
- Rival / Rival Board
- Duo Compatibility
- Friend Card
- LFG ilanı + butonla katılım
- V-Coin, mağaza, profil kozmetiği, leaderboard, görevler

### Güvenlik
- Global kullanıcı/sunucu komut rate limit
- Henrik API circuit breaker + cache
- Anti-raid join burst algılama
- Yeni Discord hesabı risk skoru
- V-Tracker Quarantine rolü
- Mass mention koruması
- Tekrarlanan mesaj fingerprint spam tespiti
- Scam/phishing kalıp filtresi
- İsteğe bağlı Discord invite filtresi
- Mention injection temizleme
- Banner HTTPS + trusted host whitelist
- Moderasyon rol hiyerarşisi
- Warn escalation: 3 uyarı -> 10 dk, 5+ uyarı -> 1 saat timeout
- Admin audit log

## Riot hesap doğrulaması

Bot sahte Riot OAuth/RSO göstermez. `register` Riot hesabını API'den bulur; kullanıcı sahiplik doğrulama talebi oluşturur ve yetkili ekran görüntüsü/kısa kayıt gibi kanıtı manuel inceler. Şifre, 2FA veya giriş bilgisi istenmez. Onay sonrası Discord ID ile Riot PUUID kalıcı eşleştirilir.

## Kurulum

1. Python 3.11+ kur.
2. `pip install -r requirements.txt`
3. `.env.example` içindeki değerleri hosting panelinin environment variables bölümüne gir.
4. Discord Developer Portal'da **Message Content Intent** ve **Server Members Intent** aç.
5. Botu başlat: `python main.py`
6. Sunucuda `v!setup` çalıştır.
7. Oluşan kanal/rol ID'lerini hosting environment variables alanına ekle ve botu yeniden başlat.

## Minimum gerekli env

- `DISCORD_TOKEN`
- `HENRIK_API_KEY` (Henrik kullanım planına göre)

Otomasyon için önerilen:
- `TRACKER_CHANNEL_ID`
- `VERIFICATION_CHANNEL_ID`
- `VERIFIER_ROLE_ID`
- `AUTOMOD_LOG_CHANNEL_ID`
- `QUARANTINE_ROLE_ID`

## Veri

Varsayılan DB: `data/vtracker.sqlite3`

Production host ephemeral filesystem kullanıyorsa `DATABASE_PATH` kalıcı diske yönlendirilmelidir. Discord ↔ Riot PUUID kilidi, ekonomi, audit ve snapshot geçmişi bu veritabanındadır.

## Gizlilik

- Token/API key kaynak dosyalara yazılmaz.
- PUUID Discord mesajlarında maskelenir.
- Kanıt sürecinde Riot şifresi veya 2FA bilgisi istenmez.
- Kullanıcı kaynaklı mention'lar sanitize edilir.

## Web sitesi

Aynı Flask servisi V-Tracker'ın public ürün sitesini de sunar:

- `/` ana sayfa
- `/commands` aranabilir 56 komut
- `/status` canlı durum ekranı
- `/privacy` gizlilik özeti
- `/sitemap.xml` ve `/robots.txt` SEO uçları

Google Search Console kurulumu için `SITE_GOOGLE_SEO.md` dosyasına bak.
