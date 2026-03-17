from pathlib import Path
import asyncpg
from seo_saas.config import DATABASE_URL

pool: asyncpg.Pool | None = None
SCHEMA = Path(__file__).with_name("schema.sql").read_text()


async def connect():
    global pool
    if not DATABASE_URL:
        return
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def close():
    global pool
    if pool:
        await pool.close()
        pool = None
