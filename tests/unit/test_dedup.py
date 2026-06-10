"""Unit tests cho Deduplicator (mock Redis)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch

import pytest

from processing.silver.deduplicator import (
    Deduplicator,
    _normalize_title,
    _simhash,
    _hamming_distance,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_dedup() -> Deduplicator:
    """Tạo Deduplicator với Redis mock (in-memory dict)."""
    store: dict = {}
    sets: dict = {}

    redis_mock = MagicMock()

    def sismember(key, val):
        return val in sets.get(key, set())

    def sadd(key, val):
        sets.setdefault(key, set()).add(val)

    def expire(key, ttl):
        pass

    def pipeline():
        pipe = MagicMock()
        cmds = []
        pipe.sadd.side_effect = lambda k, v: cmds.append(("sadd", k, v))
        pipe.expire.side_effect = lambda k, t: cmds.append(("expire", k, t))
        def execute():
            for cmd in cmds:
                if cmd[0] == "sadd":
                    sets.setdefault(cmd[1], set()).add(cmd[2])
        pipe.execute.side_effect = execute
        return pipe

    def setex(key, ttl, val):
        store[key] = val

    def get(key):
        return store.get(key)

    def scan(cursor, match=None, count=None):
        pattern = (match or b"*").decode().replace("*", "")
        keys = [k.encode() for k in store if k.startswith(pattern.replace("*", ""))]
        return 0, keys

    redis_mock.sismember.side_effect = sismember
    redis_mock.sadd.side_effect = sadd
    redis_mock.expire.side_effect = expire
    redis_mock.pipeline.side_effect = pipeline
    redis_mock.setex.side_effect = setex
    redis_mock.get.side_effect = get
    redis_mock.scan.side_effect = scan

    with patch("processing.silver.deduplicator.redis_lib.from_url", return_value=redis_mock):
        d = Deduplicator(redis_url="redis://fake:6379")
    return d


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestNormalizeTitle:
    def test_removes_diacritics(self):
        tokens = _normalize_title("Tai nạn giao thông")
        assert "tai" in tokens
        assert "nan" in tokens or "nạn" not in " ".join(tokens)

    def test_removes_stopwords(self):
        tokens = _normalize_title("Va chạm và xe máy")
        assert "va" not in tokens
        assert "cham" in tokens
        # Check that we don't have just stopwords
        assert len(tokens) > 0


class TestSimhash:
    def test_same_text_same_hash(self):
        assert _simhash("tai nạn cầu nhật tân") == _simhash("tai nạn cầu nhật tân")

    def test_different_text_different_hash(self):
        h1 = _simhash("tai nạn xe máy hà nội")
        h2 = _simhash("ngập lụt quận 7 tphcm")
        assert h1 != h2

    def test_hamming_distance_zero_for_same(self):
        h = _simhash("test string")
        assert _hamming_distance(h, h) == 0

    def test_hamming_distance_nonzero_for_different(self):
        h1 = _simhash("completely different text a")
        h2 = _simhash("completely different text b c d e f g h i j")
        assert _hamming_distance(h1, h2) > 0


class TestDeduplicator:
    def test_first_article_not_dup(self):
        d = _make_dedup()
        is_dup, orig = d.check(
            url="https://vnexpress.net/article-1.html",
            title="Tai nạn nghiêm trọng trên cầu Nhật Tân",
            content="Va chạm giữa xe tải và xe máy.",
            doc_id="doc1",
            source="vnexpress",
        )
        assert is_dup is False

    def test_same_url_is_dup(self):
        d = _make_dedup()
        url = "https://vnexpress.net/article-1.html"
        d.register(url, "Tai nạn cầu Nhật Tân", "nội dung bài", "doc1")
        is_dup, _ = d.check(url, "Tai nạn cầu Nhật Tân", "nội dung bài", "doc2", "tuoitre")
        assert is_dup is True

    def test_different_url_same_title_is_dup(self):
        d = _make_dedup()
        d.register(
            "https://source1.vn/a.html",
            "Tai nạn nghiêm trọng trên cầu Nhật Tân hà nội",
            "Nội dung dài hơn để test layer 2",
            "doc1",
        )
        is_dup, orig = d.check(
            url="https://source2.vn/b.html",
            title="Tai nạn nghiêm trọng trên cầu Nhật Tân hà nội",
            content="Nội dung dài hơn để test layer 2",
            doc_id="doc2",
            source="source2",
        )
        assert is_dup is True

    def test_update_mirrors(self):
        d = _make_dedup()
        event = {"mirrored_sources": ["tuoitre"]}
        updated = d.update_mirrors(event, "dantri")
        assert "dantri" in updated["mirrored_sources"]
        assert "tuoitre" in updated["mirrored_sources"]

    def test_no_duplicate_mirror(self):
        d = _make_dedup()
        event = {"mirrored_sources": ["tuoitre"]}
        updated = d.update_mirrors(event, "tuoitre")
        assert updated["mirrored_sources"].count("tuoitre") == 1
