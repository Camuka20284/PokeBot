import discord
from discord.ext import commands
from discord.ext import commands
import random
from database import conn, cursor
from logic import Pokemon, WizardPokemon as Wizard, FighterPokemon as Fighter

MAX_POKEMON = 10
HUNT_CATCH_CHANCE = 0.75
WINS_PER_HUNT = 3

# ── Veritabanı güncellemeleri ──────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trainer TEXT NOT NULL,
    hp INTEGER,
    power INTEGER,
    level INTEGER,
    exp INTEGER,
    pokemon_number INTEGER,
    class TEXT,
    name TEXT,
    is_main INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS hunt_stats (
    trainer TEXT PRIMARY KEY,
    win_count INTEGER DEFAULT 0,
    hunt_tokens INTEGER DEFAULT 0
)
""")
conn.commit()

# ── Yardımcı fonksiyonlar ──────────────────────────────────
def get_collection(trainer: str) -> list:
    cursor.execute("""
        SELECT id, name, hp, power, level, class, is_main
        FROM collection WHERE trainer=?
        ORDER BY (hp + power) / 2 DESC
    """, (trainer,))
    return cursor.fetchall()

def get_collection_count(trainer: str) -> int:
    cursor.execute("SELECT COUNT(*) FROM collection WHERE trainer=?", (trainer,))
    return cursor.fetchone()[0]

def get_main_pokemon(trainer: str):
    cursor.execute("SELECT * FROM collection WHERE trainer=? AND is_main=1", (trainer,))
    return cursor.fetchone()

def set_main_pokemon(trainer: str, pokemon_id: int):
    cursor.execute("UPDATE collection SET is_main=0 WHERE trainer=?", (trainer,))
    cursor.execute("UPDATE collection SET is_main=1 WHERE trainer=? AND id=?", (trainer, pokemon_id))
    conn.commit()

def remove_pokemon(trainer: str):
    """
    Aktif Pokémon'u hem pokemons tablosundan hem bellekten siler.
    Koleksiyonda başka Pokémon varsa bir sonrakini aktif yapar.
    """
    # pokemons tablosundan sil
    cursor.execute("DELETE FROM pokemons WHERE trainer=?", (trainer,))
    conn.commit()

    # Bellekten sil
    if trainer in Pokemon.pokemons:
        pokemon = Pokemon.pokemons[trainer]
        del Pokemon.pokemons[trainer]

    # Koleksiyonda başka Pokémon var mı?
    cursor.execute("""
        SELECT id, class, hp, power, level, exp, pokemon_number, name
        FROM collection WHERE trainer=? AND hp > 0
        ORDER BY (hp + power) / 2 DESC LIMIT 1
    """, (trainer,))
    row = cursor.fetchone()
    return row  # None ise koleksiyon boş

def add_kill_token(trainer: str):
    """Pokémon öldürünce direkt 1 hunt tokeni ver."""
    cursor.execute("""
        INSERT INTO hunt_stats (trainer, win_count, hunt_tokens)
        VALUES (?, 0, 1)
        ON CONFLICT(trainer) DO UPDATE SET hunt_tokens = hunt_tokens + 1
    """, (trainer,))
    conn.commit()

def add_to_collection(trainer: str, pokemon: Pokemon) -> int:
    """Koleksiyona ekler, otomatik main atar. Yeni ID döndürür."""
    is_main = 1 if get_collection_count(trainer) == 0 else 0
    cursor.execute("""
        INSERT INTO collection (trainer, hp, power, level, exp, pokemon_number, class, name, is_main)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (trainer, pokemon.hp, pokemon.power, pokemon.level, pokemon.exp,
          pokemon.pokemon_number, pokemon.__class__.__name__, pokemon.name or "?", is_main))
    conn.commit()
    return cursor.lastrowid

