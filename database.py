import os
import aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH, MAX_DB_SIZE_MB


_save_counter = 0


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        INTEGER PRIMARY KEY,
            username       TEXT,
            first_name     TEXT,
            pro_until      TEXT,
            total_paid     INTEGER DEFAULT 0,
            referrer_id    INTEGER,
            ref_bonus_paid INTEGER DEFAULT 0,
            created_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            text TEXT,
            date TEXT NOT NULL,
            source_chat_id INTEGER,
            source_type TEXT,
            author_id INTEGER,
            author_name TEXT,
            UNIQUE(user_id, message_id, source_chat_id)
        );

        CREATE TABLE IF NOT EXISTS promos (
            code         TEXT PRIMARY KEY,
            plan_payload TEXT NOT NULL,
            discount     INTEGER NOT NULL,
            max_uses     INTEGER DEFAULT 0,
            used_count   INTEGER DEFAULT 0,
            created_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS promo_uses (
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            used_at TEXT,
            PRIMARY KEY (code, user_id)
        );

        CREATE TABLE IF NOT EXISTS linked_chats (
            chat_id   INTEGER PRIMARY KEY,
            owner_id  INTEGER NOT NULL,
            title     TEXT,
            linked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS business_links (
            connection_id TEXT PRIMARY KEY,
            owner_id      INTEGER NOT NULL,
            linked_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS gifts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id   INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            days       INTEGER NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_payment_charge_id TEXT UNIQUE NOT NULL,
            amount INTEGER NOT NULL,
            payload TEXT,
            date TEXT NOT NULL,
            refunded INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
        CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referrer_id);
        CREATE INDEX IF NOT EXISTS idx_gifts_user ON gifts(user_id);
        CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
        CREATE INDEX IF NOT EXISTS idx_payments_charge ON payments(telegram_payment_charge_id);
        """)
        await db.commit()


# ---------------- CLEANUP ----------------
async def maybe_cleanup():
    try:
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    except OSError:
        return
    if size_mb < MAX_DB_SIZE_MB:
        return

    print(f"[cleanup] БД {size_mb:.1f} MB > {MAX_DB_SIZE_MB} MB — чистим старые...", flush=True)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM messages")
        (total,) = await cur.fetchone()
        if total == 0:
            return

        delete_count = max(1000, total // 10)

        cur = await db.execute(
            "SELECT user_id FROM users WHERE pro_until > ?",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        pro_ids = [r[0] for r in await cur.fetchall()]

        # Сначала соберём пути к медиа, которые будем удалять
        media_paths = []
        if pro_ids:
            placeholders = ",".join("?" * len(pro_ids))
            cur = await db.execute(
                f"""SELECT text FROM messages
                    WHERE user_id NOT IN ({placeholders})
                    AND text LIKE '[%:%]'
                    ORDER BY id ASC LIMIT ?""",
                (*pro_ids, delete_count),
            )
            media_paths = [r[0] for r in await cur.fetchall()]
        else:
            cur = await db.execute(
                """SELECT text FROM messages
                   WHERE text LIKE '[%:%]'
                   ORDER BY id ASC LIMIT ?""",
                (delete_count,),
            )
            media_paths = [r[0] for r in await cur.fetchall()]

        if pro_ids:
            placeholders = ",".join("?" * len(pro_ids))
            await db.execute(
                f"""DELETE FROM messages WHERE id IN (
                    SELECT id FROM messages
                    WHERE user_id NOT IN ({placeholders})
                    ORDER BY id ASC LIMIT ?
                )""",
                (*pro_ids, delete_count),
            )
        else:
            await db.execute(
                "DELETE FROM messages WHERE id IN ("
                "SELECT id FROM messages ORDER BY id ASC LIMIT ?)",
                (delete_count,),
            )
        await db.commit()
        await db.execute("VACUUM")
        await db.commit()

    # Удаляем файлы медиа
    deleted_files = 0
    for path in media_paths:
        try:
            inner = path.strip("[]")
            _, _, fpath = inner.partition(":")
            if fpath and os.path.exists(fpath):
                os.remove(fpath)
                deleted_files += 1
        except Exception:
            pass

    new_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(
        f"[cleanup] Удалено {delete_count} сообщений и {deleted_files} файлов. "
        f"БД теперь {new_size:.1f} MB",
        flush=True,
    )


async def _maybe_cleanup():
    global _save_counter
    _save_counter += 1
    if _save_counter % 100 != 0:
        return
    await maybe_cleanup()


# ---------------- USERS ----------------
async def upsert_user(user_id: int, username: str | None, first_name: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name,
              datetime.now().isoformat(timespec="seconds")))
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()


async def is_pro(user_id: int) -> bool:
    u = await get_user(user_id)
    if not u or not u[3]:
        return False
    return datetime.fromisoformat(u[3]) > datetime.now()


async def grant_pro(user_id: int, days: int, add_paid: int = 0):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT pro_until FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        base = now
        if row and row[0]:
            old = datetime.fromisoformat(row[0])
            if old > now:
                base = old
        new_until = (base + timedelta(days=days)).isoformat(timespec="seconds")
        await db.execute(
            "UPDATE users SET pro_until = ?, total_paid = total_paid + ? WHERE user_id = ?",
            (new_until, add_paid, user_id),
        )
        await db.commit()


async def set_referrer(user_id: int, referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL",
            (referrer_id, user_id),
        )
        await db.commit()


async def inc_ref_bonus(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_bonus_paid = ref_bonus_paid + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def count_refs(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        (n,) = await cur.fetchone()
    return n


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]


# ---------------- GIFTS ----------------
async def add_gift(admin_id: int, user_id: int, days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO gifts (admin_id, user_id, days, created_at) VALUES (?, ?, ?, ?)",
            (admin_id, user_id, days, datetime.now().isoformat(timespec="seconds")),
        )
        await db.commit()


async def list_gifts(limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT g.admin_id, g.user_id, g.days, g.created_at,
                   u.username, u.first_name
            FROM gifts g
            LEFT JOIN users u ON u.user_id = g.user_id
            ORDER BY g.id DESC LIMIT ?
        """, (limit,))
        return await cur.fetchall()


async def count_gifts() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM gifts")
        (n,) = await cur.fetchone()
    return n


# ---------------- PAYMENTS ----------------
async def save_payment(user_id: int, charge_id: str, amount: int, payload: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO payments
               (user_id, telegram_payment_charge_id, amount, payload, date)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, charge_id, amount, payload,
             datetime.now().isoformat(timespec="seconds")),
        )
        await db.commit()


