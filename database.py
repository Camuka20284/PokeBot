import sqlite3

conn = sqlite3.connect("pokemon.db")
cursor = conn.cursor()

# ── Pokémon tablosu ────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS pokemons (
    trainer TEXT PRIMARY KEY,
    name TEXT,
    hp INTEGER,
    power INTEGER,
    level INTEGER,
    exp INTEGER,
    pokemon_number INTEGER,
    class TEXT
)
""")

# ── Koleksiyon tablosu ─────────────────────────────────────
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

# ── Hunt istatistikleri ────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS hunt_stats (
    trainer TEXT PRIMARY KEY,
    win_count INTEGER DEFAULT 0,
    hunt_tokens INTEGER DEFAULT 0
)
""")

# ── Moderasyon uyarıları ───────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    count INTEGER DEFAULT 0
)
""")

conn.commit()