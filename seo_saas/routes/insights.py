from fastapi import APIRouter, Depends, HTTPException
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.insights_engine import generate_insights

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/{prop_id}/generate")
async def create_insights(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        insights = await generate_insights(db, user, prop_id)
        return insights
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{prop_id}")
async def list_insights(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()

    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Property not found")

    async with db.execute(
        """SELECT id, insight_type, title, body, severity, created_at
           FROM insights WHERE property_id = ? AND dismissed = 0
           ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END""",
        (prop_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.patch("/{insight_id}/dismiss")
async def dismiss_insight(insight_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    await db.execute(
        """UPDATE insights SET dismissed = 1 WHERE id = ? AND property_id IN
           (SELECT id FROM properties WHERE user_id = ?)""",
        (insight_id, user["id"]),
    )
    await db.commit()
    return {"ok": True}
