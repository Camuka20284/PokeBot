import discord
from discord.ext import commands
from config import token, reve_api_key
from logic import Pokemon, WizardPokemon as Wizard, FighterPokemon as Fighter
from reve_api import ReveAPI, build_prompt
from moderation import check_message, add_warning, get_timeout_seconds, format_duration, register_mod_commands
from collection import register_collection_commands, add_to_collection, add_kill_token, remove_pokemon, get_collection_count
import random
import io
import aiohttp
import datetime
from database import cursor, conn


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
reve = ReveAPI(api_key=reve_api_key)

sihirbaz = []
dövüşçü = []

# ── BAŞLANGIÇ ──────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f'Giriş yapıldı: {bot.user.name}')
    cursor.execute("SELECT trainer, hp, power, level, exp, pokemon_number, class FROM pokemons")
    rows = cursor.fetchall()
    for row in rows:
        trainer, hp, power, level, exp, number, class_name = row
        if class_name == "WizardPokemon":
            pokemon = Wizard(trainer)
            sihirbaz.append(pokemon)
        elif class_name == "FighterPokemon":
            pokemon = Fighter(trainer)
            dövüşçü.append(pokemon)
        else:
            pokemon = Pokemon(trainer)
        pokemon.hp = hp
        pokemon.power = power
        pokemon.level = level
        pokemon.exp = exp
        pokemon.pokemon_number = number
    print(f"{len(rows)} Pokémon SQL'den yüklendi.")

# ── TEK on_message — moderasyon burada ────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    await bot.process_commands(message)

    if message.content.startswith('!'):
        return

    inappropriate, found_word = check_message(message.content)
    if not inappropriate:
        return

    try:
        await message.delete()
    except discord.Forbidden:
        pass

    user_id = str(message.author.id)
    username = message.author.display_name
    warn_count = add_warning(user_id, username)

    timeout_secs = get_timeout_seconds(warn_count)
    duration_str = format_duration(timeout_secs)

    try:
        await message.author.timeout(
            datetime.timedelta(seconds=timeout_secs),
            reason=f"Yasaklı kelime: {found_word}"
        )
        timeout_msg = f"🔇 {duration_str} susturuldu."
    except discord.Forbidden:
        timeout_msg = "(Susturma yetkisi yok, bot rolünü kontrol edin.)"
    except Exception as e:
        timeout_msg = f"(Susturma uygulanamadı: {e})"

    embed = discord.Embed(title="⚠️ Kural İhlali", color=0xE24B4A)
    embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
    embed.add_field(name="Sebep", value="Yasaklı kelime tespit edildi", inline=True)
    embed.add_field(name="Uyarı sayısı", value=f"{warn_count}. ihlal", inline=True)
    embed.add_field(name="Süre", value=timeout_msg, inline=False)
    embed.set_footer(text="Lütfen sunucu kurallarına uyun.")
    await message.channel.send(embed=embed)

# ── Yardımcı: ölüm sonrası sonraki Pokémon'u aktif et ─────
async def handle_death(ctx, dead_trainer: str, display_name: str):
    next_row = remove_pokemon(dead_trainer)
    if next_row:
        pid, cls, hp, power, level, exp, number, name = next_row
        if cls == "WizardPokemon":
            new_p = Wizard(dead_trainer)
            sihirbaz.append(new_p)
        else:
            new_p = Fighter(dead_trainer)
            dövüşçü.append(new_p)
        new_p.hp = hp
        new_p.power = power
        new_p.level = level
        new_p.exp = exp
        new_p.pokemon_number = number
        new_p.name = name
        await ctx.send(
            f"🔄 {display_name}'in yeni aktif Pokémon'u: **{name.capitalize()}** (HP: {hp})"
        )
    else:
        await ctx.send(
            f"😢 {display_name}'in artık hiç Pokémon'u kalmadı! "
            f"`!go` yazarak yeni bir Pokémon alabilir."
        )

# ── !go ────────────────────────────────────────────────────
@bot.command()
async def go(ctx):
    trainer = ctx.author.name

    # Koleksiyon doluysa ve bellekte aktif hp>0 pokémon varsa engelle
    if get_collection_count(trainer) > 0 and trainer in Pokemon.pokemons and Pokemon.pokemons[trainer].hp > 0:
        await ctx.send("Zaten aktif bir Pokémon'un var!")
        return

    # Bellekte kalıntı varsa temizle
    if trainer in Pokemon.pokemons:
        del Pokemon.pokemons[trainer]

    chance = random.randint(1, 2)
    if chance == 1:
        pokemon = Wizard(trainer)
        await ctx.send("Pokémon'unuz Sihirbaz! 🪄")
        sihirbaz.append(pokemon)
    else:
        pokemon = Fighter(trainer)
        await ctx.send("Pokémon'unuz Dövüşçü! ⚔️")
        dövüşçü.append(pokemon)

    await pokemon.get_name()
    await ctx.send(await pokemon.info())
    add_to_collection(trainer, pokemon)

    image_url = await pokemon.get_img()
    if image_url:
        embed = discord.Embed(title=f"{pokemon.name} — Orijinal Görsel")
        embed.set_image(url=image_url)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Pokémon görseli yüklenemedi.")

