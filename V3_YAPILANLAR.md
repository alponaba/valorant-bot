# V-Tracker 3.0 – Yapılanlar

## Ana yükseltmeler
- Stats komutu artık dashboard tarzı ve butonlu.
- Tema turkuaz + açık sarı tona çekildi.
- V-Score, performans segmentleri, achievement özeti eklendi.
- Match Card ve gelişmiş compare/coach ekranları eklendi.
- Help komutu butonlu yardım merkezine dönüştürüldü.

## Güvenlik / koruma
- Global user + guild anti-spam limiti eklendi.
- API circuit breaker eklendi.
- Banner URL için whitelist ve HTTPS kontrolü eklendi.
- Mention injection temizleme eklendi.
- Verification için verifier role / manage_guild kontrolü eklendi.
- Moderasyonda role hierarchy kontrolü eklendi.
- Admin audit log tablosu ve komutu eklendi.

## Veri tarafı
- Daily / weekly claim artık daha güvenli atomik akışla çalışıyor.
- Shop purchase atomik hale getirildi.
- Health endpoint artık API ve uptime bilgisini de döndürüyor.

## Yeni ortam değişkenleri
- VERIFIER_ROLE_ID
- ADMIN_LOG_CHANNEL_ID
- TRUSTED_IMAGE_HOSTS
- GLOBAL_USER_RATE
- GLOBAL_USER_WINDOW
- GLOBAL_GUILD_RATE
- GLOBAL_GUILD_WINDOW
- API_FAIL_OPEN_COUNT
- API_COOLDOWN_SECONDS
