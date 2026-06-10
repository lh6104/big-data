"""Geocoder — Nominatim self-host + Redis cache + snap-to-road confidence."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

import redis as redis_lib
import requests

from infra.settings import settings

logger = logging.getLogger(__name__)

_redis: Optional[redis_lib.Redis] = None
_last_public_call: float = 0.0


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _cache_key(location_str: str) -> str:
    import hashlib
    h = hashlib.sha1(location_str.lower().strip().encode()).hexdigest()[:16]
    return f"geocode:{h}"


def _nominatim_query(location_str: str, base_url: str) -> Optional[dict]:
    params = {
        "q": location_str,
        "format": "json",
        "limit": 1,
        "countrycodes": "vn",
        "accept-language": "vi",
    }
    headers = {"User-Agent": settings.CRAWLER_USER_AGENT}
    try:
        resp = requests.get(
            f"{base_url}/search",
            params=params,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except Exception as exc:
        logger.debug("Nominatim query failed (%s): %s", base_url, exc)
    return None


def geocode(location_str: str) -> Optional[dict]:
    """Chuyển chuỗi địa danh → {lat, lon}.

    Thứ tự: Redis cache → self-hosted Nominatim → public Nominatim (rate 1 req/s).
    """
    if not location_str or not location_str.strip():
        return None

    r = _get_redis()
    cache_key = _cache_key(location_str)

    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    result = _nominatim_query(location_str, settings.NOMINATIM_URL)

    if result is None:
        global _last_public_call
        elapsed = time.time() - _last_public_call
        wait = 1.0 / settings.NOMINATIM_PUBLIC_RATE - elapsed
        if wait > 0:
            time.sleep(wait)
        result = _nominatim_query(location_str, settings.NOMINATIM_PUBLIC_URL)
        _last_public_call = time.time()

    if result:
        r.setex(cache_key, settings.DEDUP_GEOCODE_TTL, json.dumps(result))

    return result


def snap_confidence(snap_distance_m: Optional[float]) -> float:
    """Tính base confidence từ khoảng cách snap-to-road."""
    if snap_distance_m is None:
        return 0.3
    if snap_distance_m < settings.SNAP_HIGH_M:
        return settings.SNAP_CONF_HIGH
    if snap_distance_m < settings.SNAP_MID_M:
        return settings.SNAP_CONF_MID
    return settings.SNAP_CONF_LOW


def _specificity_bonus(location_str: str) -> float:
    """Bonus theo mức cụ thể của địa danh."""
    loc_lower = location_str.lower()
    if any(kw in loc_lower for kw in ("ngã tư", "ngã ba", "cầu ", "hầm ", "nút giao")):
        return 0.15
    if any(kw in loc_lower for kw in ("đường ", "phố ", "đại lộ", "quốc lộ")):
        return 0.05
    return 0.0


def geocode_with_confidence(
    location_str: str,
    city_hint: Optional[str] = None,
    snap_distance_m: Optional[float] = None,
    num_mirrors: int = 0,
) -> tuple[Optional[float], Optional[float], float, str]:
    """Geocode + tính event_confidence.

    Returns:
        (lat, lon, event_confidence, geocode_status)
    """
    query = location_str
    if city_hint and city_hint.lower() not in location_str.lower():
        query = f"{location_str}, {city_hint}"

    result = geocode(query)
    if result is None and city_hint:
        result = geocode(city_hint)
    if result is None:
        return None, None, 0.0, "failed"

    lat, lon = result["lat"], result["lon"]

    conf = snap_confidence(snap_distance_m)
    conf += _specificity_bonus(location_str)
    conf += min(num_mirrors * 0.05, 0.15)
    conf = round(min(conf, 1.0), 3)

    return lat, lon, conf, "ok"
