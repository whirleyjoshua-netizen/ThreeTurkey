import asyncio
from fastapi import APIRouter, Depends, HTTPException
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.audit_engine import run_audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.post("/{prop_id}/run")
async def start_audit(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()

    # Verify property ownership
    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Property not found")

    # Check if an audit is already running
    async with db.execute(
        "SELECT id FROM audits WHERE property_id = ? AND status = 'running'", (prop_id,)
    ) as cur:
        if await cur.fetchone():
            raise HTTPException(409, "An audit is already running for this property")

    # Start audit as background task
    asyncio.create_task(run_audit(db, user, prop_id))

    return {"status": "running", "message": "Audit started"}


@router.get("/{prop_id}/latest")
async def latest_audit(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()

    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Property not found")

    async with db.execute(
        """SELECT id, status, pages_scanned, issues_found, score, started_at, completed_at
           FROM audits WHERE property_id = ? ORDER BY created_at DESC LIMIT 1""",
        (prop_id,),
    ) as cur:
        audit = await cur.fetchone()

    if not audit:
        return None

    audit = dict(audit)

    # If completed, include issues
    if audit["status"] == "completed":
        async with db.execute(
            """SELECT ai.severity, ai.category, ai.message, ai.suggestion, ai.url
               FROM audit_issues ai WHERE ai.audit_id = ?
               ORDER BY CASE ai.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END""",
            (audit["id"],),
        ) as cur:
            audit["issues"] = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            """SELECT url, status_code, title, word_count, h1_count, load_time_ms
               FROM audit_pages WHERE audit_id = ?""",
            (audit["id"],),
        ) as cur:
            audit["pages"] = [dict(r) for r in await cur.fetchall()]

    return audit


@router.get("/{prop_id}/history")
async def audit_history(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()

    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Property not found")

    async with db.execute(
        """SELECT id, status, pages_scanned, issues_found, score, started_at, completed_at
           FROM audits WHERE property_id = ? ORDER BY created_at DESC LIMIT 20""",
        (prop_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