# ── !info ──────────────────────────────────────────────────
@bot.command()
async def info(ctx):
    trainer = ctx.author.name
    from collection import get_main_pokemon
    main_row = get_main_pokemon(trainer)

    if not main_row:
        await ctx.send("Henüz bir Pokémon'un yok! `!go` yaz.")
        return

    pid, _, hp, power, level, exp, pokemon_number, cls, name, is_main = main_row
    class_name = "Sihirbaz" if cls == "WizardPokemon" else "Dövüşçü" if cls == "FighterPokemon" else "Bilinmiyor"

    types_str = "Bilinmiyor"
    img_url = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_number}') as response:
                if response.status == 200:
                    data = await response.json()
                    types_str = ', '.join([t['type']['name'] for t in data['types']])
                    img_url = data['sprites']['front_default']
    except Exception:
        pass

    embed = discord.Embed(
        title=f"⭐ {name.capitalize()} — Main Pokémon",
        description=(
            f"Pokémon: {name}\n"
            f"HP ❤️: {hp}\n"
            f"Güç ⚔️: {power}\n"
            f"Level 🎖️: {level}\n"
            f"Deneyim 🎯: {exp}\n"
            f"Tür ❓: {types_str}\n"
            f"Sınıf: {class_name}"
        ),
        color=0x378ADD
    )
    if img_url:
        embed.set_thumbnail(url=img_url)
    await ctx.send(embed=embed)

# ── !wizard ────────────────────────────────────────────────
@bot.command()
async def wizard(ctx):
    if sihirbaz:
        await ctx.send("Sihirbaz Pokémon'lar 🪄:")
        for p in sihirbaz:
            await ctx.send(await p.info())
    else:
        await ctx.send("Henüz sihirbaz Pokémon yok!")

# ── !fighter ───────────────────────────────────────────────
@bot.command()
async def fighter(ctx):
    if dövüşçü:
        await ctx.send("Dövüşçü Pokémon'lar ⚔️:")
        for p in dövüşçü:
            await ctx.send(await p.info())
    else:
        await ctx.send("Henüz dövüşçü Pokémon yok!")

# ── !feed ──────────────────────────────────────────────────
@bot.command()
async def feed(ctx):
    trainer = ctx.author.name
    if trainer not in Pokemon.pokemons:
        await ctx.send("Henüz bir Pokémon'un yok! `!go` yaz.")
        return
    await ctx.send(await Pokemon.pokemons[trainer].feed())

# ── !train ─────────────────────────────────────────────────
@bot.command()
async def train(ctx):
    trainer = ctx.author.name
    if trainer not in Pokemon.pokemons:
        await ctx.send("Henüz bir Pokémon'un yok! `!go` yaz.")
        return
    await ctx.send(await Pokemon.pokemons[trainer].train())

# ── !attack ────────────────────────────────────────────────
@bot.command()
async def attack(ctx, target: discord.Member):
    trainer = ctx.author.name
    target_name = target.name

    if trainer not in Pokemon.pokemons or target_name not in Pokemon.pokemons:
        await ctx.send("Savaş için her iki tarafın da Pokémon sahibi olması gerekir!")
        return

    attacker = Pokemon.pokemons[trainer]
    enemy = Pokemon.pokemons[target_name]

    if attacker.hp <= 0:
        await ctx.send("Sağlık puanın 0, saldırı yapamazsın!")
        return

    if isinstance(enemy, Wizard):
        result = await enemy.defend(attacker)
    else:
        result = await attacker.attack(enemy)

    await ctx.send(result)

    # Düşman öldü mü?
    if enemy.hp <= 0:
        add_kill_token(trainer)
        await ctx.send(
            f"💀 {target.display_name}'in Pokémon'u yenildi! "
            f"🎯 {ctx.author.display_name} **1 hunt hakkı kazandı!**"
        )
        await handle_death(ctx, target_name, target.display_name)

    # Saldıranın Pokémon'u da öldü mü? (defend'den geri hasar)
    if attacker.hp <= 0:
        await handle_death(ctx, trainer, ctx.author.display_name)

