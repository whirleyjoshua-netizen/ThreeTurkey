from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from seo_saas.storage.database import pool

router = APIRouter(prefix="/api/waitlist")


class WaitlistEntry(BaseModel):
    email: str
    company: str = ""
    website: str = ""
    monthly_traffic: str = ""
    referral: str = ""


@router.post("")
async def join_waitlist(entry: WaitlistEntry):
    if not pool:
        return {"ok": True, "message": "Waitlist recorded (no DB configured)"}
    try:
        await pool.execute(
            """INSERT INTO waitlist (email, company, website, monthly_traffic, referral)
               VALUES ($1, $2, $3, $4, $5)""",
            entry.email, entry.company, entry.website,
            entry.monthly_traffic, entry.referral,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "Email already on waitlist")
    return {"ok": True}


@router.get("/count")
async def waitlist_count():
    if not pool:
        return {"count": 0}
    row = await pool.fetchval("SELECT count(*) FROM waitlist")
    return {"count": row}
