"""3-layer Deduplicator.

Layer 1 — URL hash      : SHA-1 → Redis SET `seen_urls`         (TTL 30d)
Layer 2 — Title MinHash : normalize → MinHash+LSH (datasketch)  (in-memory, checkpoint Redis)
Layer 3 — Content SimHash: 64-bit SimHash trên 1000 ký tự đầu  (in-memory)
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from typing import Optional

import redis as redis_lib
from datasketch import MinHash, MinHashLSH

from infra.settings import settings

logger = logging.getLogger(__name__)

# ── Vietnamese stopwords nhẹ (bỏ dấu) ────────────────────────────────────────
_STOPWORDS: set[str] = {
    "va", "cua", "la", "trong", "tren", "duoi", "den", "tu", "theo",
    "va", "hoac", "nhung", "cac", "mot", "hai", "ba", "bon", "nam",
    "co", "khong", "duoc", "da", "dang", "se", "rat", "khi", "nhu",
    "the", "nay", "do", "voi", "ve", "cho", "boi", "sau", "truoc",
}


def _remove_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt → ASCII."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _normalize_title(title: str) -> list[str]:
    """Lowercase, bỏ dấu, tokenize, bỏ stopword → list token."""
    t = _remove_diacritics(title.lower())
    tokens = re.findall(r"[a-z0-9]+", t)
    return [tok for tok in tokens if tok not in _STOPWORDS and len(tok) > 1]


def _normalize_url(url: str) -> str:
    """Bỏ tracking params và trailing slash."""
    import urllib.parse as up

    parsed = up.urlparse(url)
    qs = up.parse_qs(parsed.query)
    for key in list(qs.keys()):
        if key.startswith(("utm_", "fbclid", "gclid", "ref", "source")):
            del qs[key]
    clean_query = up.urlencode(qs, doseq=True)
    cleaned = parsed._replace(query=clean_query, fragment="")
    return up.urlunparse(cleaned).rstrip("/")


# ── SimHash ────────────────────────────────────────────────────────────────────

def _simhash(text: str, window: int = settings.SIMHASH_WINDOW) -> int:
    """64-bit SimHash của `window` ký tự đầu text."""
    chunk = text[:window]
    tokens = chunk.lower().split()
    v = [0] * 64
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    bits = sum(1 << i for i in range(64) if v[i] > 0)
    return bits


def _hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ─────────────────────────────────────────────────────────────────────────────


class Deduplicator:
    """Stateful deduplicator với Redis backend cho layer 1."""

    SEEN_URLS_KEY = "dedup:seen_urls"
    MINHASH_KEY_PREFIX = "dedup:minhash:"
    SIMHASH_KEY_PREFIX = "dedup:simhash:"
    SIMHASH_MAX_DIST = 4      # ngưỡng Hamming distance coi là trùng

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self._redis: redis_lib.Redis = redis_lib.from_url(redis_url, decode_responses=False)
        self._lsh = MinHashLSH(
            threshold=settings.MINHASH_THRESHOLD,
            num_perm=settings.MINHASH_NUM_PERM,
        )
        self._minhash_store: dict[str, MinHash] = {}

    # ── Layer 1: URL ──────────────────────────────────────────────────────────

    def _url_hash(self, url: str) -> str:
        normalized = _normalize_url(url)
        return hashlib.sha1(normalized.encode()).hexdigest()

    def _is_url_seen(self, url: str) -> bool:
        h = self._url_hash(url)
        return bool(self._redis.sismember(self.SEEN_URLS_KEY, h))

    def _mark_url_seen(self, url: str) -> None:
        h = self._url_hash(url)
        pipe = self._redis.pipeline()
        pipe.sadd(self.SEEN_URLS_KEY, h)
        pipe.expire(self.SEEN_URLS_KEY, settings.DEDUP_URL_TTL)
        pipe.execute()

    # ── Layer 2: Title MinHash/LSH ────────────────────────────────────────────

    def _build_minhash(self, tokens: list[str]) -> MinHash:
        m = MinHash(num_perm=settings.MINHASH_NUM_PERM)
        for tok in tokens:
            m.update(tok.encode())
        return m

    def _is_title_dup(self, title: str, doc_id: str) -> Optional[str]:
        """Trả về doc_id của bản trùng đầu tiên, hoặc None."""
        tokens = _normalize_title(title)
        if not tokens:
            return None
        m = self._build_minhash(tokens)
        results = self._lsh.query(m)
        return results[0] if results else None

    def _register_title(self, title: str, doc_id: str) -> None:
        tokens = _normalize_title(title)
        if not tokens:
            return
        m = self._build_minhash(tokens)
        if doc_id not in self._minhash_store:
            self._lsh.insert(doc_id, m)
            self._minhash_store[doc_id] = m

    # ── Layer 3: Content SimHash ──────────────────────────────────────────────

    def _content_simhash_key(self, doc_id: str) -> str:
        return f"{self.SIMHASH_KEY_PREFIX}{doc_id}"

    def _is_content_dup(self, content: str) -> Optional[str]:
        """Scan Redis simhash keys và tìm Hamming distance nhỏ hơn ngưỡng."""
        sh = _simhash(content)
        # Scan một phần keys (heuristic — không scan toàn bộ trong prod)
        cursor = 0
        pattern = f"{self.SIMHASH_KEY_PREFIX}*".encode()
        while True:
            cursor, keys = self._redis.scan(cursor, match=pattern, count=200)
            for key in keys:
                val = self._redis.get(key)
                if val is None:
                    continue
                stored = int.from_bytes(val, byteorder="big")
                if _hamming_distance(sh, stored) <= self.SIMHASH_MAX_DIST:
                    doc_id = key.decode().replace(self.SIMHASH_KEY_PREFIX, "")
                    return doc_id
            if cursor == 0:
                break
        return None

    def _register_content(self, content: str, doc_id: str) -> None:
        sh = _simhash(content)
        key = self._content_simhash_key(doc_id)
        self._redis.setex(key, settings.DEDUP_URL_TTL, sh.to_bytes(8, byteorder="big"))

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        url: str,
        title: str,
        content: str,
        doc_id: str,
        source: str,
    ) -> tuple[bool, Optional[str]]:
        """Kiểm tra trùng lặp qua 3 lớp.

        Returns:
            (is_dup, original_doc_id)
        """
        # Layer 1: URL
        if self._is_url_seen(url):
            logger.debug("Layer1 dup URL: %s", url)
            return True, None

        # Layer 2: Title
        dup_id = self._is_title_dup(title, doc_id)
        if dup_id:
            logger.debug("Layer2 dup title: %s ~ %s", doc_id, dup_id)
            return True, dup_id

        # Layer 3: Content SimHash
        if content:
            dup_id = self._is_content_dup(content)
            if dup_id:
                logger.debug("Layer3 dup content simhash: %s ~ %s", doc_id, dup_id)
                return True, dup_id

        return False, None

    def register(self, url: str, title: str, content: str, doc_id: str) -> None:
        """Đăng ký doc_id sau khi xác nhận không trùng."""
        self._mark_url_seen(url)
        self._register_title(title, doc_id)
        if content:
            self._register_content(content, doc_id)

    def update_mirrors(self, original_event: dict, new_source: str) -> dict:
        """Thêm source vào mirrored_sources của bản gốc."""
        mirrors: list = original_event.get("mirrored_sources", [])
        if new_source not in mirrors:
            mirrors.append(new_source)
        original_event["mirrored_sources"] = mirrors
        return original_event
