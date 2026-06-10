"""Article Parser — trích nội dung sạch từ HTML bằng trafilatura."""

from __future__ import annotations

import logging
import unicodedata
from typing import Optional

import chardet

logger = logging.getLogger(__name__)


def _decode_bytes(raw: bytes) -> str:
    """Giải mã bytes → str với fallback chardet."""
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    detected = chardet.detect(raw[:4096])
    enc = detected.get("encoding") or "utf-8"
    return raw.decode(enc, errors="replace")


def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def extract_content(html_bytes: bytes, url: str = "") -> Optional[str]:
    """Trích nội dung sạch.

    Ưu tiên trafilatura; fallback readability-lxml nếu trafilatura trả None.
    """
    html_str = _normalize_unicode(_decode_bytes(html_bytes))

    # --- Attempt 1: trafilatura ---
    try:
        import trafilatura

        content = trafilatura.extract(
            html_str,
            url=url or None,
            include_comments=False,
            include_tables=False,
            favor_recall=False,
            deduplicate=True,
        )
        if content and len(content.strip()) > 100:
            return _normalize_unicode(content.strip())
    except Exception as exc:
        logger.debug("trafilatura failed for %s: %s", url, exc)

    # --- Attempt 2: readability-lxml ---
    try:
        from readability import Document

        doc = Document(html_str)
        raw = doc.summary(html_partial=True)
        # Bỏ tag HTML còn lại
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        if text and len(text) > 100:
            return _normalize_unicode(text)
    except Exception as exc:
        logger.debug("readability fallback failed for %s: %s", url, exc)

    logger.warning("Both parsers returned empty content for %s", url)
    return None
