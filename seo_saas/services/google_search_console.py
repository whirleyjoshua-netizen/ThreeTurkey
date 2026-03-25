import httpx
from datetime import datetime, timedelta

GSC_API = "https://www.googleapis.com/webmasters/v3"


async def list_gsc_sites(access_token: str) -> list[dict]:
    """List Search Console sites the user has access to."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GSC_API}/sites",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {"site_url": s["siteUrl"], "permission": s.get("permissionLevel", "")}
        for s in data.get("siteEntry", [])
    ]


async def fetch_search_queries(
    access_token: str, site_url: str, days: int = 28, row_limit: int = 500
) -> list[dict]:
    """Fetch search queries with clicks, impressions, CTR, position."""
    end = datetime.utcnow().date() - timedelta(days=3)  # GSC data has ~3 day lag
    start = end - timedelta(days=days)

    body = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["query"],
        "rowLimit": row_limit,
        "type": "web",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GSC_API}/sites/{site_url}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "keyword": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
        }
        for row in data.get("rows", [])
    ]


async def fetch_pages_performance(
    access_token: str, site_url: str, days: int = 28
) -> list[dict]:
    """Fetch page-level performance data."""
    end = datetime.utcnow().date() - timedelta(days=3)
    start = end - timedelta(days=days)

    body = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["page"],
        "rowLimit": 200,
        "type": "web",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GSC_API}/sites/{site_url}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "page": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
        }
        for row in data.get("rows", [])
    ]
