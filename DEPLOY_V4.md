# V-Tracker 4.0 Deploy

1. Eski proje klasörünün yedeğini al.
2. Bu ZIP'in içindeki `VTracker_Rebuild` klasörünü eski bot klasörünün yerine koy.
3. Eski production SQLite verisini koruyacaksan eski `data/vtracker.sqlite3` dosyanı yeni klasörde aynı yere kopyala. Yeni V4 tabloları otomatik oluşturulur.
4. `pip install -r requirements.txt`
5. Hosting environment variables alanında en az `DISCORD_TOKEN` değerini ayarla; Henrik hesabın gerekiyorsa `HENRIK_API_KEY` ekle.
6. Botu bir kez başlat.
7. Discord'da `v!setup` çalıştır. Oluşan kanal ve rollerden ID'leri al.
8. Hosting'e `VERIFICATION_CHANNEL_ID`, `VERIFIER_ROLE_ID`, `TRACKER_CHANNEL_ID`, `AUTOMOD_LOG_CHANNEL_ID`, `QUARANTINE_ROLE_ID` ekle.
9. Botu yeniden başlat.
10. `v!status`, `v!help`, `v!register`, `v!stats`, `v!modpanel` ile ilk kontrolü yap.

## Önemli
- Otomatik takip ilk taramayı baseline kabul eder; eski maçı yeni maç diye duyurmaz.
- AutoMod otomatik ban atmaz. Yüksek riskte mesaj silme + timeout/karantina kullanır.
- `BLOCK_INVITES=false` varsayılandır. Tüm Discord invite linklerini engellemek istiyorsan `true` yap.
- Kalıcı disk olmayan hosting kullanıyorsan `DATABASE_PATH` kalıcı volume/disk içine verilmelidir.
