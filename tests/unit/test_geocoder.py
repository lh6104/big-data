"""Unit tests cho Geocoder (mock Redis + mock requests)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from unittest.mock import MagicMock, patch

import pytest

from geocoder.geocoder import (
    geocode,
    snap_confidence,
    geocode_with_confidence,
    _specificity_bonus,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_redis(cached_value=None):
    r = MagicMock()
    r.get.return_value = json.dumps(cached_value) if cached_value else None
    r.setex.return_value = True
    return r


def _nominatim_response(lat: float, lon: float):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = [{"lat": str(lat), "lon": str(lon)}]
    return resp


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestGeocodeCache:
    def test_cache_hit_returns_cached(self):
        cached = {"lat": 21.0245, "lon": 105.8412}
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(cached)):
            result = geocode("Hoàn Kiếm, Hà Nội")
        assert result == cached

    def test_cache_miss_calls_nominatim(self):
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get", return_value=_nominatim_response(21.03, 105.85)):
            result = geocode("ngã tư Khuất Duy Tiến, Hà Nội")
        assert result is not None
        assert abs(result["lat"] - 21.03) < 0.001

    def test_empty_string_returns_none(self):
        result = geocode("")
        assert result is None

    def test_whitespace_string_returns_none(self):
        result = geocode("   ")
        assert result is None


class TestNominatimFallback:
    def test_falls_back_to_public_when_self_host_fails(self):
        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "localhost" in url or "127" in url:
                raise Exception("connection refused")
            return _nominatim_response(10.78, 106.70)

        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get", side_effect=mock_get), \
             patch("geocoder.geocoder.time.sleep"):
            result = geocode("Quận 1, TP.HCM")

        assert result is not None
        assert call_count[0] >= 2   # gọi ít nhất 2 lần (self-host + public)

    def test_both_fail_returns_none(self):
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get", side_effect=Exception("network error")), \
             patch("geocoder.geocoder.time.sleep"):
            result = geocode("địa danh không tồn tại xyz")
        assert result is None


class TestSnapConfidence:
    def test_under_50m_is_1(self):
        assert snap_confidence(20.0) == 1.0

    def test_50_to_200m_is_0_7(self):
        assert snap_confidence(100.0) == 0.7

    def test_over_200m_is_0_4(self):
        assert snap_confidence(300.0) == 0.4

    def test_none_is_0_3(self):
        assert snap_confidence(None) == 0.3


class TestSpecificityBonus:
    def test_intersection_gets_bonus(self):
        bonus = _specificity_bonus("ngã tư Khuất Duy Tiến - Nguyễn Trãi")
        assert bonus == 0.15

    def test_bridge_gets_bonus(self):
        bonus = _specificity_bonus("cầu Nhật Tân, Hà Nội")
        assert bonus == 0.15

    def test_road_gets_small_bonus(self):
        bonus = _specificity_bonus("đường Giải Phóng, Hà Nội")
        assert bonus == 0.05

    def test_district_only_no_bonus(self):
        bonus = _specificity_bonus("Quận Hoàn Kiếm, Hà Nội")
        assert bonus == 0.0


class TestGeocodeWithConfidence:
    def test_success_returns_lat_lon_and_ok(self):
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get",
                   return_value=_nominatim_response(21.03, 105.85)):
            lat, lon, conf, status = geocode_with_confidence(
                "cầu Nhật Tân, Hà Nội",
                snap_distance_m=30.0,
            )
        assert status == "ok"
        assert lat == pytest.approx(21.03)
        assert conf >= 1.0   # snap<50m + bridge bonus

    def test_fail_returns_none_and_failed(self):
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get", side_effect=Exception("fail")), \
             patch("geocoder.geocoder.time.sleep"):
            lat, lon, conf, status = geocode_with_confidence("xyz không tồn tại")
        assert status == "failed"
        assert lat is None
        assert conf == 0.0

    def test_mirror_bonus_caps_at_1(self):
        with patch("geocoder.geocoder._get_redis", return_value=_mock_redis(None)), \
             patch("geocoder.geocoder.requests.get",
                   return_value=_nominatim_response(10.78, 106.70)):
            _, _, conf, _ = geocode_with_confidence(
                "ngã tư lớn TP.HCM",
                snap_distance_m=10.0,
                num_mirrors=100,
            )
        assert conf <= 1.0
