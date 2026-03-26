import asyncio
from fastapi import APIRouter, Depends, HTTPException
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.keyword_engine import analyze_keywords, get_keywords

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.post("/{prop_id}/analyze")
async def start_keyword_analysis(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        result = await analyze_keywords(db, user, prop_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{prop_id}")
async def list_keywords(prop_id: int, filter: str = "all", user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await get_keywords(db, prop_id, user["id"], filter)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{prop_id}/quick-wins")
async def quick_wins(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await get_keywords(db, prop_id, user["id"], "quick_wins")
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{prop_id}/clusters")
async def clusters(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        return await get_keywords(db, prop_id, user["id"], "clusters")
    except ValueError as e:
        raise HTTPException(404, str(e))
