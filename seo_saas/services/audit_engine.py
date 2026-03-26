import asyncio
import json
import logging
from datetime import datetime

from seo_saas.services.crawler import crawl_page, CrawlResult
from seo_saas.services.openai_client import chat_json

log = logging.getLogger(__name__)

MAX_PAGES = 25
CRAWL_CONCURRENCY = 3


async def run_audit(db, user: dict, property_id: int):
    """Run a full SEO audit on a property. Designed to be run as a background task."""
    audit_id = None
    try:
        # Create audit row
        async with db.execute(
            "INSERT INTO audits (property_id, status, started_at) VALUES (?, 'running', ?)",
            (property_id, datetime.utcnow().isoformat()),
        ) as cur:
            audit_id = cur.lastrowid
        await db.commit()

        # Get property info
        async with db.execute(
            "SELECT * FROM properties WHERE id = ? AND user_id = ?",
            (property_id, user["id"]),
        ) as cur:
            prop = await cur.fetchone()

        if not prop:
            raise ValueError("Property not found")

        prop = dict(prop)
        domain = prop["domain"]
        scheme = "https"
        base_url = f"{scheme}://{domain}"

        # Get pages to audit - try GSC first (real URLs), fall back to GA4
        pages = await _get_pages_to_audit(db, user, prop)

        if not pages:
            pages = ["/"]  # At minimum audit the homepage

        # Convert paths to full URLs
        urls = []
        for page in pages[:MAX_PAGES]:
            if page.startswith("http"):
                urls.append(page)
            else:
                urls.append(base_url + (page if page.startswith("/") else "/" + page))

        # Crawl pages concurrently with semaphore
        sem = asyncio.Semaphore(CRAWL_CONCURRENCY)

        async def _crawl(url):
            async with sem:
                return await crawl_page(url)

        results: list[CrawlResult] = await asyncio.gather(*[_crawl(u) for u in urls])

        # Analyze each page and store results
        total_issues = 0
        total_score_points = 0
        pages_scanned = 0

        for cr in results:
            issues = _analyze_page(cr)
            issues_json = json.dumps([{"severity": i[0], "category": i[1], "message": i[2]} for i in issues])

            async with db.execute(
                """INSERT INTO audit_pages
                   (audit_id, url, status_code, title, meta_description,
                    h1_count, h2_count, word_count, has_canonical, has_og_tags,
                    load_time_ms, issues_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit_id, cr.url, cr.status_code, cr.title, cr.meta_description,
                    cr.h1_count, cr.h2_count, cr.word_count,
                    1 if cr.has_canonical else 0,
                    1 if (cr.has_og_title and cr.has_og_description) else 0,
                    cr.load_time_ms, issues_json,
                ),
            ) as cur:
                page_id = cur.lastrowid

            for severity, category, message in issues:
                await db.execute(
                    """INSERT INTO audit_issues
                       (audit_id, page_id, severity, category, message, url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (audit_id, page_id, severity, category, message, cr.url),
                )
                total_issues += 1

            page_score = _score_page(issues)
            total_score_points += page_score
            pages_scanned += 1

        await db.commit()

        # Calculate overall score
        score = round(total_score_points / max(pages_scanned, 1))

        # Generate AI suggestions for issues (batch)
        await _generate_suggestions(db, audit_id)

        # Update audit with results
        await db.execute(
            """UPDATE audits SET status='completed', pages_scanned=?, issues_found=?,
               score=?, completed_at=? WHERE id=?""",
            (pages_scanned, total_issues, score, datetime.utcnow().isoformat(), audit_id),
        )
        await db.commit()
        log.info("Audit %d completed: %d pages, %d issues, score %d", audit_id, pages_scanned, total_issues, score)

    except Exception as e:
        log.error("Audit %s failed: %s", audit_id, e)
        if audit_id:
            await db.execute(
                "UPDATE audits SET status='failed', completed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), audit_id),
            )
            await db.commit()


async def _get_pages_to_audit(db, user: dict, prop: dict) -> list[str]:
    """Get page URLs to audit from GSC or GA4 data."""
    from seo_saas.services.google_analytics import _ensure_token, fetch_top_pages
    from seo_saas.services.google_search_console import fetch_pages_performance

    token = await _ensure_token(db, user)

    # Try GSC first (gives us full URLs)
    if prop.get("gsc_site_url"):
        try:
            pages = await fetch_pages_performance(token, prop["gsc_site_url"], 28)
            return [p["page"] for p in pages[:MAX_PAGES]]
        except Exception:
            pass

    # Fall back to GA4 (gives us paths)
    if prop.get("ga4_property_id"):
        try:
            pages = await fetch_top_pages(token, prop["ga4_property_id"], 30)
            return [p["page"] for p in pages[:MAX_PAGES]]
        except Exception:
            pass

    return []


def _analyze_page(cr: CrawlResult) -> list[tuple[str, str, str]]:
    """Analyze a crawled page and return list of (severity, category, message)."""
    issues = []

    if cr.error:
        issues.append(("critical", "crawl", f"Page could not be crawled: {cr.error}"))
        return issues

    if cr.status_code >= 400:
        issues.append(("critical", "status", f"Page returned HTTP {cr.status_code}"))

    # Title
    if not cr.title:
        issues.append(("critical", "title", "Missing title tag"))
    elif cr.title_length > 60:
        issues.append(("warning", "title", f"Title too long ({cr.title_length} chars, recommended: ≤60)"))
    elif cr.title_length < 30:
        issues.append(("warning", "title", f"Title too short ({cr.title_length} chars, recommended: 30-60)"))

    # Meta description
    if not cr.meta_description:
        issues.append(("warning", "meta", "Missing meta description"))
    elif cr.meta_desc_length > 160:
        issues.append(("warning", "meta", f"Meta description too long ({cr.meta_desc_length} chars, recommended: ≤160)"))
    elif cr.meta_desc_length < 70:
        issues.append(("warning", "meta", f"Meta description too short ({cr.meta_desc_length} chars, recommended: 70-160)"))

    # H1
    if cr.h1_count == 0:
        issues.append(("critical", "heading", "Missing H1 tag"))
    elif cr.h1_count > 1:
        issues.append(("warning", "heading", f"Multiple H1 tags found ({cr.h1_count})"))

    # H2
    if cr.h2_count == 0 and cr.word_count > 300:
        issues.append(("info", "heading", "No H2 subheadings — consider adding structure"))

    # Word count
    if cr.word_count < 100:
        issues.append(("critical", "content", f"Extremely low word count ({cr.word_count} words)"))
    elif cr.word_count < 300:
        issues.append(("info", "content", f"Low word count ({cr.word_count} words) — thin content may underperform"))

    # Images
    if cr.img_missing_alt > 0:
        issues.append(("warning", "images", f"{cr.img_missing_alt} image(s) missing alt text"))

    # Canonical
    if not cr.has_canonical:
        issues.append(("warning", "canonical", "No canonical tag found"))

    # Open Graph
    if not cr.has_og_title or not cr.has_og_description:
        issues.append(("info", "social", "Missing Open Graph tags (og:title or og:description)"))

    # Load time
    if cr.load_time_ms > 5000:
        issues.append(("warning", "performance", f"Slow page load ({cr.load_time_ms}ms)"))
    elif cr.load_time_ms > 10000:
        issues.append(("critical", "performance", f"Very slow page load ({cr.load_time_ms}ms)"))

    return issues


def _score_page(issues: list[tuple[str, str, str]]) -> int:
    """Score a page 0-100 based on issues found."""
    score = 100
    for severity, _, _ in issues:
        if severity == "critical":
            score -= 15
        elif severity == "warning":
            score -= 5
        elif severity == "info":
            score -= 2
    return max(0, score)


async def _generate_suggestions(db, audit_id: int):
    """Use OpenAI to generate suggestions for audit issues."""
    try:
        async with db.execute(
            """SELECT ai.id, ai.severity, ai.category, ai.message, ai.url
               FROM audit_issues ai WHERE ai.audit_id = ? ORDER BY ai.id""",
            (audit_id,),
        ) as cur:
            issues = [dict(r) for r in await cur.fetchall()]

        if not issues:
            return

        # Batch issues in groups of 10
        for i in range(0, len(issues), 10):
            batch = issues[i:i + 10]
            issues_text = "\n".join(
                f"- [{iss['severity']}] {iss['category']}: {iss['message']} (URL: {iss['url']})"
                for iss in batch
            )

            suggestions = await chat_json(
                system_prompt="You are an SEO expert. For each issue, provide a brief, actionable fix in 1-2 sentences.",
                user_prompt=f"Provide a suggestion for each of these SEO issues:\n{issues_text}\n\nReturn a JSON array of strings, one suggestion per issue, in the same order.",
            )

            if isinstance(suggestions, list):
                for j, suggestion in enumerate(suggestions):
                    if j < len(batch):
                        await db.execute(
                            "UPDATE audit_issues SET suggestion = ? WHERE id = ?",
                            (str(suggestion), batch[j]["id"]),
                        )

        await db.commit()
    except Exception as e:
        log.warning("Failed to generate AI suggestions: %s", e)
