import logging
from seo_saas.services.openai_client import chat_json

log = logging.getLogger(__name__)


async def analyze_keywords(db, user: dict, property_id: int) -> dict:
    """Pull GSC keywords, cluster them with AI, and identify quick wins."""
    from seo_saas.services.google_analytics import _ensure_token
    from seo_saas.services.google_search_console import fetch_search_queries

    # Get property
    async with db.execute(
        "SELECT * FROM properties WHERE id = ? AND user_id = ?",
        (property_id, user["id"]),
    ) as cur:
        prop = await cur.fetchone()

    if not prop:
        raise ValueError("Property not found")
    prop = dict(prop)

    if not prop.get("gsc_site_url"):
        raise ValueError("No Search Console site linked")

    token = await _ensure_token(db, user)
    keywords = await fetch_search_queries(token, prop["gsc_site_url"], 28, 1000)

    if not keywords:
        return {"total": 0, "clusters": 0, "quick_wins": 0}

    # Upsert keywords into database
    for kw in keywords:
        await db.execute(
            """INSERT INTO keywords (property_id, keyword, current_position, clicks, impressions, ctr, url, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(property_id, keyword) DO UPDATE SET
                 previous_position = keywords.current_position,
                 current_position = excluded.current_position,
                 clicks = excluded.clicks,
                 impressions = excluded.impressions,
                 ctr = excluded.ctr,
                 url = excluded.url,
                 fetched_at = excluded.fetched_at""",
            (property_id, kw["keyword"], kw["position"], kw["clicks"], kw["impressions"], kw["ctr"], kw.get("url", "")),
        )
    await db.commit()

    # Cluster with AI (batch in groups of 50)
    kw_texts = [k["keyword"] for k in keywords]
    for i in range(0, len(kw_texts), 50):
        batch = kw_texts[i:i + 50]
        try:
            result = await chat_json(
                system_prompt="You are an SEO keyword analyst. Classify each keyword into a topical cluster and intent type.",
                user_prompt=(
                    f"For each keyword below, assign a short cluster name and intent "
                    f"(informational, transactional, navigational, or commercial).\n\n"
                    f"Keywords:\n" + "\n".join(f"- {k}" for k in batch) +
                    f"\n\nReturn a JSON array of objects: "
                    f'[{{"keyword": "...", "cluster": "...", "intent": "..."}}]'
                ),
                max_tokens=2048,
            )
            if isinstance(result, list):
                for item in result:
                    kw_name = item.get("keyword", "")
                    cluster = item.get("cluster", "")
                    intent = item.get("intent", "")
                    if kw_name:
                        await db.execute(
                            "UPDATE keywords SET cluster = ?, intent = ? WHERE property_id = ? AND keyword = ?",
                            (cluster, intent, property_id, kw_name),
                        )
        except Exception as e:
            log.warning("Keyword clustering batch failed: %s", e)

    await db.commit()

    # Count results
    async with db.execute(
        "SELECT COUNT(*) FROM keywords WHERE property_id = ?", (property_id,)
    ) as cur:
        total = (await cur.fetchone())[0]

    async with db.execute(
        "SELECT COUNT(DISTINCT cluster) FROM keywords WHERE property_id = ? AND cluster IS NOT NULL AND cluster != ''",
        (property_id,),
    ) as cur:
        clusters = (await cur.fetchone())[0]

    async with db.execute(
        """SELECT COUNT(*) FROM keywords
           WHERE property_id = ? AND current_position BETWEEN 5 AND 20 AND impressions > 10""",
        (property_id,),
    ) as cur:
        quick_wins = (await cur.fetchone())[0]

    return {"total": total, "clusters": clusters, "quick_wins": quick_wins}


async def get_keywords(db, property_id: int, user_id: int, filter_type: str = "all") -> list[dict]:
    """Get keywords for a property with optional filtering."""
    # Verify ownership
    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (property_id, user_id)
    ) as cur:
        if not await cur.fetchone():
            raise ValueError("Property not found")

    if filter_type == "quick_wins":
        query = """SELECT * FROM keywords
                   WHERE property_id = ? AND current_position BETWEEN 5 AND 20 AND impressions > 10
                   ORDER BY (impressions * (21 - current_position)) DESC"""
    elif filter_type == "clusters":
        query = """SELECT cluster, COUNT(*) as count,
                   SUM(clicks) as total_clicks, SUM(impressions) as total_impressions,
                   ROUND(AVG(current_position), 1) as avg_position
                   FROM keywords WHERE property_id = ? AND cluster IS NOT NULL AND cluster != ''
                   GROUP BY cluster ORDER BY total_impressions DESC"""
    else:
        query = "SELECT * FROM keywords WHERE property_id = ? ORDER BY impressions DESC LIMIT 200"

    async with db.execute(query, (property_id,)) as cur:
        return [dict(r) for r in await cur.fetchall()]
