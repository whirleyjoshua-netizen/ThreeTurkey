import logging
from seo_saas.services.openai_client import chat_json

log = logging.getLogger(__name__)


async def generate_insights(db, user: dict, property_id: int) -> list[dict]:
    """Analyze GA4 + GSC data and generate AI-powered insights."""
    from seo_saas.services.google_analytics import _ensure_token, fetch_traffic_summary, fetch_top_pages
    from seo_saas.services.google_search_console import fetch_search_queries

    # Verify property
    async with db.execute(
        "SELECT * FROM properties WHERE id = ? AND user_id = ?",
        (property_id, user["id"]),
    ) as cur:
        prop = await cur.fetchone()
    if not prop:
        raise ValueError("Property not found")
    prop = dict(prop)

    token = await _ensure_token(db, user)

    # Gather data
    context_parts = [f"Website: {prop['domain']}"]

    if prop.get("ga4_property_id"):
        try:
            traffic = await fetch_traffic_summary(token, prop["ga4_property_id"], 30)
            total_sessions = sum(r["sessions"] for r in traffic)
            total_users = sum(r["users"] for r in traffic)
            total_pageviews = sum(r["pageviews"] for r in traffic)
            avg_bounce = sum(r["bounce_rate"] for r in traffic) / max(len(traffic), 1)

            # Detect trends
            if len(traffic) >= 14:
                first_half = sum(r["sessions"] for r in traffic[:len(traffic)//2])
                second_half = sum(r["sessions"] for r in traffic[len(traffic)//2:])
                trend = "increasing" if second_half > first_half * 1.1 else "decreasing" if second_half < first_half * 0.9 else "stable"
            else:
                trend = "unknown"

            context_parts.append(
                f"GA4 (30 days): {total_sessions} sessions, {total_users} users, "
                f"{total_pageviews} pageviews, {avg_bounce:.1%} avg bounce rate, trend: {trend}"
            )

            pages = await fetch_top_pages(token, prop["ga4_property_id"], 30)
            top5 = pages[:5]
            bottom5 = [p for p in pages if p["sessions"] > 0][-5:]
            context_parts.append("Top pages: " + ", ".join(f"{p['page']} ({p['sessions']} sessions)" for p in top5))
            if bottom5:
                context_parts.append("Low-performing pages: " + ", ".join(f"{p['page']} ({p['sessions']} sessions)" for p in bottom5))
        except Exception as e:
            log.warning("Failed to fetch GA4 data for insights: %s", e)

    if prop.get("gsc_site_url"):
        try:
            keywords = await fetch_search_queries(token, prop["gsc_site_url"], 28, 200)
            total_clicks = sum(k["clicks"] for k in keywords)
            total_impressions = sum(k["impressions"] for k in keywords)

            # Quick wins
            quick_wins = [k for k in keywords if 5 <= k["position"] <= 20 and k["impressions"] > 10]
            # Low CTR opportunities
            low_ctr = [k for k in keywords if k["position"] <= 10 and k["ctr"] < 0.03 and k["impressions"] > 50]

            context_parts.append(
                f"GSC (28 days): {total_clicks} clicks, {total_impressions} impressions, "
                f"{len(keywords)} tracked keywords"
            )
            context_parts.append(f"Quick wins (position 5-20 with >10 impressions): {len(quick_wins)} keywords")
            if quick_wins[:5]:
                context_parts.append("Top quick wins: " + ", ".join(
                    f"{k['keyword']} (pos {k['position']}, {k['impressions']} imp)"
                    for k in sorted(quick_wins, key=lambda x: x["impressions"], reverse=True)[:5]
                ))
            if low_ctr[:5]:
                context_parts.append("Low CTR on page 1: " + ", ".join(
                    f"{k['keyword']} (pos {k['position']}, CTR {k['ctr']:.1%})"
                    for k in low_ctr[:5]
                ))
        except Exception as e:
            log.warning("Failed to fetch GSC data for insights: %s", e)

    if len(context_parts) <= 1:
        return []

    context = "\n".join(context_parts)

    # Generate insights with AI
    insights = await chat_json(
        system_prompt=(
            "You are an expert SEO analyst. Generate 3-5 actionable insights based on the website data. "
            "Each insight must have: type (one of: traffic_drop, ctr_opportunity, keyword_trend, "
            "content_suggestion, technical_issue, quick_win), title (short), body (specific actionable "
            "recommendation in 2-3 sentences), and severity (critical, warning, or info)."
        ),
        user_prompt=f"Analyze this data and provide insights:\n\n{context}\n\nReturn a JSON array of insight objects.",
        max_tokens=2048,
    )

    if not isinstance(insights, list):
        return []

    # Clear old insights, insert new ones
    await db.execute(
        "DELETE FROM insights WHERE property_id = ? AND dismissed = 0",
        (property_id,),
    )

    saved = []
    for ins in insights:
        await db.execute(
            """INSERT INTO insights (property_id, insight_type, title, body, severity)
               VALUES (?, ?, ?, ?, ?)""",
            (property_id, ins.get("type", "info"), ins.get("title", ""),
             ins.get("body", ""), ins.get("severity", "info")),
        )
        saved.append(ins)
    await db.commit()

    return saved