async def get_recent_payments(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT p.id, p.user_id, p.telegram_payment_charge_id, p.amount,
                   p.date, p.refunded, u.username, u.first_name
            FROM payments p
            LEFT JOIN users u ON u.user_id = p.user_id
            ORDER BY p.id DESC LIMIT ?
        """, (limit,))
        return await cur.fetchall()


async def get_payment_by_id(pid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, user_id, telegram_payment_charge_id, amount, refunded "
            "FROM payments WHERE id = ?", (pid,)
        )
        return await cur.fetchone()


async def get_payment_by_charge_id(charge_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, user_id, amount, refunded FROM payments "
            "WHERE telegram_payment_charge_id = ?", (charge_id,)
        )
        return await cur.fetchone()


async def mark_payment_refunded(charge_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET refunded = 1 WHERE telegram_payment_charge_id = ?",
            (charge_id,),
        )
        await db.commit()


async def count_refunds() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM payments WHERE refunded = 1")
        (n,) = await cur.fetchone()
    return n


# ---------------- MESSAGES ----------------
async def count_saved(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,))
        (n,) = await cur.fetchone()
    return n


async def save_message(
    owner_id: int,
    message_id: int,
    text: str,
    source_chat_id: int | None = None,
    source_type: str = "private",
    author_id: int | None = None,
    author_name: str | None = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO messages
               (user_id, message_id, text, date, source_chat_id, source_type,
                author_id, author_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (owner_id, message_id, text,
             datetime.now().isoformat(timespec="seconds"),
             source_chat_id, source_type, author_id, author_name),
        )
        await db.commit()

    await _maybe_cleanup()


async def save_business_message(
    owner_id: int,
    chat_id: int,
    message_id: int,
    text: str,
    author_id: int | None = None,
    author_name: str | None = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO messages
               (user_id, message_id, text, date, source_chat_id, source_type,
                author_id, author_name)
               VALUES (?, ?, ?, ?, ?, 'business', ?, ?)""",
            (owner_id, message_id, text,
             datetime.now().isoformat(timespec="seconds"), chat_id,
             author_id, author_name),
        )
        await db.commit()

    await _maybe_cleanup()


