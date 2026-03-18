import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "waitlist.db"

db: aiosqlite.Connection | None = None


async def connect():
    global db
    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute(
        """CREATE TABLE IF NOT EXISTS waitlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL UNIQUE,
            created_at  TEXT DEFAULT (datetime('now'))
        )"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS customers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            email               TEXT NOT NULL UNIQUE,
            stripe_customer_id  TEXT,
            stripe_session_id   TEXT,
            amount_paid         INTEGER NOT NULL DEFAULT 14900,
            paid_at             TEXT DEFAULT (datetime('now'))
        )"""
    )
    await db.commit()


async def close():
    global db
    if db:
        await db.close()
        db = None
