from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.brief_generator import generate_brief, list_briefs, get_brief, delete_brief

router = APIRouter(prefix="/api/briefs", tags=["briefs"])


class BriefRequest(BaseModel):
    target_keyword: str


@router.post("/{prop_id}/generate")
async def create_brief(prop_id: int, body: BriefRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    if not body.target_keyword.strip():
        raise HTTPException(400, "Target keyword is required")
    try:
        brief = await generate_brief(db, prop_id, body.target_keyword.strip(), user["id"])
        return brief
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{prop_id}")
async def briefs_list(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await list_briefs(db, prop_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/detail/{brief_id}")
async def brief_detail(brief_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await get_brief(db, brief_id, user["id"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{brief_id}")
async def remove_brief(brief_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        await delete_brief(db, brief_id, user["id"])
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))
