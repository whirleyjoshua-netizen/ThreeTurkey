from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import seo_saas.storage.database as store

router = APIRouter(prefix="/api/waitlist")


class WaitlistEntry(BaseModel):
    email: str


@router.post("")
async def join_waitlist(entry: WaitlistEntry):
    if not store.db:
        raise HTTPException(500, "Database not ready")
    try:
        await store.db.execute("INSERT INTO waitlist (email) VALUES (?)", (entry.email,))
        await store.db.commit()
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "Email already on waitlist")
        raise
    return {"ok": True}


@router.get("/count")
async def waitlist_count():
    if not store.db:
        return {"count": 0}
    async with store.db.execute("SELECT count(*) FROM waitlist") as cursor:
        row = await cursor.fetchone()
    return {"count": row[0] if row else 0}
