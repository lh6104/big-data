"""Ingest live sources directly into local raw/ JSONL folders.

This is a lightweight raw-zone collector for short local runs. It does not
replace the original Kafka/Spark lakehouse path; it creates raw JSONL snapshots
that can be consumed by scripts/build_local_gold_dataset.py.

Sources:
- TomTom Flow Segment API -> raw/traffic
- OpenWeatherMap current weather -> raw/weather
- RSS/HTML sources from sources.yaml -> raw/events

API-keyed sources are skipped when their keys are missing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.producers.rss_fetcher import fetch_rss


LOGGER = logging.getLogger(__name__)
TOMTOM_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
LOCAL_TZ = timezone.utc

TRAFFIC_POINTS = [
    {"city": "hanoi", "segment_id": "HN_LIVE_001", "segment_name": "Hoan Kiem", "weather_cell_id": "HN_W1", "lat": 21.0285, "lon": 105.8542},
    {"city": "hanoi", "segment_id": "HN_LIVE_002", "segment_name": "Nguyen Trai", "weather_cell_id": "HN_W2", "lat": 20.9956, "lon": 105.8220},
    {"city": "hanoi", "segment_id": "HN_LIVE_003", "segment_name": "Ring Road 3", "weather_cell_id": "HN_W3", "lat": 21.0060, "lon": 105.7900},
    {"city": "hanoi", "segment_id": "HN_LIVE_004", "segment_name": "Giai Phong", "weather_cell_id": "HN_W4", "lat": 20.9860, "lon": 105.8410},
    {"city": "hanoi", "segment_id": "HN_LIVE_005", "segment_name": "Vo Chi Cong", "weather_cell_id": "HN_W5", "lat": 21.0600, "lon": 105.8100},
    {"city": "hcmc", "segment_id": "HCMC_LIVE_001", "segment_name": "District 1", "weather_cell_id": "HCMC_W1", "lat": 10.7769, "lon": 106.7009},
    {"city": "hcmc", "segment_id": "HCMC_LIVE_002", "segment_name": "Vo Van Kiet", "weather_cell_id": "HCMC_W2", "lat": 10.7550, "lon": 106.6900},
    {"city": "hcmc", "segment_id": "HCMC_LIVE_003", "segment_name": "Dien Bien Phu", "weather_cell_id": "HCMC_W3", "lat": 10.8010, "lon": 106.7150},
    {"city": "hcmc", "segment_id": "HCMC_LIVE_004", "segment_name": "Nguyen Van Linh", "weather_cell_id": "HCMC_W4", "lat": 10.7280, "lon": 106.7050},
    {"city": "hcmc", "segment_id": "HCMC_LIVE_005", "segment_name": "Hanoi Highway", "weather_cell_id": "HCMC_W5", "lat": 10.8230, "lon": 106.7600},
]

WEATHER_POINTS = [
    {"city": "hanoi", "weather_cell_id": "HN_W1", "lat": 21.0285, "lon": 105.8542},
    {"city": "hanoi", "weather_cell_id": "HN_W2", "lat": 20.9956, "lon": 105.8220},
    {"city": "hanoi", "weather_cell_id": "HN_W3", "lat": 21.0060, "lon": 105.7900},
    {"city": "hanoi", "weather_cell_id": "HN_W4", "lat": 20.9860, "lon": 105.8410},
    {"city": "hanoi", "weather_cell_id": "HN_W5", "lat": 21.0600, "lon": 105.8100},
    {"city": "hcmc", "weather_cell_id": "HCMC_W1", "lat": 10.7769, "lon": 106.7009},
    {"city": "hcmc", "weather_cell_id": "HCMC_W2", "lat": 10.7550, "lon": 106.6900},
    {"city": "hcmc", "weather_cell_id": "HCMC_W3", "lat": 10.8010, "lon": 106.7150},
    {"city": "hcmc", "weather_cell_id": "HCMC_W4", "lat": 10.7280, "lon": 106.7050},
    {"city": "hcmc", "weather_cell_id": "HCMC_W5", "lat": 10.8230, "lon": 106.7600},
]

TRAFFIC_NEWS_KEYWORDS = {
    "giao thông",
    "ùn tắc",
    "kẹt xe",
    "tai nạn",
    "va chạm",
    "cao tốc",
    "đường bộ",
    "đường sắt",
    "đường thủy",
    "hàng không",
    "cầu",
    "đường",
    "csgt",
    "atgt",
    "xe",
    "bus",
    "buýt",
    "metro",
    "phân luồng",
    "đăng kiểm",
    "sân bay",
    "nút giao",
    "vận tải",
}


def utc_now() -> datetime:
    return datetime.now(tz=LOCAL_TZ)


def iso_now() -> str:
    return utc_now().isoformat()


def bucket_time(dt: datetime, bucket_minutes: int) -> datetime:
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def append_jsonl(raw_dir: Path, subdir: str, prefix: str, records: list[dict[str, Any]]) -> Path | None:
    if not records:
        return None
    out_dir = raw_dir / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{utc_now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    path = out_dir / filename
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    LOGGER.info("Wrote %s records to %s", len(records), path)
    return path


def last_coordinate(flow: dict[str, Any], fallback: dict[str, Any]) -> tuple[float, float]:
    coords = flow.get("coordinates", {}).get("coordinate") or flow.get("coordinates") or []
    if isinstance(coords, list) and coords:
        point = coords[-1]
        if isinstance(point, dict):
            return float(point.get("latitude", fallback["lat"])), float(point.get("longitude", fallback["lon"]))
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            return float(point[1]), float(point[0])
    return float(fallback["lat"]), float(fallback["lon"])


def collect_tomtom(raw_dir: Path, bucket_minutes: int, timeout: int) -> int:
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        LOGGER.warning("Skipping TomTom: TOMTOM_API_KEY is not set")
        return 0

    records = []
    now = utc_now()
    time_bucket = bucket_time(now, bucket_minutes).isoformat()
    for point in TRAFFIC_POINTS:
        params = {
            "key": api_key,
            "point": f"{point['lat']},{point['lon']}",
            "unit": "KMPH",
            "openLr": "false",
        }
        try:
            response = requests.get(TOMTOM_URL, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            flow = payload.get("flowSegmentData", payload)
            lat, lon = last_coordinate(flow, point)
            current_speed = flow.get("currentSpeed")
            free_flow_speed = flow.get("freeFlowSpeed")
            if current_speed is None or free_flow_speed is None:
                LOGGER.warning("TomTom point returned no speed data: %s", point["segment_id"])
                continue
            if flow.get("jamFactor") is not None:
                jam_factor = flow.get("jamFactor")
            elif free_flow_speed and free_flow_speed > 0:
                jam_factor = round(max(0.0, min(10.0, (1.0 - current_speed / free_flow_speed) * 10.0)), 2)
            else:
                jam_factor = None
            record = {
                "source": "tomtom",
                "provider": "tomtom_flow_segment",
                "city": point["city"],
                "segment_id": point["segment_id"],
                "segment_name": point["segment_name"],
                "weather_cell_id": point["weather_cell_id"],
                "lat": lat,
                "lon": lon,
                "event_time": now.isoformat(),
                "ingestion_time": iso_now(),
                "time_bucket": time_bucket,
                "currentSpeed": current_speed,
                "freeFlowSpeed": free_flow_speed,
                "currentTravelTime": flow.get("currentTravelTime"),
                "freeFlowTravelTime": flow.get("freeFlowTravelTime"),
                "jamFactor": jam_factor,
                "confidence": flow.get("confidence"),
                "roadClosure": flow.get("roadClosure", False),
                "raw": payload,
            }
            records.append(record)
        except Exception as exc:
            LOGGER.warning("TomTom failed for %s: %s", point["segment_id"], exc)
    append_jsonl(raw_dir, "traffic", "traffic_live", records)
    return len(records)


def collect_weather(raw_dir: Path, bucket_minutes: int, timeout: int) -> int:
    api_key = os.getenv("OWM_API_KEY") or os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        LOGGER.warning("Skipping OpenWeatherMap: OWM_API_KEY/OPENWEATHER_API_KEY is not set")
        return 0

    records = []
    now = utc_now()
    time_bucket = bucket_time(now, bucket_minutes).isoformat()
    for point in WEATHER_POINTS:
        params = {"lat": point["lat"], "lon": point["lon"], "appid": api_key, "units": "metric"}
        try:
            response = requests.get(OWM_URL, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            main = payload.get("main", {})
            wind = payload.get("wind", {})
            rain = payload.get("rain", {})
            weather = payload.get("weather", [{}])[0]
            record = {
                "source": "openweathermap",
                "provider": "openweathermap_current",
                "city": point["city"],
                "weather_cell_id": point["weather_cell_id"],
                "lat": point["lat"],
                "lon": point["lon"],
                "event_time": datetime.fromtimestamp(payload.get("dt", int(now.timestamp())), tz=timezone.utc).isoformat(),
                "api_dt": payload.get("dt"),
                "ingestion_time": iso_now(),
                "time_bucket": time_bucket,
                "temp": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "humidity": main.get("humidity"),
                "pressure": main.get("pressure"),
                "weather_id": weather.get("id"),
                "weather_main": weather.get("main"),
                "weather_desc": weather.get("description"),
                "visibility": payload.get("visibility"),
                "rain_1h": rain.get("1h", 0.0),
                "wind_speed": wind.get("speed"),
                "wind_deg": wind.get("deg"),
                "clouds": payload.get("clouds", {}).get("all"),
                "raw": payload,
            }
            records.append(record)
        except Exception as exc:
            LOGGER.warning("OpenWeatherMap failed for %s: %s", point["weather_cell_id"], exc)
    append_jsonl(raw_dir, "weather", "weather_live", records)
    return len(records)


def load_sources(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return [source for source in config.get("sources", []) if source.get("enabled", True)]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def collect_rss(raw_dir: Path, sources: list[dict[str, Any]]) -> int:
    records = []
    now = iso_now()
    for source in sources:
        if source.get("type") != "rss":
            continue
        entries, _, _ = fetch_rss(source["url"], filter_keywords=True)
        for entry in entries:
            records.append(
                {
                    "source": source["name"],
                    "provider": "rss",
                    "event_type": "traffic_news",
                    "external_id": entry.get("external_id"),
                    "title": entry.get("title"),
                    "summary": entry.get("summary"),
                    "source_url": entry.get("link"),
                    "published_at": entry.get("published_at").isoformat() if entry.get("published_at") else None,
                    "city_hint": source.get("city_hint"),
                    "ingestion_time": now,
                }
            )
    append_jsonl(raw_dir, "events", "events_rss", records)
    return len(records)


def collect_html(raw_dir: Path, sources: list[dict[str, Any]], timeout: int) -> int:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    records = []
    headers = {"User-Agent": "TrafficAnalyticsResearchBot/1.0"}
    now = iso_now()

    def is_relevant(title: str, link: str) -> bool:
        text = f"{title} {link}".lower()
        normalized_title = title.strip().lower().lstrip("#").strip()
        blocked_titles = {
            "giao thông",
            "an toàn giao thông",
            "giao thông 24h",
            "chuyện dọc đường",
            "thời sự",
            "đô thị",
            "xe++",
            "trang nhất",
        }
        if len(title.strip()) < 8:
            return False
        if normalized_title in blocked_titles:
            return False
        if link.rstrip("/").count("/") <= 2:
            return False
        article_like = (
            bool(re.search(r"-\d{5,}\.html?$", link))
            or bool(re.search(r"-\d{5,}\.vov$", link))
            or bool(re.search(r"-\d{9,}\.htm$", link))
        )
        if not article_like:
            return False
        return any(keyword in text for keyword in TRAFFIC_NEWS_KEYWORDS)

    global_seen = set()
    for source in sources:
        if source.get("type") != "html":
            continue
        try:
            response = requests.get(source["url"], headers=headers, timeout=timeout)
            response.raise_for_status()
            seen = set()
            if BeautifulSoup:
                soup = BeautifulSoup(response.text, "lxml")
                extracted = []
                for container in soup.select(source.get("article_selector", "article"))[:30]:
                    title_node = container.select_one(source.get("title_selector", "h2,h3"))
                    link_node = container.select_one(source.get("link_selector", "a"))
                    if not link_node or not link_node.get("href"):
                        continue
                    title = title_node.get_text(" ", strip=True) if title_node else link_node.get_text(" ", strip=True)
                    extracted.append((link_node["href"], title))
            else:
                LOGGER.warning("beautifulsoup4 not installed; using simple HTML link fallback for %s", source["name"])
                extracted = [
                    (href, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip())
                    for href, text in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', response.text, flags=re.I | re.S)
                ][:30]

            for href, title in extracted:
                if not href:
                    continue
                link = urljoin(source["url"], href)
                if link in seen or link in global_seen:
                    continue
                if not is_relevant(title, link):
                    continue
                seen.add(link)
                global_seen.add(link)
                records.append(
                    {
                        "source": source["name"],
                        "provider": "html_listing",
                        "event_type": "traffic_news",
                        "external_id": hashlib.sha1(link.encode("utf-8")).hexdigest(),
                        "title": title,
                        "summary": None,
                        "source_url": link,
                        "published_at": None,
                        "city_hint": source.get("city_hint"),
                        "ingestion_time": now,
                    }
                )
        except Exception as exc:
            LOGGER.warning("HTML source failed %s: %s", source.get("name"), exc)
    append_jsonl(raw_dir, "events", "events_html", records)
    return len(records)


def run(args: argparse.Namespace) -> None:
    raw_dir = args.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    load_env_file(Path(".env"))
    load_env_file(Path(".env.local"))
    sources = load_sources(args.sources)
    deadline = time.monotonic() + args.duration_seconds
    cycle = 0

    while True:
        cycle += 1
        LOGGER.info("Starting raw ingest cycle %s", cycle)
        counts = {
            "traffic": collect_tomtom(raw_dir, args.bucket_minutes, args.timeout),
            "weather": collect_weather(raw_dir, args.bucket_minutes, args.timeout),
            "rss_events": collect_rss(raw_dir, sources),
            "html_events": collect_html(raw_dir, sources, args.timeout),
        }
        LOGGER.info("Cycle %s counts: %s", cycle, counts)

        if args.once or time.monotonic() + args.poll_seconds > deadline:
            break
        time.sleep(args.poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest live sources into local raw/ JSONL folders.")
    parser.add_argument("--raw-dir", type=Path, default=Path("raw"))
    parser.add_argument("--sources", type=Path, default=Path("sources.yaml"))
    parser.add_argument("--duration-seconds", type=int, default=600)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--bucket-minutes", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--once", action="store_true", help="Run one cycle only.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args)


if __name__ == "__main__":
    main()