def get_hunt_stats(trainer: str) -> tuple[int, int]:
    """(win_count, hunt_tokens) döndürür."""
    cursor.execute("SELECT win_count, hunt_tokens FROM hunt_stats WHERE trainer=?", (trainer,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO hunt_stats (trainer) VALUES (?)", (trainer,))
        conn.commit()
        return 0, 0
    return row[0], row[1]

def add_win(trainer: str):
    """Galibiyet ekler, 3 galibiyette 1 hunt tokeni verir."""
    cursor.execute("""
        INSERT INTO hunt_stats (trainer, win_count, hunt_tokens)
        VALUES (?, 1, 0)
        ON CONFLICT(trainer) DO UPDATE SET win_count = win_count + 1
    """, (trainer,))
    conn.commit()
    wins, tokens = get_hunt_stats(trainer)
    if wins % WINS_PER_HUNT == 0:
        cursor.execute("UPDATE hunt_stats SET hunt_tokens = hunt_tokens + 1 WHERE trainer=?", (trainer,))
        conn.commit()
        return True  # token kazandı
    return False

def use_hunt_token(trainer: str) -> bool:
    """Token varsa kullanır, True döndürür."""
    _, tokens = get_hunt_stats(trainer)
    if tokens <= 0:
        return False
    cursor.execute("UPDATE hunt_stats SET hunt_tokens = hunt_tokens - 1 WHERE trainer=?", (trainer,))
    conn.commit()
    return True

# ── Komutları kaydet ───────────────────────────────────────
def register_collection_commands(bot: commands.Bot, sihirbaz: list, dövüşçü: list):

    @bot.command()
    async def collection(ctx, *, arg: str = ""):
        """
        !collection          → koleksiyonu listele
        !collection id=main  → o Pokémon'u main yap
        """
        trainer = ctx.author.name

        # Main atama: !collection id=main
        if "=main" in arg.lower():
            try:
                pokemon_id = int(arg.lower().replace("=main", "").strip())
            except ValueError:
                await ctx.send("Geçersiz format. Örnek: `!collection 3=main`")
                return
            row = cursor.execute(
                "SELECT id FROM collection WHERE trainer=? AND id=?", (trainer, pokemon_id)
            ).fetchone()
            if not row:
                await ctx.send(f"ID {pokemon_id} sana ait bir Pokémon değil!")
                return
            set_main_pokemon(trainer, pokemon_id)
            await ctx.send(f"✅ ID {pokemon_id} numaralı Pokémon artık senin main'in!")
            return

        # Koleksiyon listesi
        pokemons = get_collection(trainer)
        if not pokemons:
            await ctx.send("Koleksiyonun boş! `!go` veya `!hunt` ile Pokémon edin.")
            return

        wins, tokens = get_hunt_stats(trainer)

        embed = discord.Embed(
            title=f"📦 {ctx.author.display_name} koleksiyonu",
            description=f"Toplam: {len(pokemons)}/{MAX_POKEMON} | "
                        f"Galibiyetler: {wins} | Hunt tokeni: {tokens}",
            color=0x534AB7
        )

        for row in pokemons:
            pid, name, hp, power, level, cls, is_main = row
            score = (hp + power) / 2
            main_tag = " ⭐ MAIN" if is_main else ""
            class_tag = "🪄" if cls == "WizardPokemon" else "⚔️"
            embed.add_field(
                name=f"ID {pid} — {name.capitalize()} {class_tag}{main_tag}",
                value=f"HP: {hp} | Güç: {power} | Level: {level} | Skor: {score:.0f}",
                inline=False
            )

        await ctx.send(embed=embed)

    @bot.command()
    async def hunt(ctx):
        """!hunt → Pokémon avına çık (3 galibiyet = 1 hak)"""
        trainer = ctx.author.name

        # Kapasite kontrolü
        if get_collection_count(trainer) >= MAX_POKEMON:
            await ctx.send(f"Koleksiyonun dolu! Maksimum {MAX_POKEMON} Pokémon taşıyabilirsin.")
            return

        # Token kontrolü
        if not use_hunt_token(trainer):
            wins, tokens = get_hunt_stats(trainer)
            kalan = WINS_PER_HUNT - (wins % WINS_PER_HUNT)
            await ctx.send(
                f"🎯 Hunt hakkın yok! Daha {kalan} galibiyet kazan → 1 hunt hakkı."
            )
            return

        # Pokémon oluştur
        chance = random.randint(1, 2)
        if chance == 1:
            pokemon = Wizard(trainer + f"_hunt_{random.randint(1000,9999)}")
            class_label = "Sihirbaz 🪄"
            sihirbaz.append(pokemon)
        else:
            pokemon = Fighter(trainer + f"_hunt_{random.randint(1000,9999)}")
            class_label = "Dövüşçü ⚔️"
            dövüşçü.append(pokemon)

        await pokemon.get_name()

        # %75 yakalama şansı
        caught = random.random() < HUNT_CATCH_CHANCE

        if caught:
            new_id = add_to_collection(trainer, pokemon)
            is_first = get_collection_count(trainer) == 1

            embed = discord.Embed(
                title="🎉 Pokémon yakalandı!",
                color=0x1D9E75
            )
            embed.add_field(name="Pokémon", value=pokemon.name.capitalize(), inline=True)
            embed.add_field(name="Sınıf", value=class_label, inline=True)
            embed.add_field(name="ID", value=str(new_id), inline=True)
            embed.add_field(name="HP", value=str(pokemon.hp), inline=True)
            embed.add_field(name="Güç", value=str(pokemon.power), inline=True)
            if is_first:
                embed.set_footer(text="⭐ İlk Pokémon'un, otomatik main olarak atandı!")

            image_url = await pokemon.get_img()
            if image_url:
                embed.set_thumbnail(url=image_url)

            await ctx.send(embed=embed)
        else:
            await ctx.send(
                f"😔 **{pokemon.name.capitalize()}** kaçtı! Hunt hakkın harcandı."
            )