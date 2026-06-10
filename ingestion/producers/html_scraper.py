"""HTML Scraper — async, rate-limited, robots.txt-aware."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from infra.settings import settings

logger = logging.getLogger(__name__)

# Semaphore per domain (max 1 req / DOMAIN_RATE_LIMIT giây)
_domain_locks: dict[str, asyncio.Semaphore] = {}
_robots_cache: dict[str, RobotFileParser] = {}


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _get_semaphore(domain: str) -> asyncio.Semaphore:
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Semaphore(1)
    return _domain_locks[domain]


def _check_robots(url: str) -> bool:
    domain = _domain(url)
    if domain not in _robots_cache:
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            # Nếu không đọc được robots.txt thì cho phép crawl
            _robots_cache[domain] = None
            return True
        _robots_cache[domain] = rp
    rp = _robots_cache[domain]
    if rp is None:
        return True
    return rp.can_fetch(settings.CRAWLER_USER_AGENT, url)


HEADERS = {
    "User-Agent": settings.CRAWLER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi,en;q=0.9",
}


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(settings.HTTP_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def _fetch_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    resp = await client.get(url, headers=HEADERS, timeout=settings.HTTP_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp


async def fetch_html(url: str, client: Optional[httpx.AsyncClient] = None) -> Optional[bytes]:
    """Lấy HTML bytes từ URL, tôn trọng robots.txt và rate limit per domain."""
    if not _check_robots(url):
        logger.warning("robots.txt disallows: %s", url)
        return None

    domain = _domain(url)
    sem = _get_semaphore(domain)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()

    try:
        async with sem:
            # Rate limit: chờ 1/DOMAIN_RATE_LIMIT giây giữa mỗi request cùng domain
            await asyncio.sleep(1.0 / settings.DOMAIN_RATE_LIMIT)
            resp = await _fetch_with_retry(client, url)
            return resp.content
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error %s for %s", e.response.status_code, url)
        return None
    except Exception as exc:
        logger.error("fetch_html failed %s: %s", url, exc)
        return None
    finally:
        if own_client:
            await client.aclose()


async def scrape_article_links(
    page_url: str,
    article_selector: str,
    link_selector: str = "a",
    client: Optional[httpx.AsyncClient] = None,
) -> list[str]:
    """Lấy danh sách link bài từ trang listing (dùng CSS selector từ sources.yaml)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # fallback nếu không có beautifulsoup4
        logger.error("beautifulsoup4 not installed")
        return []

    html = await fetch_html(page_url, client=client)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for container in soup.select(article_selector):
        a_tag = container.select_one(link_selector)
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            full_url = urljoin(page_url, href)
            links.append(full_url)
    return links
