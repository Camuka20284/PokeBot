import aiohttp
import random
from datetime import datetime, timedelta
from database import conn, cursor

# ── Ana Pokémon sınıfı ─────────────────────────────────────
class Pokemon:
    # Tüm aktif Pokémonları tutan sözlük {trainer_adı: Pokemon nesnesi}
    pokemons = {}

    def __init__(self, pokemon_trainer):
        self.pokemon_trainer = pokemon_trainer
        self.pokemon_number = random.randint(1, 151)  # 1. nesil rastgele Pokémon
        self.name = None                               # İsim PokéAPI'den çekilecek
        self.hp = random.randint(100, 200)             # Başlangıç HP
        self.power = random.randint(10, 30)            # Başlangıç güç
        self.level = 1
        self.exp = 0
        self.types = []                                # Pokémon tipleri (fire, water vb.)
        self.last_feed_time = datetime.now()           # Besleme cooldown takibi

        # Belleğe kaydet
        Pokemon.pokemons[pokemon_trainer] = self

        # Veritabanına kaydet
        cursor.execute("""
        INSERT OR REPLACE INTO pokemons 
        (trainer, hp, power, level, exp, pokemon_number)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (pokemon_trainer, self.hp, self.power, self.level, self.exp, self.pokemon_number))
        conn.commit()

    # ── Veritabanı güncelleme ──────────────────────────────
    def _save(self):
        """Mevcut durumu hem pokemons hem collection tablosuna yazar."""
        cursor.execute("""
        UPDATE pokemons
        SET hp=?, power=?, level=?, exp=?, pokemon_number=?
        WHERE trainer=?
        """, (self.hp, self.power, self.level, self.exp, self.pokemon_number, self.pokemon_trainer))

        # collection tablosunu da güncelle (aktif pokemonun satırı)
        cursor.execute("""
        UPDATE collection
        SET hp=?, power=?, level=?, exp=?
        WHERE trainer=? AND pokemon_number=? AND hp > 0
        """, (self.hp, self.power, self.level, self.exp, self.pokemon_trainer, self.pokemon_number))

        conn.commit()

    # ── PokéAPI istekleri ──────────────────────────────────
    async def get_name(self):
        """PokéAPI'den Pokémon ismini ve tiplerini çeker."""
        url = f'https://pokeapi.co/api/v2/pokemon/{self.pokemon_number}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.types = [t['type']['name'] for t in data['types']]
                    self.name = data['forms'][0]['name']
                    return self.name
                else:
                    # API çalışmazsa varsayılan isim
                    self.name = "Pikachu"
                    return self.name

    async def get_img(self):
        """PokéAPI'den Pokémon görsel URL'ini çeker."""
        url = f'https://pokeapi.co/api/v2/pokemon/{self.pokemon_number}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['sprites']['front_default']
                else:
                    return None

    # ── Bilgi ──────────────────────────────────────────────
    async def info(self):
        """Pokémon bilgilerini formatlanmış string olarak döndürür."""
        if not self.name:
            await self.get_name()
        types_str = ', '.join(self.types) if self.types else "Bilinmiyor"
        return (f"Pokémon: {self.name}\n"
                f"HP ❤️: {self.hp}\n"
                f"Güç ⚔️: {self.power}\n"
                f"Level 🎖️: {self.level}\n"
                f"Deneyim 🎯: {self.exp}\n"
                f"Tür ❓: {types_str}")

    # ── Besleme ────────────────────────────────────────────
    async def feed(self, feed_interval=60, hp_increase=10):
        """
        Pokémon'u besler, HP artırır.
        feed_interval: Kaç saniyede bir beslenebilir (varsayılan 60sn)
        hp_increase: Her beslemede ne kadar HP kazanır (varsayılan 10)
        """
        current_time = datetime.now()
        delta_time = timedelta(seconds=feed_interval)
        if (current_time - self.last_feed_time) > delta_time:
            self.hp += hp_increase
            self.last_feed_time = current_time
            self._save()
            return f"Pokémon'un sağlığı geri yüklendi. Mevcut sağlık: {self.hp}"
        else:
            # Kalan süreyi hesapla
            remaining = self.last_feed_time + delta_time - current_time
            secs = int(remaining.total_seconds())
            return f"Pokémonunuzu {secs} saniye sonra besleyebilirsiniz."

    # ── Eğitim ────────────────────────────────────────────
    async def train(self):
        """Pokémon'u eğitir: güç +5, level +1."""
        self.power += 5
        self.level += 1
        self._save()
        return f"{self.pokemon_trainer} Pokémon'unu eğitti 👨‍🏫. Güç +5 ({self.power}), Level {self.level}"

    # ── Saldırı ───────────────────────────────────────────
    async def attack(self, enemy):
        """
        Düşmana saldırır. Güç kadar hasar verir.
        Düşman HP'si sıfırlanırsa yenildi mesajı döner.
        """
        if enemy.hp > self.power:
            enemy.hp -= self.power
            enemy._save()
            return (f"Pokémon eğitmeni @{self.pokemon_trainer} @{enemy.pokemon_trainer}'ne saldırdı.\n"
                    f"@{enemy.pokemon_trainer}'nin sağlık durumu ❤️: {enemy.hp}")
        else:
            enemy.hp = 0
            enemy._save()
            return f"Pokémon eğitmeni @{self.pokemon_trainer} @{enemy.pokemon_trainer}'ni yendi 🏅!"


# ── Sihirbaz Pokémon sınıfı ────────────────────────────────
class WizardPokemon(Pokemon):
    """
    Sihirbaz tipi Pokémon.
    - Saldırı: Sabit 5 hasar ateş topu
    - Savunma: %40 tam hasar, %10 yarı hasar, %30 kaçış,
               %10 yarı geri yansıma, %9 tam geri yansıma, %1 çift geri yansıma
    - Besleme: Normal Pokémon'dan 2 kat fazla HP kazanır (+20)
    """

    async def attack(self, enemy):
        """Ateş topu: sabit 5 hasar."""
        fireball = 5
        enemy.hp -= fireball
        if enemy.hp < 0:
            enemy.hp = 0
        enemy._save()
        return (f"Sihirbaz Pokémon ateş topu fırlattı! 🔥 Hasar: {fireball}\n"
                f"@{enemy.pokemon_trainer}'nin sağlık durumu ❤️: {enemy.hp}")

    async def defend(self, attacker):
        """
        Saldırıya karşı rastgele savunma mekanizması.
        Zar atılır (1-100) ve sonuca göre farklı senaryolar devreye girer.
        """
        chance = random.randint(1, 100)
        msg = ""

        if chance <= 40:
            # %40 — tam hasar al
            self.hp -= attacker.power
            msg = f"Sihirbaz Pokémon saldırıya karşı koyamadı ve tam hasar aldı! -{attacker.power} HP"
        elif chance <= 50:
            # %10 — yarı hasar al
            half_damage = attacker.power // 2
            self.hp -= half_damage
            msg = f"Sihirbaz Pokémon saldırının yarısını aldı! -{half_damage} HP"
        elif chance <= 80:
            # %30 — saldırıdan kaç, hiç hasar alma
            msg = "Sihirbaz Pokémon saldırıdan kaçtı! Hiç hasar almadı!"
        elif chance <= 90:
            # %10 — yarı hasarı rakibe yansıt
            half_attack = attacker.power // 2
            attacker.hp -= half_attack
            msg = f"Sihirbaz Pokémon hasardan etkilenmedi ve saldırının yarısını geri yolladı! Rakip -{half_attack} HP"
        elif chance <= 99:
            # %9 — tam hasarı rakibe yansıt
            attacker.hp -= attacker.power
            msg = f"Sihirbaz Pokémon saldırıyı savuşturdu ve tam güç geri yolladı! Rakip -{attacker.power} HP"
        else:
            # %1 — çift hasar rakibe yansıt (kritik savunma)
            super_attack = attacker.power * 2
            attacker.hp -= super_attack
            msg = f"Sihirbaz Pokémon süper güç kullandı! Rakip -{super_attack} HP"

        # HP 0'ın altına düşmesin
        if self.hp < 0:
            self.hp = 0
        if attacker.hp < 0:
            attacker.hp = 0

        # Her iki tarafı da kaydet
        self._save()
        attacker._save()

        return (f"{msg}\n"
                f"@{self.pokemon_trainer} HP ❤️: {self.hp}\n"
                f"@{attacker.pokemon_trainer} HP ❤️: {attacker.hp}")

    async def feed(self):
        """Sihirbaz Pokémon her beslemede +20 HP kazanır."""
        return await super().feed(hp_increase=20)


# ── Dövüşçü Pokémon sınıfı ────────────────────────────────
class FighterPokemon(Pokemon):
    """
    Dövüşçü tipi Pokémon.
    - Saldırı: Her saldırıda 5-15 ekstra güç bonusu alır (geçici)
    - Besleme: 10 saniyede bir beslenebilir, +15 HP kazanır
    """

    def __init__(self, pokemon_trainer):
        super().__init__(pokemon_trainer)

    async def attack(self, enemy):
        """Süper saldırı: geçici güç bonusuyla saldırır."""
        super_guc = random.randint(5, 15)  # Geçici güç bonusu
        self.power += super_guc
        sonuc = await super().attack(enemy)
        self.power -= super_guc  # Saldırı sonrası bonus geri alınır
        return sonuc + f"\nDövüşçü Pokémon süper saldırı kullandı. Eklenen güç: {super_guc}"

    async def feed(self):
        """Dövüşçü Pokémon 10 saniyede bir beslenebilir, +15 HP kazanır."""
        return await super().feed(feed_interval=10, hp_increase=15)