"""RSS Fetcher — lấy bài từ RSS/Atom feed với etag/modified caching."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import mktime
from typing import Optional, Tuple

import feedparser

from infra.settings import settings

logger = logging.getLogger(__name__)

# Từ khoá giao thông — filter sơ bộ trước khi tốn công xử lý sâu
TRAFFIC_KEYWORDS: set[str] = {
    "tai nạn", "va chạm", "lật xe", "đâm vào", "đụng nhau",
    "ngập", "ngập lụt", "ngập sâu", "mưa lớn",
    "sửa đường", "thi công", "rào chắn", "cấm đường", "phân luồng",
    "ùn tắc", "ùn ứ", "kẹt xe", "tắc đường", "tắc nghiêm trọng",
    "lễ hội", "hội chợ", "sự kiện", "biểu diễn",
    "bão", "gió mạnh", "sương mù",
    "tai nạn giao thông", "ách tắc",
}


def _is_traffic_related(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in TRAFFIC_KEYWORDS)


def _parse_published(entry: feedparser.FeedParserDict) -> Optional[datetime]:
    """Chuyển published_parsed (time.struct_time UTC) sang datetime UTC."""
    if entry.get("published_parsed"):
        try:
            ts = mktime(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass
    if entry.get("published"):
        try:
            return parsedate_to_datetime(entry.published).astimezone(timezone.utc)
        except Exception:
            pass
    return None


def fetch_rss(
    url: str,
    last_etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    filter_keywords: bool = True,
) -> Tuple[list[dict], Optional[str], Optional[str]]:
    """Parse RSS feed và trả về danh sách bài viết.

    Returns:
        (entries, new_etag, new_modified)
        entries: list[dict] với keys external_id, title, summary, link, published_at
    """
    kwargs: dict = {}
    if last_etag:
        kwargs["etag"] = last_etag
    if last_modified:
        kwargs["modified"] = last_modified

    try:
        fp = feedparser.parse(url, **kwargs)
    except Exception as exc:
        logger.error("feedparser error url=%s: %s", url, exc)
        return [], last_etag, last_modified

    status = getattr(fp, "status", None)
    if status == 304:
        logger.debug("RSS 304 Not Modified: %s", url)
        return [], getattr(fp, "etag", last_etag), getattr(fp, "modified", last_modified)

    if status and status >= 400:
        logger.warning("RSS HTTP %s: %s", status, url)
        return [], last_etag, last_modified

    entries: list[dict] = []
    for e in fp.entries:
        eid = e.get("id") or e.get("link", "")
        if not eid:
            continue
        title = getattr(e, "title", "") or ""
        summary = getattr(e, "summary", "") or ""

        if filter_keywords and not _is_traffic_related(title, summary):
            continue

        entries.append(
            {
                "external_id": hashlib.sha1(eid.encode()).hexdigest(),
                "title": title,
                "summary": summary,
                "link": e.get("link", eid),
                "published_at": _parse_published(e),
            }
        )

    new_etag = getattr(fp, "etag", last_etag)
    new_modified = getattr(fp, "modified", last_modified)
    logger.info("RSS %s: fetched %d entries (status=%s)", url, len(entries), status)
    return entries, new_etag, new_modified
