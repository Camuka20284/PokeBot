# Pokémon Discord Botu 🎮
Pokémon yakalamak, savaştırmak ve koleksiyon oluşturmak için Discord botu.

Kurulum
bashpip install discord.py aiohttp

config.py dosyasına aşağıdakileri ekleyin:

pythontoken = "DISCORD_TOKEN"

reve_api_key = "REVE_API_KEY"

Botu başlatın:
bashpython bot.py

Komutlar
Temel Komutlar
KomutAçıklama:

!go
Yeni bir Pokémon oluşturur. Sihirbaz 🪄 veya Dövüşçü ⚔️ rastgele gelir.

!info
Main Pokémon'unun bilgilerini gösterir (HP, Güç, Level, Tür, Sınıf).

!feed
Pokémon'u besler, HP artar. 60 saniyede bir kullanılabilir.

!train
Pokémon'u eğitir. Güç +5, Level +1 artar.

Savaş
KomutAçıklama:

!attack @hedefHedef oyuncunun Pokémon'una saldırır. Hedef Sihirbaz ise savunma mekanizması devreye girer. Düşman ölürse 1 hunt tokeni kazanırsın.

Koleksiyon
KomutAçıklama:
!collection
Tüm Pokémon'larını (HP+Güç)/2 skoruna göre listeler. Main ⭐ ile işaretlenir.

!collection [id]=main
Belirtilen Pokémon'u main yapar. Örnek: !collection 3=main

!release[id]
Pokémon'u doğaya bırakır. Main bırakılırsa en güçlüsü otomatik main olur.

Hunt Sistemi
KomutAçıklama:
!hunt
Pokémon avına çıkar. %75 yakalama şansı. Maks. 10 Pokémon taşınabilir. Her öldürülen Pokémon → 1 hunt tokeni kazanılır.

AI Görsel
KomutAçıklama:
!aiart anime
Anime stilinde AI görsel.

!aiart cyberpunk
Cyberpunk stilinde AI görsel.

!aiart watercolor
Suluboya stilinde AI görsel.

!aiart realistic
Gerçekçi stilinde AI görsel.

Moderasyon (Yönetici)
KomutAçıklama:

!warnings @kullanıcı
Kullanıcının kaç kural ihlali yaptığını gösterir.

!clearwarnings@kullanıcı
Kullanıcının uyarılarını sıfırlar.


Susturma süresi:

1–4 ihlal → 1 dakika

5–9 ihlal → 1 saat

10–19 ihlal → 1 gün

20+ ihlal → 2 gün




Pokémon Sınıfları

Sihirbaz 🪄

Saldırı: Sabit 5 hasar ateş topu

Savunma: Rastgele savunma mekanizması

%40 → Tam hasar al

%10 → Yarı hasar al

%30 → Kaçış (0 hasar)

%10 → Yarı hasarı geri yansıt

%9 → Tam hasarı geri yansıt

%1 → Çift hasar geri yansıt


Besleme: +20 HP

Dövüşçü ⚔️

Saldırı: Her saldırıda 5–15 ekstra geçici güç bonusu

Besleme: 10 saniyede bir, +15 HP



Dosya Yapısı
pokemon_bot/
├── bot.py          # Ana bot dosyası, tüm komutlar

├── logic.py        # Pokémon sınıfları

├── database.py     # SQLite bağlantısı ve tablolar

├── reve_api.py     # Reve AI görsel üretimi

├── moderation.py   # Moderasyon sistemi

├── collection.py   # Koleksiyon ve hunt sistemi

└── config.py       # Token ve API anahtarları
