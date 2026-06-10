"""Tiền xử lý văn bản tiếng Việt."""

from __future__ import annotations

import html
import re
import unicodedata

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]+;")


def clean_html(text: str) -> str:
    """Bỏ tag HTML, decode HTML entity, normalize whitespace."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _ENTITY_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def tokenize(text: str) -> list[str]:
    """Word-tokenize tiếng Việt bằng underthesea (xử lý từ ghép)."""
    try:
        from underthesea import word_tokenize
        return word_tokenize(text, format="text").split()
    except Exception:
        # fallback: split đơn giản
        return text.split()


def preprocess(text: str) -> str:
    """Pipeline đầy đủ: clean HTML → normalize Unicode."""
    return normalize_unicode(clean_html(text))
