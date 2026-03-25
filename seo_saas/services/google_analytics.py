import httpx
from datetime import datetime, timedelta

GA4_API = "https://analyticsdata.googleapis.com/v1beta"


async def _ensure_token(db, user: dict) -> str:
    """Return a valid access token, refreshing if needed."""
    from seo_saas.services.google_auth import refresh_access_token

    expires = user.get("token_expires_at")
    if expires and datetime.fromisoformat(expires) > datetime.utcnow():
        return user["access_token"]

    token_data = await refresh_access_token(user["refresh_token"])
    new_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 3600)
    new_expires = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    await db.execute(
        "UPDATE users SET access_token = ?, token_expires_at = ? WHERE id = ?",
        (new_token, new_expires, user["id"]),
    )
    await db.commit()
    return new_token


async def list_ga4_properties(access_token: str) -> list[dict]:
    """List GA4 properties the user has access to."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    properties = []
    for account in data.get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            properties.append({
                "property_id": prop["property"],
                "display_name": prop.get("displayName", ""),
                "account_name": account.get("displayName", ""),
            })
    return properties


async def fetch_traffic_summary(access_token: str, property_id: str, days: int = 30) -> list[dict]:
    """Fetch daily sessions/users/pageviews for the last N days."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    body = {
        "dateRanges": [{"startDate": str(start), "endDate": str(end)}],
        "dimensions": [{"name": "date"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "screenPageViews"},
            {"name": "bounceRate"},
        ],
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GA4_API}/{property_id}:runReport",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    rows = []
    for row in data.get("rows", []):
        rows.append({
            "date": row["dimensionValues"][0]["value"],
            "sessions": int(row["metricValues"][0]["value"]),
            "users": int(row["metricValues"][1]["value"]),
            "pageviews": int(row["metricValues"][2]["value"]),
            "bounce_rate": float(row["metricValues"][3]["value"]),
        })
    return rows


async def fetch_top_pages(access_token: str, property_id: str, days: int = 30) -> list[dict]:
    """Fetch top pages by sessions."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    body = {
        "dateRanges": [{"startDate": str(start), "endDate": str(end)}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "screenPageViews"},
            {"name": "bounceRate"},
        ],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 50,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GA4_API}/{property_id}:runReport",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    rows = []
    for row in data.get("rows", []):
        rows.append({
            "page": row["dimensionValues"][0]["value"],
            "sessions": int(row["metricValues"][0]["value"]),
            "pageviews": int(row["metricValues"][1]["value"]),
            "bounce_rate": float(row["metricValues"][2]["value"]),
        })
    return rows


async def fetch_traffic_sources(access_token: str, property_id: str, days: int = 30) -> list[dict]:
    """Fetch traffic by source/medium."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    body = {
        "dateRanges": [{"startDate": str(start), "endDate": str(end)}],
        "dimensions": [{"name": "sessionSource"}, {"name": "sessionMedium"}],
        "metrics": [{"name": "sessions"}, {"name": "totalUsers"}],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 20,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GA4_API}/{property_id}:runReport",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    rows = []
    for row in data.get("rows", []):
        rows.append({
            "source": row["dimensionValues"][0]["value"],
            "medium": row["dimensionValues"][1]["value"],
            "sessions": int(row["metricValues"][0]["value"]),
            "users": int(row["metricValues"][1]["value"]),
        })
    return rows
