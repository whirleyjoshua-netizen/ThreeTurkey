from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.content_gaps import analyze_content_gaps, get_content_gaps, update_gap_status

router = APIRouter(prefix="/api/content-gaps", tags=["content-gaps"])


@router.post("/{prop_id}/analyze")
async def create_gap_analysis(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        gaps = await analyze_content_gaps(db, user, prop_id)
        return gaps
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{prop_id}")
async def list_gaps(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await get_content_gaps(db, prop_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))


class StatusUpdate(BaseModel):
    status: str


@router.patch("/{gap_id}/status")
async def update_status(gap_id: int, body: StatusUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    if body.status not in ("open", "in_progress", "done"):
        raise HTTPException(400, "Status must be open, in_progress, or done")
    try:
        await update_gap_status(db, gap_id, body.status, user["id"])
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))