async def get_history(user_id: int, limit: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT text, date, author_name, source_type
               FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        return await cur.fetchall()


async def get_recent_media(user_id: int, limit: int = 10):
    """Возвращает последние медиа-сообщения пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT text, date, author_name, source_type
               FROM messages
               WHERE user_id = ? AND text LIKE '[%:%]'
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        return await cur.fetchall()


async def get_all_messages(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT text, date, author_name, source_type
               FROM messages WHERE user_id = ? ORDER BY id ASC""",
            (user_id,),
        )
        return await cur.fetchall()


async def search_messages(user_id: int, query: str, limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT text, date, author_name, source_type
               FROM messages WHERE user_id = ? AND text LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, f"%{query}%", limit),
        )
        return await cur.fetchall()


async def clear_history(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # собираем пути к медиа для удаления
        cur = await db.execute(
            "SELECT text FROM messages WHERE user_id = ? AND text LIKE '[%:%]'",
            (user_id,),
        )
        media_rows = await cur.fetchall()

        await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        await db.commit()

    for (path,) in media_rows:
        try:
            inner = path.strip("[]")
            _, _, fpath = inner.partition(":")
            if fpath and os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass


# ---------------- LINKED CHATS ----------------
async def link_chat(chat_id: int, owner_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO linked_chats (chat_id, owner_id, title, linked_at)
            VALUES (?, ?, ?, ?)
        """, (chat_id, owner_id, title,
              datetime.now().isoformat(timespec="seconds")))
        await db.commit()


async def get_chat_owner(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT owner_id FROM linked_chats WHERE chat_id = ?", (chat_id,)
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def unlink_chat(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM linked_chats WHERE chat_id = ?", (chat_id,))
        await db.commit()


# ---------------- BUSINESS ----------------
async def link_business_owner(connection_id: str, owner_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO business_links (connection_id, owner_id, linked_at)
            VALUES (?, ?, ?)
        """, (connection_id, owner_id, datetime.now().isoformat(timespec="seconds")))
        await db.commit()


async def get_business_owner(connection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT owner_id FROM business_links WHERE connection_id = ?",
            (connection_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


# ---------------- PROMOS ----------------
async def get_promo(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM promos WHERE code = ?", (code,))
        return await cur.fetchone()


async def promo_used_by(code: str, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ?", (code, user_id)
        )
        return await cur.fetchone() is not None


async def mark_promo_used(code: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO promo_uses (code, user_id, used_at) VALUES (?, ?, ?)",
            (code, user_id, datetime.now().isoformat(timespec="seconds")),
        )
        await db.execute("UPDATE promos SET used_count = used_count + 1 WHERE code = ?", (code,))
        await db.commit()


async def create_promo(code: str, plan_payload: str, discount: int, max_uses: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO promos
               (code, plan_payload, discount, max_uses, used_count, created_at)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (code, plan_payload, discount, max_uses,
             datetime.now().isoformat(timespec="seconds")),
        )
        await db.commit()


async def delete_promo(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promos WHERE code = ?", (code,))
        await db.execute("DELETE FROM promo_uses WHERE code = ?", (code,))
        await db.commit()


async def list_promos():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code, plan_payload, discount, max_uses, used_count "
            "FROM promos ORDER BY created_at DESC"
        )
        return await cur.fetchall()


# ---------------- ADMIN STATS ----------------
async def admin_overview():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(total_paid),0) FROM users")
        total_users, total_stars = await cur.fetchone()
        cur = await db.execute(
            "SELECT COUNT(*) FROM users WHERE pro_until > ?",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        (active_pro,) = await cur.fetchone()
        cur = await db.execute("SELECT COALESCE(SUM(used_count),0) FROM promos")
        (promo_uses,) = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM gifts")
        (gifts_count,) = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM payments WHERE refunded = 1")
        (refunds_count,) = await cur.fetchone()

    try:
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    except OSError:
        db_size_mb = 0

    return {
        "total_users": total_users,
        "total_stars": total_stars,
        "active_pro": active_pro,
        "promo_uses": promo_uses,
        "gifts_count": gifts_count,
        "refunds_count": refunds_count,
        "db_size_mb": db_size_mb,
    }


async def admin_users(limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, username, first_name, pro_until, total_paid, referrer_id "
            "FROM users ORDER BY total_paid DESC, user_id ASC LIMIT ?",
            (limit,),
        )
        return await cur.fetchall()