"""Local CSV/Parquet access for demo-friendly API endpoints.

The production path can still use Redis/Trino later. This module keeps the
current API useful from a fresh checkout when `data/silver` and `data/gold`
already exist locally.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("API_DATA_DIR", PROJECT_ROOT / "data"))


class DataUnavailableError(RuntimeError):
    """Raised when a local dataset needed by an endpoint is missing."""


def _first_existing(paths: Iterable[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    tried = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in paths)
    raise DataUnavailableError(f"Local dataset is missing. Expected one of: {tried}. Run `make gold` first.")


def _read_table(base: Path) -> pd.DataFrame:
    path = _table_path(base)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _table_path(base: Path) -> Path:
    csv_path = base.with_suffix(".csv")
    parquet_path = base.with_suffix(".parquet")
    return _first_existing([csv_path, parquet_path])


_TABLE_CACHE: dict[tuple[str, int], pd.DataFrame] = {}


def _read_table_cached(base: Path) -> pd.DataFrame:
    path = _table_path(base)
    cache_key = (str(path), path.stat().st_mtime_ns)
    cached = _TABLE_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()
    # Drop older cached versions of the same file after a local pipeline rebuild.
    for key in list(_TABLE_CACHE):
        if key[0] == str(path):
            _TABLE_CACHE.pop(key, None)
    df = _read_table(base)
    _TABLE_CACHE[cache_key] = df
    return df.copy()


def traffic_features() -> pd.DataFrame:
    return _read_table_cached(DATA_DIR / "gold" / "cleaned_traffic_features")


def traffic_cleaned() -> pd.DataFrame:
    return _read_table_cached(DATA_DIR / "silver" / "traffic_cleaned")


def train_features(horizon: int = 15) -> pd.DataFrame:
    if horizon not in {15, 60}:
        horizon = 15
    return _read_table_cached(DATA_DIR / "gold" / f"train_features_{horizon}m")


def news_events() -> pd.DataFrame:
    return _read_table_cached(DATA_DIR / "silver" / "news_events_normalized")


def normalize_city(city: str | None) -> str | None:
    if city is None:
        return None
    normalized = city.lower().strip().replace("ho_chi_minh", "hcmc").replace("hochiminh", "hcmc")
    if normalized in {"ha_noi", "hà nội", "hanoi"}:
        return "hanoi"
    if normalized in {"tp.hcm", "tphcm", "hcm", "hcmc", "ho chi minh"}:
        return "hcmc"
    return normalized


def latest_by_segment(df: pd.DataFrame, city: str | None = None) -> pd.DataFrame:
    work = df.copy()
    if "city" in work.columns:
        work["city"] = work["city"].map(normalize_city)
        if city:
            work = work[work["city"] == normalize_city(city)]
    if work.empty:
        return work
    work["timestamp"] = pd.to_datetime(work.get("timestamp", work.get("time_bucket")), errors="coerce")
    work = work.dropna(subset=["timestamp"])
    return work.sort_values("timestamp").groupby(["city", "segment_id"], as_index=False).tail(1)


def severity_from_jam(jam_factor: float) -> str:
    if jam_factor >= 8:
        return "CRITICAL"
    if jam_factor >= 6:
        return "HIGH"
    if jam_factor >= 3:
        return "MEDIUM"
    return "LOW"


def synthetic_geojson_line(lat: float, lon: float, offset: float = 0.006) -> list[list[float]]:
    return [[lon - offset, lat - offset], [lon, lat], [lon + offset, lat + offset]]