# ── !release ───────────────────────────────────────────────
@bot.command()
async def release(ctx, pokemon_id: int):
    trainer = ctx.author.name

    row = cursor.execute(
        "SELECT id, name, is_main, pokemon_number FROM collection WHERE trainer=? AND id=?",
        (trainer, pokemon_id)
    ).fetchone()

    if not row:
        await ctx.send(f"ID {pokemon_id} sana ait bir Pokémon bulunamadı!")
        return

    pid, name, is_main, pokemon_number = row

    # Koleksiyondan sil
    cursor.execute("DELETE FROM collection WHERE id=?", (pokemon_id,))
    conn.commit()

    # Aktif Pokémon buysa bellekten ve pokemons tablosundan da sil
    if trainer in Pokemon.pokemons and Pokemon.pokemons[trainer].pokemon_number == pokemon_number:
        cursor.execute("DELETE FROM pokemons WHERE trainer=?", (trainer,))
        conn.commit()
        del Pokemon.pokemons[trainer]

    await ctx.send(f"🌿 **{name.capitalize()}** doğaya bırakıldı. Güle güle!")

    # Main'i bıraktıysa yeni main ata
    if is_main:
        new_main = cursor.execute(
            "SELECT id FROM collection WHERE trainer=? ORDER BY (hp+power)/2 DESC LIMIT 1",
            (trainer,)
        ).fetchone()
        if new_main:
            cursor.execute("UPDATE collection SET is_main=1 WHERE id=?", (new_main[0],))
            conn.commit()
            await ctx.send("⭐ Yeni main Pokémon otomatik atandı. `!info` ile görebilirsin.")
        else:
            await ctx.send("Koleksiyonun boşaldı! `!go` yazarak yeni bir Pokémon alabilirsin.")

# ── gizli ──────────────────────────────────────────────────
@bot.command()
async def best_poke(ctx):
    if ctx.author.name != "camuka2.0":
        return
    trainer = ctx.author.name
    if trainer not in Pokemon.pokemons:
        await ctx.send("Önce `!go` yaz.")
        return
    p = Pokemon.pokemons[trainer]
    p.hp = 99999
    p.power = 99999
    p._save()
    await ctx.send("⚡")

@bot.command()
async def hunt_token(ctx, amount: int):
    if ctx.author.name != "camuka2.0":
        return
    for _ in range(amount):
        add_kill_token(ctx.author.name)
    await ctx.send(f"⚡ {amount} hunt tokeni eklendi.")

# ── !aiart ─────────────────────────────────────────────────
@bot.command()
async def aiart(ctx, style: str = "anime"):
    trainer = ctx.author.name

    geçerli_stiller = ["anime", "cyberpunk", "watercolor", "realistic"]
    if style not in geçerli_stiller:
        await ctx.send(f"Geçersiz stil. Seçenekler: `{'`, `'.join(geçerli_stiller)}`")
        return

    # Main Pokémon'u collection'dan al
    from collection import get_main_pokemon
    main_row = get_main_pokemon(trainer)
    if not main_row:
        await ctx.send("Henüz bir Pokémon'un yok! `!go` yaz.")
        return

    pid, _, hp, power, level, exp, pokemon_number, cls, name, is_main = main_row

    # Geçici Pokemon nesnesi oluştur (sadece görsel için)
    if trainer in Pokemon.pokemons and Pokemon.pokemons[trainer].pokemon_number == pokemon_number:
        pokemon = Pokemon.pokemons[trainer]
    else:
        # Bellekte yoksa geçici nesne yap
        pokemon = Pokemon.__new__(Pokemon)
        pokemon.pokemon_trainer = trainer
        pokemon.pokemon_number = pokemon_number
        pokemon.name = name
        pokemon.types = []
        # Tipi PokéAPI'den çek
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_number}') as response:
                    if response.status == 200:
                        data = await response.json()
                        pokemon.types = [t['type']['name'] for t in data['types']]
        except Exception:
            pass

    await ctx.send(f"🎨 **{name.capitalize()}** için **{style}** stilinde görsel oluşturuluyor...")
    await send_ai_art(ctx, pokemon, style=style)

# ── Yardımcı: AI görsel gönder ─────────────────────────────
async def send_ai_art(ctx, pokemon: Pokemon, style: str = "anime"):
    if not pokemon.name:
        await pokemon.get_name()

    prompt = build_prompt(pokemon.name, pokemon.types, style)
    image_bytes = await reve.generate_image(prompt)

    if image_bytes:
        file = discord.File(io.BytesIO(image_bytes), filename="pokemon_ai.png")
        embed = discord.Embed(
            title=f"✨ {pokemon.name.capitalize()} — AI Görsel ({style})",
            description=f"*{prompt}*",
            color=0x7B2FBE
        )
        embed.set_image(url="attachment://pokemon_ai.png")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send("❌ AI görseli oluşturulamadı.")

# ── Başlat ─────────────────────────────────────────────────
async def main():
    register_mod_commands(bot)
    register_collection_commands(bot, sihirbaz, dövüşçü)
    await bot.start(token)

import asyncio
asyncio.run(main())