"""Build an auditable Bronze news evidence layer from raw JSONL captures.

Inputs:
- raw/events/*.jsonl

Outputs:
- data/bronze/news_bronze_raw_enhanced.parquet
- data/bronze/news_bronze_raw_enhanced.csv
- data/bronze/news_bronze_quality_report.{csv,md}
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
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import pandas as pd


LOGGER = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = ZoneInfo("UTC")
CRAWLER_NAME = "raw_news_ingest_enhancer"
CRAWLER_VERSION = "news_bronze_crawler_v1.0"
SCHEMA_VERSION = "news_bronze_schema_v1"

BRONZE_COLUMNS = [
    "record_id",
    "external_id",
    "source",
    "source_domain",
    "source_section",
    "provider",
    "crawler_name",
    "crawler_version",
    "schema_version",
    "source_url",
    "canonical_url",
    "url_hash",
    "content_hash",
    "title_raw",
    "summary_raw",
    "summary_text",
    "content_raw_optional",
    "html_raw_optional",
    "image_url",
    "published_at_raw",
    "published_at_utc",
    "published_at_local",
    "published_at_source",
    "published_at_parse_status",
    "ingestion_time_utc",
    "crawl_date",
    "fetch_status",
    "http_status",
    "language",
    "encoding",
    "city_hint_raw",
    "location_hint_raw",
    "category_hint_raw",
    "author_raw",
    "tags_raw",
    "raw_payload_json",
    "data_quality_flags",
    "is_exact_duplicate",
    "duplicate_of_record_id",
]

SOURCE_SECTION_BY_SOURCE = {
    "vnexpress_giaothong": "giao_thong",
    "tuoitre_giaothong": "giao_thong",
    "baoxaydung_giaothong": "giaothong",
    "baoxaydung_atgt": "atgt",
    "baoxaydung_gt24h": "gt24h",
    "dantri_thoisux": "thoi_su",
    "thanhnien_thoisux": "thoi_su",
    "vietnamnet_thoisux": "thoi_su",
}

SOURCE_SECTION_MAP = {
    "giaothong": "giaothong",
    "giao_thong": "giao_thong",
    "atgt": "atgt",
    "gt24h": "gt24h",
    "thoisux": "thoi_su",
    "thoi_su": "thoi_su",
}

CITY_RULES = {
    "hanoi": [
        "hà nội",
        "ha noi",
        "thường tín",
        "thuong tin",
        "nguyễn chí thanh",
        "nguyen chi thanh",
        "la thành",
        "la thanh",
        "nguyễn chánh",
        "nguyen chanh",
        "nội bài",
        "noi bai",
        "mỹ đình",
        "my dinh",
        "pháp vân",
        "phap van",
        "cầu giẽ",
        "cau gie",
    ],
    "hcmc": [
        "tp hcm",
        "tp.hcm",
        "tphcm",
        "tp hồ chí minh",
        "tp ho chi minh",
        "hồ chí minh",
        "ho chi minh",
        "sài gòn",
        "sai gon",
        "thủ thiêm",
        "thu thiem",
        "cầu sài gòn",
        "cau sai gon",
        "tân sơn nhất",
        "tan son nhat",
        "cộng hòa",
        "cong hoa",
        "hàng xanh",
        "hang xanh",
        "cầu phú mỹ",
        "cau phu my",
        "điện biên phủ",
        "dien bien phu",
        "nguyễn duy trinh",
        "nguyen duy trinh",
    ],
    "haiphong": ["hải phòng", "hai phong", "cát bi", "cat bi"],
    "danang": ["đà nẵng", "da nang"],
    "cantho": ["cần thơ", "can tho"],
    "hue": ["huế", "hue", "phú bài", "phu bai"],
    "dongnai": ["đồng nai", "dong nai", "long thành", "long thanh", "dầu giây", "dau giay", "quốc lộ 51", "quoc lo 51"],
    "lamdong": ["lâm đồng", "lam dong", "đạ huoai", "da huoai", "cư jút", "cu jut"],
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

CATEGORY_RULES = {
    "accident": ["tai nạn", "va chạm", "tông", "đâm", "cán", "tử vong", "bị thương", "liên hoàn"],
    "congestion": ["ùn tắc", "kẹt xe", "ùn ứ"],
    "roadwork": ["thi công", "phân luồng", "sửa đường", "mở rộng", "sửa cầu", "xuống cấp"],
    "weather": ["mưa lớn", "ngập úng", "trơn trượt", "không khí lạnh", "ngập sâu", "giông", "sạt lở"],
    "airport": ["sân bay", "đường băng", "cảng hàng không"],
    "enforcement": ["csgt", "xử phạt", "nồng độ cồn", "gplx"],
    "public_transport": ["xe buýt", "buýt", "metro", "đường sắt", "tàu hỏa"],
    "planned_event": ["diễn đàn", "lễ hội", "hội báo", "đại biểu"],
    "possible_unrelated": ["ngân hàng", "tài chính", "sim", "thuê bao", "trái cây", "lễ phục"],
}

HTML_TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', flags=re.I)
SCRIPT_STYLE_RE = re.compile(r"<script.*?</script>|<style.*?</style>", flags=re.I | re.S)


def iter_jsonl(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield path, line_no, json.loads(line)
                except json.JSONDecodeError as exc:
                    LOGGER.warning("Skipping invalid JSON in %s:%s: %s", path, line_no, exc)


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "none", "null", "nan"}


def normalize_spaces(value: object) -> str:
    if is_missing(value):
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def sha256_or_none(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def detect_html(value: object) -> bool:
    return False if is_missing(value) else bool(HTML_TAG_RE.search(str(value)))


def clean_summary(summary_raw: object) -> tuple[str | None, str | None, bool]:
    if is_missing(summary_raw):
        return None, None, False
    raw = str(summary_raw)
    image_match = IMG_RE.search(raw)
    image_url = html.unescape(image_match.group(1)) if image_match else None
    text = html.unescape(raw)
    text = SCRIPT_STYLE_RE.sub(" ", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text or None), image_url, bool(image_url)


def canonicalize_url(source_url: object) -> str | None:
    if is_missing(source_url):
        return None
    parsed = urlsplit(str(source_url).strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/")
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in {"fbclid", "gclid", "yclid"}:
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def source_domain(source_url: object) -> str | None:
    if is_missing(source_url):
        return None
    netloc = urlsplit(str(source_url).strip()).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc or None


def source_section(source: object) -> str | None:
    if is_missing(source):
        return None
    source_text = str(source).strip().lower()
    if source_text in SOURCE_SECTION_BY_SOURCE:
        return SOURCE_SECTION_BY_SOURCE[source_text]
    parts = source_text.split("_", 1)
    if len(parts) < 2:
        return None
    suffix = parts[1].strip().lower()
    return SOURCE_SECTION_MAP.get(suffix, suffix or None)


def parse_datetime(value: object) -> pd.Timestamp | pd.NaT:
    if is_missing(value):
        return pd.NaT
    return pd.to_datetime(value, utc=True, errors="coerce")


def valid_url_timestamp(year: int, month: int, day: int, hour: int, minute: int, second: int) -> pd.Timestamp | pd.NaT:
    try:
        local_dt = datetime(year, month, day, hour, minute, second, tzinfo=LOCAL_TZ)
    except ValueError:
        return pd.NaT
    return pd.Timestamp(local_dt.astimezone(UTC))


def parse_timestamp_from_url(source_url: object) -> pd.Timestamp | pd.NaT:
    if is_missing(source_url):
        return pd.NaT
    path = urlsplit(str(source_url)).path

    for match in re.finditer(r"(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", path):
        year, month, day, hour, minute, second = map(int, match.groups())
        parsed = valid_url_timestamp(year, month, day, hour, minute, second)
        if pd.notna(parsed):
            return parsed

    for digit_run in re.findall(r"\d{12,}", path):
        for start in range(0, len(digit_run) - 11):
            yy, month, day, hour, minute, second = (
                int(digit_run[start : start + 2]),
                int(digit_run[start + 2 : start + 4]),
                int(digit_run[start + 4 : start + 6]),
                int(digit_run[start + 6 : start + 8]),
                int(digit_run[start + 8 : start + 10]),
                int(digit_run[start + 10 : start + 12]),
            )
            if yy < 20 or yy > 39:
                continue
            parsed = valid_url_timestamp(2000 + yy, month, day, hour, minute, second)
            if pd.notna(parsed):
                return parsed
    return pd.NaT


def resolve_published_time(row: dict, flags: list[str]) -> tuple[str | None, str | None, str | None, str]:
    published_raw = row.get("published_at")
    parsed = parse_datetime(published_raw)
    if pd.notna(parsed):
        source = "rss" if row.get("provider") == "rss" else "html_meta"
        return parsed.isoformat(), parsed.tz_convert(LOCAL_TZ).isoformat(), source, "ok"

    flags.append("missing_published_at")
    parsed = parse_timestamp_from_url(row.get("source_url"))
    if pd.notna(parsed):
        flags.append("published_at_from_url")
        return parsed.isoformat(), parsed.tz_convert(LOCAL_TZ).isoformat(), "url_timestamp", "parsed_from_url"

    parsed = parse_datetime(row.get("ingestion_time"))
    if pd.notna(parsed):
        flags.append("published_at_fallback_ingestion_time")
        return (
            parsed.isoformat(),
            parsed.tz_convert(LOCAL_TZ).isoformat(),
            "ingestion_time_fallback",
            "fallback_low_confidence",
        )

    flags.append("parse_error")
    return None, None, None, "missing"


def detect_city_and_location(text: str, city_hint: object) -> tuple[str | None, str | None]:
    candidates: list[tuple[str, str]] = []
    hint = normalize_spaces(city_hint)
    if hint:
        candidates.append(("source_hint", hint))
    candidates.append(("text", text))
    for _, haystack_text in candidates:
        haystack = remove_accents(haystack_text)
        for city, aliases in CITY_RULES.items():
            for alias in aliases:
                if remove_accents(alias) in haystack:
                    return city, alias
    return None, None


def detect_categories(text: str) -> str | None:
    haystack = remove_accents(text)
    categories = []
    for category, keywords in CATEGORY_RULES.items():
        if any(remove_accents(keyword) in haystack for keyword in keywords):
            categories.append(category)
    return ";".join(categories) if categories else None


def has_flag(flags: object, flag: str) -> bool:
    if hasattr(flags, "tolist"):
        flags = flags.tolist()
    if isinstance(flags, (list, tuple, set)):
        return flag in flags
    if is_missing(flags):
        return False
    try:
        parsed = json.loads(str(flags))
    except json.JSONDecodeError:
        return flag in str(flags)
    return isinstance(parsed, list) and flag in parsed


def iter_flags(flags: object) -> Iterable[str]:
    if hasattr(flags, "tolist"):
        flags = flags.tolist()
    if isinstance(flags, (list, tuple, set)):
        yield from flags
        return
    if is_missing(flags):
        return
    try:
        parsed = json.loads(str(flags))
    except json.JSONDecodeError:
        return
    if isinstance(parsed, list):
        yield from parsed


def make_record_id(raw_payload_json: str, path: Path, line_no: int) -> str:
    payload = f"{path.name}:{line_no}:{raw_payload_json}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_rows(raw_dir: Path) -> list[dict]:
    files = sorted((raw_dir / "events").glob("*.jsonl"))
    rows: list[dict] = []
    for path, line_no, record in iter_jsonl(files):
        flags: list[str] = []
        raw_payload_json = json.dumps(record, ensure_ascii=False, sort_keys=True)
        title_raw = None if is_missing(record.get("title")) else normalize_spaces(record.get("title"))
        summary_raw = None if is_missing(record.get("summary")) else str(record.get("summary"))
        summary_text, image_url, image_extracted = clean_summary(summary_raw)
        summary_contains_html = detect_html(summary_raw)

        if is_missing(title_raw):
            flags.append("missing_title")
        if is_missing(summary_raw):
            flags.append("missing_summary")
        if summary_contains_html:
            flags.append("summary_contains_html")
        if is_missing(summary_text):
            flags.append("summary_text_empty")
        if image_extracted:
            flags.append("image_extracted")

        canonical_url = canonicalize_url(record.get("source_url"))
        url_hash = sha256_or_none(canonical_url)
        content_key = f"{normalize_spaces(title_raw).lower()}|{normalize_spaces(summary_text).lower()}"
        content_hash = sha256_or_none(content_key)
        ingestion_ts = parse_datetime(record.get("ingestion_time"))
        published_utc, published_local, published_source, published_status = resolve_published_time(record, flags)

        full_text = normalize_spaces(f"{title_raw or ''} {summary_text or ''}")
        city_hint_raw, location_hint_raw = detect_city_and_location(full_text, record.get("city_hint"))
        category_hint_raw = detect_categories(full_text)
        if not city_hint_raw:
            flags.append("city_hint_missing")
        if not category_hint_raw:
            flags.append("category_hint_missing")
        elif "possible_unrelated" in category_hint_raw.split(";"):
            flags.append("possible_unrelated")
        if record.get("provider") == "html_listing" and (is_missing(summary_raw) or is_missing(record.get("published_at"))):
            flags.append("html_listing_partial")

        row = {
            "record_id": make_record_id(raw_payload_json, path, line_no),
            "external_id": None if is_missing(record.get("external_id")) else str(record.get("external_id")),
            "source": None if is_missing(record.get("source")) else str(record.get("source")),
            "source_domain": source_domain(record.get("source_url")),
            "source_section": source_section(record.get("source")),
            "provider": None if is_missing(record.get("provider")) else str(record.get("provider")),
            "crawler_name": CRAWLER_NAME,
            "crawler_version": CRAWLER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "source_url": None if is_missing(record.get("source_url")) else str(record.get("source_url")),
            "canonical_url": canonical_url,
            "url_hash": url_hash,
            "content_hash": content_hash,
            "title_raw": title_raw,
            "summary_raw": summary_raw,
            "summary_text": summary_text,
            "content_raw_optional": record.get("content"),
            "html_raw_optional": record.get("html"),
            "image_url": image_url,
            "published_at_raw": None if is_missing(record.get("published_at")) else str(record.get("published_at")),
            "published_at_utc": published_utc,
            "published_at_local": published_local,
            "published_at_source": published_source,
            "published_at_parse_status": published_status,
            "ingestion_time_utc": ingestion_ts.isoformat() if pd.notna(ingestion_ts) else None,
            "crawl_date": ingestion_ts.date().isoformat() if pd.notna(ingestion_ts) else None,
            "fetch_status": "partial" if "html_listing_partial" in flags else "ok",
            "http_status": record.get("http_status"),
            "language": record.get("language") or "vi",
            "encoding": record.get("encoding") or "utf-8",
            "city_hint_raw": city_hint_raw,
            "location_hint_raw": location_hint_raw,
            "category_hint_raw": category_hint_raw,
            "author_raw": record.get("author"),
            "tags_raw": json.dumps(record.get("tags"), ensure_ascii=False) if isinstance(record.get("tags"), (list, dict)) else record.get("tags"),
            "raw_payload_json": raw_payload_json,
            "data_quality_flags": sorted(set(flags)),
            "is_exact_duplicate": False,
            "duplicate_of_record_id": None,
        }
        rows.append(row)
    return rows


def apply_exact_duplicate_flags(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    first_by_external_id: dict[str, str] = {}
    first_by_url: dict[str, str] = {}
    first_by_content: dict[str, str] = {}
    duplicate_of: list[str | None] = []
    duplicate_flags: list[bool] = []

    for row in df.itertuples(index=False):
        dup_id = None
        if row.external_id and row.external_id in first_by_external_id:
            dup_id = first_by_external_id[row.external_id]
        elif row.url_hash and row.url_hash in first_by_url:
            dup_id = first_by_url[row.url_hash]
        elif row.content_hash and row.content_hash in first_by_content:
            dup_id = first_by_content[row.content_hash]

        duplicate_of.append(dup_id)
        duplicate_flags.append(bool(dup_id))
        if row.external_id and row.external_id not in first_by_external_id:
            first_by_external_id[row.external_id] = row.record_id
        if row.url_hash and row.url_hash not in first_by_url:
            first_by_url[row.url_hash] = row.record_id
        if row.content_hash and row.content_hash not in first_by_content:
            first_by_content[row.content_hash] = row.record_id

    df = df.copy()
    df["is_exact_duplicate"] = duplicate_flags
    df["duplicate_of_record_id"] = duplicate_of
    for idx in df.index[df["is_exact_duplicate"]]:
        flags = list(df.at[idx, "data_quality_flags"])
        flags.append("exact_duplicate")
        df.at[idx, "data_quality_flags"] = sorted(set(flags))
    return df


def missing_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().str.lower().isin(["", "none", "null", "nan"])


def add_metric(rows: list[dict], metric: str, value: object) -> None:
    rows.append({"metric": metric, "value": value})


def build_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    total = len(df)
    if total == 0:
        return pd.DataFrame([{"metric": "total_records", "value": 0}])

    add_metric(rows, "total_records", total)
    for source, count in df["source"].fillna("missing").value_counts().items():
        add_metric(rows, f"records_by_source.{source}", int(count))
    for provider, count in df["provider"].fillna("missing").value_counts().items():
        add_metric(rows, f"records_by_provider.{provider}", int(count))
    for domain, count in df["source_domain"].fillna("missing").value_counts().items():
        add_metric(rows, f"records_by_source_domain.{domain}", int(count))

    missing_title = missing_mask(df["title_raw"])
    missing_summary_raw = missing_mask(df["summary_raw"])
    missing_published_raw = missing_mask(df["published_at_raw"])
    missing_published_after = missing_mask(df["published_at_utc"])
    missing_summary_text = missing_mask(df["summary_text"])
    city_coverage = 1.0 - float(missing_mask(df["city_hint_raw"]).mean())
    category_coverage = 1.0 - float(missing_mask(df["category_hint_raw"]).mean())

    add_metric(rows, "missing_title_rate", f"{missing_title.mean():.4f}")
    add_metric(rows, "missing_summary_rate", f"{missing_summary_raw.mean():.4f}")
    add_metric(rows, "missing_summary_text_rate", f"{missing_summary_text.mean():.4f}")
    add_metric(rows, "missing_published_at_rate_before_fallback", f"{missing_published_raw.mean():.4f}")
    add_metric(rows, "missing_published_at_rate_after_fallback", f"{missing_published_after.mean():.4f}")
    add_metric(rows, "city_hint_raw_coverage", f"{city_coverage:.4f}")
    add_metric(rows, "category_hint_raw_coverage", f"{category_coverage:.4f}")
    add_metric(rows, "duplicate_external_id_count", int(df["external_id"].dropna().duplicated().sum()))
    add_metric(rows, "duplicate_canonical_url_count", int(df["canonical_url"].dropna().duplicated().sum()))
    add_metric(rows, "duplicate_content_hash_count", int(df["content_hash"].dropna().duplicated().sum()))
    add_metric(rows, "summary_html_rate", f"{df['data_quality_flags'].map(lambda flags: has_flag(flags, 'summary_contains_html')).mean():.4f}")
    add_metric(rows, "image_extraction_rate", f"{(~missing_mask(df['image_url'])).mean():.4f}")
    add_metric(rows, "raw_payload_json_coverage", f"{(1.0 - missing_mask(df['raw_payload_json']).mean()):.4f}")
    add_metric(rows, "url_hash_coverage", f"{(1.0 - missing_mask(df['url_hash']).mean()):.4f}")
    add_metric(rows, "content_hash_coverage", f"{(1.0 - missing_mask(df['content_hash']).mean()):.4f}")
    add_metric(rows, "exact_duplicate_records", int(df["is_exact_duplicate"].sum()))

    flag_counts: dict[str, int] = {}
    for flags in df["data_quality_flags"]:
        for flag in iter_flags(flags):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    for flag, count in sorted(flag_counts.items()):
        add_metric(rows, f"data_quality_flags_distribution.{flag}", int(count))

    for source, count in df["published_at_source"].fillna("missing").value_counts().items():
        add_metric(rows, f"published_at_source_distribution.{source}", int(count))
    for status, count in df["published_at_parse_status"].fillna("missing").value_counts().items():
        add_metric(rows, f"published_at_parse_status_distribution.{status}", int(count))

    source_counts = df["source"].fillna("missing").value_counts()
    for rank, (source, count) in enumerate(source_counts.head(10).items(), start=1):
        add_metric(rows, f"top_sources_by_record_count.{rank}.{source}", int(count))
    top_source = source_counts.index[0]
    top_share = float(source_counts.iloc[0] / total)
    if top_share >= 0.5:
        note = f"dominant_source={top_source};share={top_share:.4f};review_source_mix_before_modeling"
    else:
        note = "no_single_source_exceeds_50pct"
    add_metric(rows, "source_imbalance_notes", note)

    return pd.DataFrame(rows)


def write_report_markdown(report: pd.DataFrame, path: Path) -> None:
    lines = ["# News Bronze Quality Report", "", "| metric | value |", "| --- | --- |"]
    lines.extend(f"| {row.metric} | {row.value} |" for row in report.itertuples(index=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(raw_dir: Path, output_dir: Path) -> pd.DataFrame:
    rows = build_rows(raw_dir)
    df = pd.DataFrame(rows, columns=BRONZE_COLUMNS)
    df = apply_exact_duplicate_flags(df)
    df = df[BRONZE_COLUMNS].sort_values(["ingestion_time_utc", "source", "title_raw"], na_position="last").reset_index(drop=True)

    bronze_dir = output_dir / "bronze"
    bronze_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(bronze_dir / "news_bronze_raw_enhanced.csv", index=False)
    df.to_parquet(bronze_dir / "news_bronze_raw_enhanced.parquet", index=False)

    report = build_quality_report(df)
    report.to_csv(bronze_dir / "news_bronze_quality_report.csv", index=False)
    write_report_markdown(report, bronze_dir / "news_bronze_quality_report.md")

    LOGGER.info("Wrote %s Bronze news records to %s", len(df), bronze_dir / "news_bronze_raw_enhanced.parquet")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build auditable Bronze news evidence from raw event JSONL.")
    parser.add_argument("--raw-dir", type=Path, default=Path("raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build(args.raw_dir, args.output_dir)


if __name__ == "__main__":
    main()
