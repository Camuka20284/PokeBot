import discord
from discord.ext import commands
import re
import datetime
from database import conn, cursor
from config import BANNED_WORDS

# ── Regex pattern — config'den gelen listeden oluşturulur ──
def _build_pattern():
    escaped = [re.escape(w) for w in BANNED_WORDS]
    return re.compile("|".join(escaped), re.IGNORECASE)

PATTERN = _build_pattern()

def check_message(text: str) -> tuple[bool, str]:
    """
    Mesajı kontrol eder.
    (uygunsuz_mu: bool, bulunan_kelime: str) döndürür.
    """
    # Boşlukları ve özel karakterleri temizle (l33tspeak gibi hileleri yakala)
    cleaned = text.lower()
    cleaned = cleaned.replace("@", "a").replace("0", "o").replace("3", "e").replace("1", "i")
    
    match = PATTERN.search(cleaned)
    if match:
        return True, match.group()
    return False, ""

# ── Timeout süresi hesaplama ───────────────────────────────
def get_timeout_seconds(warn_count: int) -> int:
    if warn_count < 5:
        return 60
    elif warn_count < 10:
        return 3600
    elif warn_count < 20:
        return 86400
    else:
        return 172800

def format_duration(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60} dakika"
    elif seconds < 86400:
        return f"{seconds // 3600} saat"
    else:
        return f"{seconds // 86400} gün"

# ── Uyarı kaydet / güncelle ────────────────────────────────
def add_warning(user_id: str, username: str) -> int:
    cursor.execute("""
        INSERT INTO warnings (user_id, username, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET count = count + 1, username = ?
    """, (user_id, username, username))
    conn.commit()
    cursor.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 1

def get_warning_count(user_id: str) -> int:
    cursor.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

# ── Moderasyon komutları ───────────────────────────────────
def register_mod_commands(bot: commands.Bot):

    @bot.command()
    @commands.has_permissions(manage_messages=True)
    async def warnings(ctx, member: discord.Member):
        count = get_warning_count(str(member.id))
        await ctx.send(f"📋 {member.display_name} → **{count}** uyarı")

    @bot.command()
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(ctx, member: discord.Member):
        cursor.execute("UPDATE warnings SET count = 0 WHERE user_id = ?", (str(member.id),))
        conn.commit()
        await ctx.send(f"✅ {member.display_name} uyarıları sıfırlandı.")