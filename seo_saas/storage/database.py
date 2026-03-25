import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "waitlist.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

db: aiosqlite.Connection | None = None


async def connect():
    global db
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    schema = SCHEMA_PATH.read_text()
    for statement in schema.split(";"):
        stmt = statement.strip()
        if stmt:
            await db.execute(stmt)
    await db.commit()


async def close():
    global db
    if db:
        await db.close()
        db = None
