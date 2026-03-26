import time
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    url: str
    status_code: int = 0
    load_time_ms: int = 0
    error: str = ""
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_desc_length: int = 0
    h1_tags: list[str] = field(default_factory=list)
    h1_count: int = 0
    h2_tags: list[str] = field(default_factory=list)
    h2_count: int = 0
    word_count: int = 0
    img_total: int = 0
    img_missing_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    has_canonical: bool = False
    has_og_title: bool = False
    has_og_description: bool = False
    has_og_image: bool = False


async def crawl_page(url: str, timeout: float = 15.0) -> CrawlResult:
    """Crawl a single page and extract SEO-relevant data."""
    result = CrawlResult(url=url)
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "ThreeTurkey-SEOBot/1.0"},
        ) as client:
            resp = await client.get(url)
            result.status_code = resp.status_code
            result.load_time_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code >= 400:
                result.error = f"HTTP {resp.status_code}"
                return result

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                result.error = f"Not HTML: {content_type}"
                return result

            _parse_html(resp.text, url, result)

    except httpx.TimeoutException:
        result.error = "Timeout"
        result.load_time_ms = int(timeout * 1000)
    except Exception as e:
        result.error = str(e)
        log.warning("Crawl failed for %s: %s", url, e)

    return result


def _parse_html(html: str, url: str, result: CrawlResult):
    soup = BeautifulSoup(html, "html.parser")
    domain = urlparse(url).netloc

    # Title
    tag = soup.find("title")
    if tag and tag.string:
        result.title = tag.string.strip()
        result.title_length = len(result.title)

    # Meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        result.meta_description = meta["content"].strip()
        result.meta_desc_length = len(result.meta_description)

    # Headings
    result.h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    result.h1_count = len(result.h1_tags)
    result.h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
    result.h2_count = len(result.h2_tags)

    # Word count
    body = soup.find("body")
    if body:
        text = body.get_text(separator=" ", strip=True)
        result.word_count = len(text.split())

    # Images
    images = soup.find_all("img")
    result.img_total = len(images)
    result.img_missing_alt = sum(1 for img in images if not img.get("alt", "").strip())

    # Links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != domain:
            result.external_links += 1
        elif href.startswith("/") or parsed.netloc == domain:
            result.internal_links += 1

    # Canonical
    result.has_canonical = bool(soup.find("link", rel="canonical"))

    # Open Graph
    result.has_og_title = bool(soup.find("meta", property="og:title"))
    result.has_og_description = bool(soup.find("meta", property="og:description"))
    result.has_og_image = bool(soup.find("meta", property="og:image"))
