from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from seo_saas.deps import get_db, get_current_user
from seo_saas.services.google_analytics import (
    list_ga4_properties,
    fetch_traffic_summary,
    fetch_top_pages,
    fetch_traffic_sources,
    _ensure_token,
)
from seo_saas.services.google_search_console import (
    list_gsc_sites,
    fetch_search_queries,
    fetch_pages_performance,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── Helpers ──────────────────────────────────────────────

async def _fresh_token(user: dict) -> str:
    db = get_db()
    return await _ensure_token(db, user)


# ── Properties ───────────────────────────────────────────

@router.get("/properties")
async def list_properties(user: dict = Depends(get_current_user)):
    db = get_db()
    async with db.execute(
        "SELECT id, display_name, domain, ga4_property_id, gsc_site_url FROM properties WHERE user_id = ?",
        (user["id"],),
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


class AddPropertyRequest(BaseModel):
    display_name: str
    domain: str
    ga4_property_id: str = ""
    gsc_site_url: str = ""


@router.post("/properties")
async def add_property(body: AddPropertyRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    async with db.execute(
        """INSERT INTO properties (user_id, display_name, domain, ga4_property_id, gsc_site_url)
           VALUES (?, ?, ?, ?, ?)""",
        (user["id"], body.display_name, body.domain, body.ga4_property_id, body.gsc_site_url),
    ) as cur:
        prop_id = cur.lastrowid
    await db.commit()
    return {"id": prop_id, "display_name": body.display_name, "domain": body.domain}


@router.delete("/properties/{prop_id}")
async def delete_property(prop_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    await db.execute(
        "DELETE FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    )
    await db.commit()
    return {"ok": True}


# ── Discovery: list GA4 properties & GSC sites ──────────

@router.get("/google/ga4-properties")
async def google_ga4_properties(user: dict = Depends(get_current_user)):
    token = await _fresh_token(user)
    return await list_ga4_properties(token)


@router.get("/google/gsc-sites")
async def google_gsc_sites(user: dict = Depends(get_current_user)):
    token = await _fresh_token(user)
    return await list_gsc_sites(token)


# ── GA4 Data ─────────────────────────────────────────────

async def _get_prop(prop_id: int, user: dict) -> dict:
    db = get_db()
    async with db.execute(
        "SELECT * FROM properties WHERE id = ? AND user_id = ?", (prop_id, user["id"])
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Property not found")
    return dict(row)


@router.get("/properties/{prop_id}/traffic")
async def property_traffic(prop_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    prop = await _get_prop(prop_id, user)
    if not prop.get("ga4_property_id"):
        raise HTTPException(400, "No GA4 property linked")
    token = await _fresh_token(user)
    return await fetch_traffic_summary(token, prop["ga4_property_id"], days)


@router.get("/properties/{prop_id}/top-pages")
async def property_top_pages(prop_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    prop = await _get_prop(prop_id, user)
    if not prop.get("ga4_property_id"):
        raise HTTPException(400, "No GA4 property linked")
    token = await _fresh_token(user)
    return await fetch_top_pages(token, prop["ga4_property_id"], days)


@router.get("/properties/{prop_id}/sources")
async def property_sources(prop_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    prop = await _get_prop(prop_id, user)
    if not prop.get("ga4_property_id"):
        raise HTTPException(400, "No GA4 property linked")
    token = await _fresh_token(user)
    return await fetch_traffic_sources(token, prop["ga4_property_id"], days)


# ── GSC Data ─────────────────────────────────────────────

@router.get("/properties/{prop_id}/keywords")
async def property_keywords(prop_id: int, days: int = 28, user: dict = Depends(get_current_user)):
    prop = await _get_prop(prop_id, user)
    if not prop.get("gsc_site_url"):
        raise HTTPException(400, "No Search Console site linked")
    token = await _fresh_token(user)
    return await fetch_search_queries(token, prop["gsc_site_url"], days)


@router.get("/properties/{prop_id}/page-performance")
async def property_page_performance(prop_id: int, days: int = 28, user: dict = Depends(get_current_user)):
    prop = await _get_prop(prop_id, user)
    if not prop.get("gsc_site_url"):
        raise HTTPException(400, "No Search Console site linked")
    token = await _fresh_token(user)
    return await fetch_pages_performance(token, prop["gsc_site_url"], days)


# ── Overview (combined summary) ──────────────────────────

@router.get("/properties/{prop_id}/overview")
async def property_overview(prop_id: int, user: dict = Depends(get_current_user)):
    """Return a combined overview for the dashboard hero cards."""
    prop = await _get_prop(prop_id, user)
    token = await _fresh_token(user)
    result = {"property": {"id": prop["id"], "display_name": prop["display_name"], "domain": prop["domain"]}}

    if prop.get("ga4_property_id"):
        try:
            traffic = await fetch_traffic_summary(token, prop["ga4_property_id"], 30)
            total_sessions = sum(r["sessions"] for r in traffic)
            total_users = sum(r["users"] for r in traffic)
            total_pageviews = sum(r["pageviews"] for r in traffic)
            avg_bounce = sum(r["bounce_rate"] for r in traffic) / max(len(traffic), 1)
            result["ga4"] = {
                "sessions_30d": total_sessions,
                "users_30d": total_users,
                "pageviews_30d": total_pageviews,
                "avg_bounce_rate": round(avg_bounce, 4),
                "daily": traffic,
            }
        except Exception:
            result["ga4"] = None

    if prop.get("gsc_site_url"):
        try:
            keywords = await fetch_search_queries(token, prop["gsc_site_url"], 28, 100)
            total_clicks = sum(k["clicks"] for k in keywords)
            total_impressions = sum(k["impressions"] for k in keywords)
            avg_position = sum(k["position"] for k in keywords) / max(len(keywords), 1)
            result["gsc"] = {
                "total_clicks_28d": total_clicks,
                "total_impressions_28d": total_impressions,
                "avg_position": round(avg_position, 1),
                "top_keywords": keywords[:20],
            }
        except Exception:
            result["gsc"] = None

    return result
