"""Normalize raw news JSONL into event signals and aggregate no-leakage features.

Inputs:
- raw/events/*.jsonl
- raw/traffic/*.jsonl, only for the target city/segment/time_bucket grid

Outputs:
- data/silver/news_events_normalized.{parquet,csv}
- data/gold/traffic_event_features.{parquet,csv}
- data/gold/news_event_quality_report.{csv,md}
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = ZoneInfo("UTC")
MODEL_RELEVANCE_THRESHOLD = 0.55

CITY_ALIASES = {
    "hanoi": [
        "hà nội", "ha noi", "nguyễn chí thanh", "nguyen chi thanh", "la thành", "la thanh",
        "nguyễn chánh", "nguyen chanh", "thủ đô", "thu do", "nội bài", "noi bai",
        "vành đai 3", "vanh dai 3", "hoàn kiếm", "hoan kiem", "mỹ đình", "my dinh",
        "thường tín", "thuong tin", "pháp vân", "phap van", "cầu giẽ", "cau gie",
        "nguyễn văn huyên", "nguyen van huyen", "nguyễn xuân linh", "nguyen xuan linh",
    ],
    "hcmc": [
        "tp.hcm", "tp hcm", "tphcm", "hồ chí minh", "ho chi minh", "sài gòn", "sai gon",
        "thủ thiêm", "thu thiem", "cầu sài gòn", "cau sai gon", "tân sơn nhất", "tan son nhat",
        "quận 1", "quan 1", "bến thành", "ben thanh", "cộng hòa", "cong hoa",
        "hàng xanh", "hang xanh", "cầu phú mỹ", "cau phu my", "cầu bình lợi", "cau binh loi",
        "điện biên phủ", "dien bien phu", "nguyễn duy trinh", "nguyen duy trinh",
        "an khánh", "an khanh", "sala", "bùi viện", "bui vien",
    ],
    "danang": ["đà nẵng", "da nang"],
    "haiphong": ["hải phòng", "hai phong", "cát bi", "cat bi"],
    "cantho": ["cần thơ", "can tho"],
    "hue": ["huế", "hue", "phú bài", "phu bai"],
    "dongnai": ["đồng nai", "dong nai", "long thành", "long thanh", "dầu giây", "dau giay", "quốc lộ 51", "quoc lo 51"],
    "lamdong": ["lâm đồng", "lam dong", "đà lạt", "da lat", "đạ huoai", "da huoai"],
    "hatinh": ["hà tĩnh", "ha tinh", "bãi vọt", "bai vot", "hàm nghi", "ham nghi"],
    "quangninh": ["quảng ninh", "quang ninh", "hạ long", "ha long", "móng cái", "mong cai", "cẩm phả", "cam pha"],
    "hungyen": ["hưng yên", "hung yen", "nguyễn văn linh", "nguyen van linh"],
    "ninhbinh": ["ninh bình", "ninh binh", "hoa lư", "hoa lu"],
    "quangtri": ["quảng trị", "quang tri", "cam lộ", "cam lo", "la sơn", "la son", "đông hà", "dong ha"],
    "khanhhoa": ["khánh hòa", "khanh hoa", "nha trang"],
    "tayninh": ["tây ninh", "tay ninh"],
    "daklak": ["đắk lắk", "dak lak", "đăk lăk", "daklak", "buôn ma thuột", "buon ma thuot"],
    "gialai": ["gia lai", "an khê", "an khe", "tô na", "to na"],
    "laocai": ["lào cai", "lao cai"],
    "bacninh": ["bắc ninh", "bac ninh"],
    "nghean": ["nghệ an", "nghe an"],
    "thanhhoa": ["thanh hóa", "thanh hoa"],
    "quangngai": ["quảng ngãi", "quang ngai"],
    "vungtau": ["vũng tàu", "vung tau", "bà rịa", "ba ria"],
    "binhduong": ["bình dương", "binh duong", "thủ dầu một", "thu dau mot"],
    "camau": ["cà mau", "ca mau"],
    "angiang": ["an giang", "núi sam", "nui sam", "châu đốc", "chau doc"],
    "dongthap": ["đồng tháp", "dong thap"],
}

DISTRICT_PATTERNS = [
    r"\bquận\s+[0-9a-zà-ỹ]+",
    r"\bhuyện\s+[a-zà-ỹ\s]{2,25}",
    r"\bthành phố\s+[a-zà-ỹ\s]{2,25}",
    r"\btp\.?\s*[a-zà-ỹ\s]{2,25}",
]

ROAD_PATTERN = re.compile(
    r"\b("
    r"(?:đường|phố|cầu|cao tốc|quốc lộ|tỉnh lộ|đại lộ|vành đai|nút giao|hầm|sân bay|ga)\s+"
    r"[A-ZÀ-Ỹ0-9][A-Za-zÀ-ỹ0-9.\-/]*(?:\s+[A-ZÀ-Ỹ0-9][A-Za-zÀ-ỹ0-9.\-/]*){0,6}"
    r")",
    flags=re.I,
)

CATEGORY_RULES = [
    ("accident", ["tai nạn", "va chạm", "tông", "đâm", "lật xe", "bị cán", "tử vong", "bị thương"]),
    ("congestion", ["ùn tắc", "ùn ứ", "kẹt xe", "tắc đường", "tắc kéo dài", "ách tắc"]),
    ("flood", ["ngập", "ngập úng", "ngập lụt", "nước dâng"]),
    ("weather_disruption", ["mưa lớn", "mưa rất to", "bão", "gió mạnh", "sạt lở", "trơn trượt", "sương mù"]),
    ("roadwork_active", ["thi công", "rào chắn", "phân luồng", "cấm đường", "đóng đường", "sửa đường"]),
    ("airport", ["sân bay", "đường băng", "chuyến bay", "hạ cánh", "cảng hàng không"]),
    ("public_transport", ["xe buýt", "buýt", "metro", "đường sắt đô thị", "tàu điện", "bến xe"]),
    ("enforcement", ["csgt", "xử phạt", "nồng độ cồn", "tước gplx", "camera phạt nguội", "đăng kiểm"]),
    ("planned_event", ["lễ hội", "concert", "sự kiện", "diễu hành", "chạy marathon", "cấm đường phục vụ"]),
    ("roadwork_planned", ["sắp thi công", "sẽ phân luồng", "chuẩn bị rào chắn", "dự kiến thi công"]),
    ("infrastructure_planning", ["quy hoạch", "đề xuất", "sắp mở rộng", "dự án", "đầu tư", "khởi công", "thẩm định", "thi tuyển kiến trúc"]),
]

PLANNING_TERMS = [
    "quy hoạch", "đề xuất", "sắp mở rộng", "dự án", "đầu tư", "khởi công", "thẩm định",
    "thi tuyển kiến trúc", "dự kiến", "chuẩn bị", "sắp thông xe", "sắp về đích",
]
ACTIVE_ROADWORK_TERMS = [
    "đang thi công", "thi công", "phân luồng", "cấm đường", "hạn chế phương tiện", "rào chắn",
    "đóng đường", "sửa đường", "sửa cầu", "lộ trình thay thế", "cải tạo",
]

ACTIVE_CATEGORIES = {
    "accident",
    "congestion",
    "flood",
    "weather_disruption",
    "roadwork_active",
    "airport",
    "public_transport",
    "enforcement",
    "planned_event",
}

NORMALIZED_EVENT_COLUMNS = [
    "event_id", "external_id", "source", "provider", "source_url", "title", "summary_text", "image_url",
    "published_at_utc", "published_at_local", "ingestion_time_utc", "event_time_start", "event_time_end",
    "event_time_source", "event_time_confidence", "city", "district", "road_name", "location_text", "lat", "lon",
    "geo_confidence", "event_category", "event_subtype", "severity_score", "traffic_relevance_score",
    "has_accident", "has_congestion", "has_roadwork", "has_flood", "has_heavy_rain",
    "has_public_transport_issue", "has_airport_issue", "has_enforcement", "has_planned_event",
    "is_relevant_for_traffic_model", "dedup_group_id",
]

AGG_EVENT_COLUMNS = [
    "city", "segment_id", "time_bucket", "news_event_count_1h", "news_event_count_3h", "news_event_count_6h",
    "accident_count_1h", "congestion_news_count_1h", "roadwork_count_24h",
    "weather_disruption_count_6h", "flood_count_6h", "max_event_severity_1h",
    "max_event_severity_6h", "avg_traffic_relevance_score_6h", "has_recent_accident",
    "has_recent_roadwork", "has_recent_flood", "has_major_event", "has_weather_disruption",
]


def iter_jsonl(paths: Iterable[Path]) -> Iterable[dict]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    LOGGER.warning("Skipping invalid JSON in %s:%s: %s", path, line_no, exc)


def normalize_spaces(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = html.unescape(text)
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_image_url(summary: str | None) -> str | None:
    if summary is None or pd.isna(summary):
        return None
    summary = str(summary)
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, flags=re.I)
    return html.unescape(match.group(1)) if match else None


def remove_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def parse_datetime(value: str | None) -> pd.Timestamp | pd.NaT:
    if not value or pd.isna(value):
        return pd.NaT
    return pd.to_datetime(value, utc=True, errors="coerce")


def parse_time_from_url(url: str | None) -> pd.Timestamp | pd.NaT:
    if not url:
        return pd.NaT
    # Bao Xay Dung pattern: ...-192260608151155779.htm -> 2026-06-08 15:11:55 local.
    match = re.search(r"192(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\d*\.htm", url)
    if match:
        yy, month, day, hour, minute, second = map(int, match.groups())
        local_dt = datetime(2000 + yy, month, day, hour, minute, second, tzinfo=LOCAL_TZ)
        return pd.Timestamp(local_dt.astimezone(UTC))
    # Generic Vietnamese article URL date: ...-20260608155717402.htm
    match = re.search(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\d*\.htm", url)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        local_dt = datetime(year, month, day, hour, minute, second, tzinfo=LOCAL_TZ)
        return pd.Timestamp(local_dt.astimezone(UTC))
    return pd.NaT


def parse_time_from_text(text: str) -> pd.Timestamp | pd.NaT:
    now = pd.Timestamp.now(tz=UTC)
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text)
    if match:
        day, month, year = map(int, match.groups())
        local_dt = datetime(year, month, day, 0, 0, tzinfo=LOCAL_TZ)
        return pd.Timestamp(local_dt.astimezone(UTC))
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", text)
    if match:
        day, month = map(int, match.groups())
        local_dt = datetime(now.year, month, day, 0, 0, tzinfo=LOCAL_TZ)
        return pd.Timestamp(local_dt.astimezone(UTC))
    return pd.NaT


def choose_event_time(row: pd.Series) -> tuple[pd.Timestamp, str, str]:
    published = parse_datetime(row.get("published_at"))
    if pd.notna(published):
        return published, "published_at", "high"
    from_url = parse_time_from_url(row.get("source_url"))
    if pd.notna(from_url):
        return from_url, "source_url", "medium"
    text_time = parse_time_from_text(f"{row.get('title', '')} {row.get('summary_text', '')}")
    if pd.notna(text_time):
        return text_time, "title_or_summary", "medium"
    ingestion = parse_datetime(row.get("ingestion_time"))
    if pd.notna(ingestion):
        return ingestion, "ingestion_time", "low"
    return pd.Timestamp.now(tz=UTC), "fallback_now", "low"


def detect_city(text: str, city_hint: str | None) -> tuple[str | None, str | None]:
    haystack = remove_accents(text)
    if city_hint and str(city_hint).strip().lower() not in {"nan", "none", ""}:
        hint = remove_accents(str(city_hint))
        for city, aliases in CITY_ALIASES.items():
            if any(remove_accents(alias) in hint for alias in aliases):
                return city, str(city_hint)
    for city, aliases in CITY_ALIASES.items():
        for alias in aliases:
            if remove_accents(alias) in haystack:
                return city, alias
    return None, None


def extract_district(text: str) -> str | None:
    lower = text.lower()
    for pattern in DISTRICT_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return normalize_spaces(match.group(0))
    return None


def extract_road_name(text: str) -> str | None:
    match = ROAD_PATTERN.search(text)
    return normalize_spaces(match.group(1)) if match else None


def classify_event(text: str) -> tuple[str, str]:
    lower = text.lower()
    active_roadwork = next((term for term in ACTIVE_ROADWORK_TERMS if term in lower), None)
    planning = next((term for term in PLANNING_TERMS if term in lower), None)
    if planning and not active_roadwork:
        if any(term in lower for term in ["đường", "cầu", "cao tốc", "quốc lộ", "vành đai", "hạ tầng", "nút giao"]):
            subtype = planning
            if any(term in lower for term in ["sắp thi công", "dự kiến thi công", "chuẩn bị rào chắn"]):
                return "roadwork_planned", subtype
            return "infrastructure_planning", subtype

    ordered_rules = CATEGORY_RULES
    if active_roadwork:
        ordered_rules = [("roadwork_active", ACTIVE_ROADWORK_TERMS)] + [
            rule for rule in CATEGORY_RULES if rule[0] != "roadwork_active"
        ]
    for category, keywords in ordered_rules:
        if any(keyword in lower for keyword in keywords):
            subtype = next(keyword for keyword in keywords if keyword in lower)
            return category, subtype
    return "unrelated", "unrelated"


def score_severity(category: str, text: str) -> int:
    lower = text.lower()
    if category == "unrelated":
        return 0
    if any(token in lower for token in ["tử vong", "chết", "nhiều người bị thương", "19 người bị thương", "thiệt mạng"]):
        return 5
    if any(token in lower for token in ["ùn tắc kéo dài", "va chạm liên hoàn", "mưa rất to", "ngập úng", "ngập sâu", "sạt lở"]):
        return 4
    if any(token in lower for token in ["tai nạn", "va chạm", "thi công", "phân luồng", "trơn trượt", "cấm đường"]):
        return 3
    if category in {"infrastructure_planning", "roadwork_planned"}:
        return 1 if any(token in lower for token in ["đề xuất", "quy hoạch", "sắp mở rộng"]) else 2
    return 2


def score_relevance(category: str, severity: int, text: str) -> float:
    base = {
        "accident": 0.95,
        "congestion": 0.95,
        "flood": 0.9,
        "weather_disruption": 0.85,
        "roadwork_active": 0.85,
        "airport": 0.65,
        "public_transport": 0.6,
        "enforcement": 0.55,
        "planned_event": 0.55,
        "roadwork_planned": 0.35,
        "infrastructure_planning": 0.25,
        "unrelated": 0.0,
    }.get(category, 0.0)
    if severity >= 4:
        base += 0.05
    if any(token in text.lower() for token in ["tài chính", "ngân hàng", "thi tuyển kiến trúc", "đề xuất"]):
        base -= 0.1
    return float(max(0.0, min(1.0, base)))


def event_duration_hours(category: str) -> int:
    if category in {"roadwork_active", "roadwork_planned", "infrastructure_planning"}:
        return 24
    if category in {"flood", "weather_disruption", "planned_event"}:
        return 6
    return 3


def normalized_title(title: str) -> str:
    text = remove_accents(title)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_dedup_groups(df: pd.DataFrame) -> pd.Series:
    group_ids: list[str] = []
    groups: list[dict] = []
    for row in df.sort_values("event_time_start").itertuples(index=False):
        title_norm = normalized_title(row.title)
        assigned = None
        for group in groups:
            if row.city != group["city"] or row.event_category != group["category"]:
                continue
            if abs((row.event_time_start - group["time"]).total_seconds()) > 24 * 3600:
                continue
            similarity = SequenceMatcher(None, title_norm, group["title_norm"]).ratio()
            same_location = bool(row.location_text and row.location_text == group["location_text"])
            if similarity >= 0.82 or (similarity >= 0.68 and same_location):
                assigned = group["id"]
                break
        if not assigned:
            assigned = hashlib.sha1(f"{row.city}|{row.event_category}|{title_norm[:80]}|{row.event_time_start.date()}".encode()).hexdigest()[:16]
            groups.append(
                {
                    "id": assigned,
                    "city": row.city,
                    "category": row.event_category,
                    "title_norm": title_norm,
                    "location_text": row.location_text,
                    "time": row.event_time_start,
                }
            )
        group_ids.append(assigned)
    return pd.Series(group_ids, index=df.sort_values("event_time_start").index).sort_index()


def read_raw_events(raw_dir: Path) -> pd.DataFrame:
    files = sorted((raw_dir / "events").glob("*.jsonl"))
    if not files:
        return pd.DataFrame()
    return pd.DataFrame(iter_jsonl(files))


def read_bronze_events(output_dir: Path) -> pd.DataFrame:
    bronze_path = output_dir / "bronze" / "news_bronze_raw_enhanced.parquet"
    if not bronze_path.exists():
        return pd.DataFrame()
    bronze = pd.read_parquet(bronze_path)
    if bronze.empty:
        return pd.DataFrame()
    published_at = bronze["published_at_utc"].where(
        bronze.get("published_at_source", pd.Series(index=bronze.index, dtype=object)) != "ingestion_time_fallback",
        bronze["published_at_raw"],
    )
    return pd.DataFrame(
        {
            "source": bronze.get("source"),
            "provider": bronze.get("provider"),
            "event_type": "traffic_news",
            "external_id": bronze.get("external_id"),
            "title": bronze.get("title_raw"),
            "summary": bronze.get("summary_raw"),
            "source_url": bronze.get("source_url"),
            "published_at": published_at,
            "city_hint": bronze.get("city_hint_raw"),
            "ingestion_time": bronze.get("ingestion_time_utc"),
            "published_at_source": bronze.get("published_at_source"),
            "published_at_parse_status": bronze.get("published_at_parse_status"),
            "bronze_record_id": bronze.get("record_id"),
            "bronze_data_quality_flags": bronze.get("data_quality_flags"),
        }
    )


def normalize_events(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=NORMALIZED_EVENT_COLUMNS)
    df = raw.copy()
    for col in ["source", "provider", "event_type", "external_id", "title", "summary", "source_url", "published_at", "city_hint", "ingestion_time"]:
        if col not in df.columns:
            df[col] = None
    df["title"] = df["title"].fillna("").map(normalize_spaces)
    df["summary_text"] = df["summary"].map(normalize_spaces)
    df["image_url"] = df["summary"].map(extract_image_url)
    df["ingestion_time_utc"] = pd.to_datetime(df["ingestion_time"], utc=True, errors="coerce")
    df["published_at_utc"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")

    chosen = df.apply(choose_event_time, axis=1, result_type="expand")
    df["event_time_start"] = pd.to_datetime(chosen[0], utc=True)
    df["event_time_source"] = chosen[1]
    df["event_time_confidence"] = chosen[2]
    df["published_at_local"] = df["published_at_utc"].dt.tz_convert(LOCAL_TZ)

    full_text = (df["title"].fillna("") + " " + df["summary_text"].fillna("")).map(normalize_spaces)
    detected = [detect_city(text, hint) for text, hint in zip(full_text, df["city_hint"])]
    df["city"] = [city for city, _ in detected]
    df["location_text"] = [loc for _, loc in detected]
    df["district"] = full_text.map(extract_district)
    df["road_name"] = full_text.map(extract_road_name)
    df["location_text"] = df["road_name"].fillna(df["district"]).fillna(df["location_text"])
    df["geo_confidence"] = np.select(
        [df["road_name"].notna(), df["district"].notna(), df["city"].notna()],
        [0.75, 0.55, 0.4],
        default=0.0,
    )
    df["lat"] = np.nan
    df["lon"] = np.nan

    classified = [classify_event(text) for text in full_text]
    df["event_category"] = [cat for cat, _ in classified]
    df["event_subtype"] = [subtype for _, subtype in classified]
    df["severity_score"] = [score_severity(cat, text) for cat, text in zip(df["event_category"], full_text)]
    df["traffic_relevance_score"] = [
        score_relevance(cat, sev, text) for cat, sev, text in zip(df["event_category"], df["severity_score"], full_text)
    ]
    duration = df["event_category"].map(event_duration_hours)
    df["event_time_end"] = df["event_time_start"] + pd.to_timedelta(duration, unit="h")

    df["has_accident"] = (df["event_category"] == "accident").astype(int)
    df["has_congestion"] = (df["event_category"] == "congestion").astype(int)
    df["has_roadwork"] = df["event_category"].isin(["roadwork_active", "roadwork_planned"]).astype(int)
    df["has_flood"] = (df["event_category"] == "flood").astype(int)
    df["has_heavy_rain"] = (df["event_category"] == "weather_disruption").astype(int)
    df["has_public_transport_issue"] = (df["event_category"] == "public_transport").astype(int)
    df["has_airport_issue"] = (df["event_category"] == "airport").astype(int)
    df["has_enforcement"] = (df["event_category"] == "enforcement").astype(int)
    df["has_planned_event"] = (df["event_category"] == "planned_event").astype(int)
    df["is_relevant_for_traffic_model"] = (
        df["city"].notna()
        & df["event_category"].isin(ACTIVE_CATEGORIES)
        & (df["traffic_relevance_score"] >= MODEL_RELEVANCE_THRESHOLD)
    ).astype(int)

    df["dedup_group_id"] = build_dedup_groups(df)
    df["event_id"] = df["dedup_group_id"]

    return df[NORMALIZED_EVENT_COLUMNS].sort_values(["event_time_start", "source", "title"]).reset_index(drop=True)


def collapse_semantic_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    ordered = events.sort_values(["dedup_group_id", "traffic_relevance_score", "severity_score"], ascending=[True, False, False])
    return ordered.drop_duplicates("dedup_group_id", keep="first").sort_values("event_time_start").reset_index(drop=True)


def read_traffic_grid(raw_dir: Path, bucket_minutes: int) -> pd.DataFrame:
    files = sorted((raw_dir / "traffic").glob("*.jsonl"))
    if not files:
        return pd.DataFrame(columns=["city", "segment_id", "time_bucket"])
    rows = pd.DataFrame(iter_jsonl(files))
    if rows.empty:
        return pd.DataFrame(columns=["city", "segment_id", "time_bucket"])
    rows["time_bucket"] = pd.to_datetime(rows["time_bucket"], utc=True, errors="coerce").dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    rows["time_bucket"] = rows["time_bucket"].dt.floor(f"{bucket_minutes}min")
    rows["city"] = rows["city"].astype(str).str.lower().replace({"ho_chi_minh": "hcmc"})
    return rows[["city", "segment_id", "time_bucket"]].dropna().drop_duplicates().sort_values(["city", "segment_id", "time_bucket"])


def aggregate_events(events: pd.DataFrame, traffic_grid: pd.DataFrame) -> pd.DataFrame:
    if traffic_grid.empty:
        return pd.DataFrame(columns=AGG_EVENT_COLUMNS)
    if events.empty or "is_relevant_for_traffic_model" not in events.columns:
        features = traffic_grid.copy()
        for col in AGG_EVENT_COLUMNS:
            if col not in features.columns:
                features[col] = 0
        return features[AGG_EVENT_COLUMNS]
    relevant = events[(events["is_relevant_for_traffic_model"] == 1) & events["city"].notna()].copy()
    relevant["event_time_local"] = relevant["event_time_start"].dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)
    rows = []
    for bucket in traffic_grid.itertuples(index=False):
        city_events = relevant[relevant["city"] == bucket.city]
        t = bucket.time_bucket
        w1 = city_events[(city_events["event_time_local"] <= t) & (city_events["event_time_local"] >= t - pd.Timedelta(hours=1))]
        w3 = city_events[(city_events["event_time_local"] <= t) & (city_events["event_time_local"] >= t - pd.Timedelta(hours=3))]
        w6 = city_events[(city_events["event_time_local"] <= t) & (city_events["event_time_local"] >= t - pd.Timedelta(hours=6))]
        w24 = city_events[(city_events["event_time_local"] <= t) & (city_events["event_time_local"] >= t - pd.Timedelta(hours=24))]
        max_sev_1h = int(w1["severity_score"].max()) if not w1.empty else 0
        max_sev_6h = int(w6["severity_score"].max()) if not w6.empty else 0
        rows.append(
            {
                "city": bucket.city,
                "segment_id": bucket.segment_id,
                "time_bucket": t,
                "news_event_count_1h": int(len(w1)),
                "news_event_count_3h": int(len(w3)),
                "news_event_count_6h": int(len(w6)),
                "accident_count_1h": int((w1["event_category"] == "accident").sum()),
                "congestion_news_count_1h": int((w1["event_category"] == "congestion").sum()),
                "roadwork_count_24h": int(w24["event_category"].isin(["roadwork_active", "roadwork_planned"]).sum()),
                "weather_disruption_count_6h": int(w6["event_category"].isin(["weather_disruption", "flood"]).sum()),
                "flood_count_6h": int((w6["event_category"] == "flood").sum()),
                "max_event_severity_1h": max_sev_1h,
                "max_event_severity_6h": max_sev_6h,
                "avg_traffic_relevance_score_6h": float(w6["traffic_relevance_score"].mean()) if not w6.empty else 0.0,
                "has_recent_accident": int((w1["event_category"] == "accident").any()),
                "has_recent_roadwork": int(w24["event_category"].isin(["roadwork_active", "roadwork_planned"]).any()),
                "has_recent_flood": int((w6["event_category"] == "flood").any()),
                "has_major_event": int(max_sev_6h >= 4),
                "has_weather_disruption": int(w6["event_category"].isin(["weather_disruption", "flood"]).any()),
            }
        )
    return pd.DataFrame(rows, columns=AGG_EVENT_COLUMNS)


def build_quality_report(raw: pd.DataFrame, normalized: pd.DataFrame, deduped: pd.DataFrame) -> pd.DataFrame:
    raw_published = raw.get("published_at", pd.Series(dtype=object))
    raw_summary = raw.get("summary", pd.Series(dtype=object))
    raw_city_hint = raw.get("city_hint", pd.Series(dtype=object))
    raw_missing_published = raw_published.isna() | raw_published.astype(str).str.strip().isin(["", "null", "None", "nan"])
    raw_missing_summary = raw_summary.isna() | raw_summary.astype(str).str.strip().isin(["", "null", "None", "nan"])
    raw_missing_city_hint = raw_city_hint.isna() | raw_city_hint.astype(str).str.strip().isin(["", "null", "None", "nan"])
    normalized_missing_city = int(normalized["city"].isna().sum()) if not normalized.empty else 0
    rows = [
        {"metric": "raw_records", "value": len(raw)},
        {"metric": "raw_missing_published_at", "value": int(raw_missing_published.sum())},
        {"metric": "raw_missing_summary", "value": int(raw_missing_summary.sum())},
        {"metric": "raw_city_hint_null_before_detect", "value": int(raw_missing_city_hint.sum())},
        {"metric": "normalized_missing_city_after_detect", "value": normalized_missing_city},
        {"metric": "city_detected_or_retained", "value": int(len(normalized) - normalized_missing_city) if not normalized.empty else 0},
        {"metric": "unrelated_records", "value": int((normalized["event_category"] == "unrelated").sum()) if not normalized.empty else 0},
        {"metric": "events_after_semantic_dedup", "value": len(deduped)},
        {"metric": "events_removed_by_semantic_dedup", "value": int(len(normalized) - len(deduped))},
        {"metric": "model_eligible_records_before_dedup", "value": int(normalized["is_relevant_for_traffic_model"].sum()) if not normalized.empty else 0},
        {"metric": "model_eligible_events_after_dedup", "value": int(deduped["is_relevant_for_traffic_model"].sum()) if not deduped.empty else 0},
    ]
    if not normalized.empty:
        for category, count in normalized["event_category"].value_counts().items():
            rows.append({"metric": f"event_category.{category}", "value": int(count)})
        for city, count in normalized["city"].fillna("missing").value_counts().items():
            rows.append({"metric": f"city.{city}", "value": int(count)})
        for severity, count in normalized["severity_score"].value_counts().sort_index().items():
            rows.append({"metric": f"severity_score.{severity}", "value": int(count)})
        for conf, count in normalized["event_time_confidence"].value_counts().items():
            rows.append({"metric": f"event_time_confidence.{conf}", "value": int(count)})
    return pd.DataFrame(rows)


def write_dataset(df: pd.DataFrame, path_without_suffix: Path) -> None:
    path_without_suffix.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path_without_suffix.with_suffix(".csv"), index=False)
    df.to_parquet(path_without_suffix.with_suffix(".parquet"), index=False)
    LOGGER.info("Wrote %s rows to %s.[csv|parquet]", len(df), path_without_suffix)


def write_report_markdown(report: pd.DataFrame, path: Path) -> None:
    lines = ["# News Event Quality Report", "", "| metric | value |", "| --- | --- |"]
    lines.extend(f"| {row.metric} | {row.value} |" for row in report.itertuples(index=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(raw_dir: Path, output_dir: Path, bucket_minutes: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_bronze_events(output_dir)
    if raw.empty:
        raw = read_raw_events(raw_dir)
    normalized = normalize_events(raw)
    deduped = collapse_semantic_events(normalized)
    traffic_grid = read_traffic_grid(raw_dir, bucket_minutes)
    features = aggregate_events(deduped, traffic_grid)
    report = build_quality_report(raw, normalized, deduped)

    write_dataset(normalized, output_dir / "silver" / "news_events_normalized")
    write_dataset(features, output_dir / "gold" / "traffic_event_features")
    report.to_csv(output_dir / "gold" / "news_event_quality_report.csv", index=False)
    write_report_markdown(report, output_dir / "gold" / "news_event_quality_report.md")
    LOGGER.info("News events normalized=%s deduped=%s feature_rows=%s", len(normalized), len(deduped), len(features))
    return normalized, features


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized news events and no-leakage traffic event features.")
    parser.add_argument("--raw-dir", type=Path, default=Path("raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--bucket-minutes", type=int, default=5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build(args.raw_dir, args.output_dir, args.bucket_minutes)


if __name__ == "__main__":
    main()
