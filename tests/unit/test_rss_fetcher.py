"""Unit tests cho RSS Fetcher."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import textwrap
from unittest.mock import patch, MagicMock

import feedparser
import pytest

from ingestion.producers.rss_fetcher import fetch_rss, _is_traffic_related, _normalize_url

ORIGINAL_FEEDPARSER_PARSE = feedparser.parse


# ── Fixture RSS XML ────────────────────────────────────────────────────────────

RSS_FIXTURE = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>VnExpress Giao thông</title>
        <link>https://vnexpress.net/giao-thong</link>
        <item>
          <title>Tai nạn nghiêm trọng trên cầu Nhật Tân</title>
          <link>https://vnexpress.net/tai-nan-cau-nhat-tan-1234.html</link>
          <guid>https://vnexpress.net/tai-nan-cau-nhat-tan-1234.html</guid>
          <description>Va chạm giữa xe tải và xe máy gây ùn tắc kéo dài.</description>
          <pubDate>Thu, 29 May 2026 07:30:00 +0700</pubDate>
        </item>
        <item>
          <title>Ngập sâu tại quận Bình Thạnh sau mưa lớn</title>
          <link>https://vnexpress.net/ngap-binh-thanh-5678.html</link>
          <guid>https://vnexpress.net/ngap-binh-thanh-5678.html</guid>
          <description>Mưa lớn gây ngập sâu nhiều tuyến đường.</description>
          <pubDate>Thu, 29 May 2026 08:00:00 +0700</pubDate>
        </item>
        <item>
          <title>Top 10 món ăn ngon Hà Nội</title>
          <link>https://vnexpress.net/mon-an-hanoi-9999.html</link>
          <guid>https://vnexpress.net/mon-an-hanoi-9999.html</guid>
          <description>Ẩm thực Hà Nội phong phú.</description>
          <pubDate>Thu, 29 May 2026 06:00:00 +0700</pubDate>
        </item>
      </channel>
    </rss>
""")


class TestIsTrafficRelated:
    def test_accident_keyword(self):
        assert _is_traffic_related("Tai nạn xe máy ở Hà Nội", "") is True

    def test_flood_keyword(self):
        assert _is_traffic_related("", "Mưa lớn gây ngập sâu nhiều tuyến đường") is True

    def test_road_work_keyword(self):
        assert _is_traffic_related("Sửa đường Nguyễn Trãi từ ngày mai", "") is True

    def test_unrelated_returns_false(self):
        assert _is_traffic_related("Top 10 món ăn ngon Hà Nội", "Ẩm thực phong phú") is False

    def test_event_keyword(self):
        assert _is_traffic_related("Lễ hội đường phố sắp diễn ra", "") is True


class TestFetchRss:
    def _mock_feedparser(self, xml_text: str, status: int = 200, etag: str = "abc"):
        parsed = ORIGINAL_FEEDPARSER_PARSE(xml_text)
        parsed.status = status
        parsed.etag = etag
        parsed.modified = None
        return parsed

    def test_returns_traffic_entries_only(self):
        import feedparser
        xml = RSS_FIXTURE
        with patch("ingestion.producers.rss_fetcher.feedparser.parse") as mock_parse:
            mock_parse.return_value = self._mock_feedparser(xml)
            entries, _, _ = fetch_rss("http://fake.rss")
        # "Top 10 món ăn" bị lọc ra
        assert len(entries) == 2
        titles = [e["title"] for e in entries]
        assert any("tai nạn" in t.lower() for t in titles)
        assert all("ẩm thực" not in t.lower() for t in titles)

    def test_304_returns_empty(self):
        with patch("ingestion.producers.rss_fetcher.feedparser.parse") as mock_parse:
            fp = MagicMock()
            fp.status = 304
            fp.etag = "same_etag"
            fp.modified = None
            mock_parse.return_value = fp
            entries, etag, _ = fetch_rss("http://fake.rss", last_etag="same_etag")
        assert entries == []

    def test_external_id_is_sha1_hex(self):
        import re
        with patch("ingestion.producers.rss_fetcher.feedparser.parse") as mock_parse:
            mock_parse.return_value = self._mock_feedparser(RSS_FIXTURE)
            entries, _, _ = fetch_rss("http://fake.rss")
        for e in entries:
            assert re.fullmatch(r"[0-9a-f]{40}", e["external_id"])

    def test_no_filter_returns_all(self):
        with patch("ingestion.producers.rss_fetcher.feedparser.parse") as mock_parse:
            mock_parse.return_value = self._mock_feedparser(RSS_FIXTURE)
            entries, _, _ = fetch_rss("http://fake.rss", filter_keywords=False)
        assert len(entries) == 3
