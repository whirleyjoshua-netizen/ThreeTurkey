import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "waitlist.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

MIGRATIONS = [
    ("content_gaps", "volume_label", "TEXT"),
    ("content_gaps", "rationale", "TEXT"),
]

db: aiosqlite.Connection | None = None


async def connect():
    global db
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    for statement in schema.split(";"):
        stmt = statement.strip()
        if stmt:
            await db.execute(stmt)

    # Columns added after tables already existed in production
    for table, column, col_type in MIGRATIONS:
        async with db.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row["name"] for row in await cur.fetchall()}
        if column not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    await db.commit()


async def close():
    global db
    if db:
        await db.close()
        db = None
