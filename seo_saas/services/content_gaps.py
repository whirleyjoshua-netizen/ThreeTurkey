import json
import logging
from seo_saas.services.openai_client import chat_json

log = logging.getLogger(__name__)


async def analyze_content_gaps(db, user: dict, property_id: int) -> list[dict]:
    """Identify content gaps using existing keyword data and AI analysis."""
    # Verify property
    async with db.execute(
        "SELECT * FROM properties WHERE id = ? AND user_id = ?",
        (property_id, user["id"]),
    ) as cur:
        prop = await cur.fetchone()
    if not prop:
        raise ValueError("Property not found")
    prop = dict(prop)

    # Get existing keywords
    async with db.execute(
        "SELECT keyword, cluster, current_position, clicks, impressions FROM keywords WHERE property_id = ? ORDER BY impressions DESC LIMIT 100",
        (property_id,),
    ) as cur:
        existing_kws = [dict(r) for r in await cur.fetchall()]

    kw_list = ", ".join(k["keyword"] for k in existing_kws[:50]) if existing_kws else "none yet"
    clusters = set(k.get("cluster") or "" for k in existing_kws if k.get("cluster"))
    cluster_list = ", ".join(clusters) if clusters else "unknown"

    gaps = await chat_json(
        system_prompt=(
            "You are an SEO content strategist. Identify content topics this website is missing "
            "that would drive organic traffic. Focus on realistic, high-value opportunities."
        ),
        user_prompt=(
            f"Website: {prop['domain']}\n"
            f"Current keyword clusters: {cluster_list}\n"
            f"Current top keywords: {kw_list}\n\n"
            "Identify 10-15 content topics this site should cover but likely doesn't. "
            "For each, provide:\n"
            "- topic: descriptive topic name\n"
            "- priority_score: 1-10 (10 = highest priority)\n"
            "- estimated_volume: estimated monthly search volume category (low/medium/high)\n"
            "- rationale: brief reason this is a gap\n\n"
            "Return a JSON array of objects."
        ),
        max_tokens=2048,
    )

    if not isinstance(gaps, list):
        return []

    # Clear old gaps and insert new
    await db.execute("DELETE FROM content_gaps WHERE property_id = ?", (property_id,))

    saved = []
    for gap in gaps:
        volume_map = {"low": 100, "medium": 1000, "high": 5000}
        est_vol = volume_map.get(str(gap.get("estimated_volume", "")).lower(), 500)
        priority = min(10, max(1, gap.get("priority_score", 5)))

        await db.execute(
            """INSERT INTO content_gaps (property_id, topic, priority_score, estimated_volume, status)
               VALUES (?, ?, ?, ?, 'open')""",
            (property_id, gap.get("topic", ""), priority, est_vol),
        )
        saved.append({
            "topic": gap.get("topic", ""),
            "priority_score": priority,
            "estimated_volume": gap.get("estimated_volume", "medium"),
            "rationale": gap.get("rationale", ""),
            "status": "open",
        })

    await db.commit()
    return saved


async def get_content_gaps(db, property_id: int, user_id: int) -> list[dict]:
    """Get content gaps for a property."""
    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (property_id, user_id)
    ) as cur:
        if not await cur.fetchone():
            raise ValueError("Property not found")

    async with db.execute(
        "SELECT * FROM content_gaps WHERE property_id = ? ORDER BY priority_score DESC",
        (property_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def update_gap_status(db, gap_id: int, status: str, user_id: int):
    """Update a content gap's status."""
    await db.execute(
        """UPDATE content_gaps SET status = ? WHERE id = ? AND property_id IN
           (SELECT id FROM properties WHERE user_id = ?)""",
        (status, gap_id, user_id),
    )
    await db.commit()
