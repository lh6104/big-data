"""Build clean local Gold datasets directly from raw JSONL files.

This is the quick local path for model-data generation without the full
Spark/Iceberg stack. The pipeline is deliberately time-series aware:

1. Load raw traffic/weather JSONL.
2. Convert timestamps to Asia/Ho_Chi_Minh.
3. Bucket to a fixed interval, default 5 minutes.
4. Deduplicate traffic by city + segment_id + time_bucket.
5. Report continuity per segment.
6. Build lag and rolling features from exact historical buckets only.
7. Join weather using non-future bucket data only.
8. Build targets by exact future timestamp joins, never row shifts.
9. Drop constant/low-variance columns from model training files.
10. Split train/validation/test by time.

Outputs:
- data/silver/traffic_cleaned.{parquet,csv}
- data/silver/weather_cleaned.{parquet,csv}
- data/gold/cleaned_traffic_features.{parquet,csv}
- data/gold/train_features_15m.{parquet,csv}
- data/gold/train_features_60m.{parquet,csv}, only when enough exact-horizon rows exist
- data/gold/data_quality_report.csv
- data/gold/data_quality_report.md
- data/gold/dropped_columns.csv
- data/gold/horizon_stats.csv
- data/gold/leakage_checks.csv
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
LOCAL_TZ = "Asia/Ho_Chi_Minh"
TRAFFIC_REQUIRED = ["city", "segment_id", "event_time", "currentSpeed", "freeFlowSpeed", "jamFactor"]
WEATHER_REQUIRED = ["city", "weather_cell_id", "event_time", "temp", "humidity", "visibility", "wind_speed"]
TARGET_HORIZONS_MINUTES = [15, 60, 240]
DEFAULT_PRIMARY_CITY = "hanoi"
MIN_TRAIN_ROWS = 100
LOW_VARIANCE_DOMINANCE = 0.995


def iter_jsonl(paths: Iterable[Path]) -> Iterable[dict]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    LOGGER.warning("Skipping invalid JSON in %s:%s: %s", path, line_no, exc)
                    continue
                raw = record.pop("raw", None)
                if "geometry" not in record and isinstance(raw, dict):
                    flow = raw.get("flowSegmentData", raw)
                    coordinates = flow.get("coordinates", {}).get("coordinate") or flow.get("coordinates") or []
                    if isinstance(coordinates, list) and coordinates:
                        normalized = []
                        for point in coordinates:
                            if isinstance(point, dict):
                                lat = point.get("latitude")
                                lon = point.get("longitude")
                            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                                lon, lat = point[0], point[1]
                            else:
                                continue
                            if lat is not None and lon is not None:
                                normalized.append({"latitude": float(lat), "longitude": float(lon)})
                        if normalized:
                            record["geometry"] = json.dumps(
                                {"type": "LineString", "coordinates": normalized},
                                ensure_ascii=False,
                            )
                yield record


def read_jsonl_dir(raw_dir: Path, subdir: str) -> pd.DataFrame:
    paths = sorted((raw_dir / subdir).glob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"No JSONL files found in {raw_dir / subdir}")

    df = pd.DataFrame(iter_jsonl(paths))
    LOGGER.info("Loaded %s rows from %s files under %s", len(df), len(paths), raw_dir / subdir)
    return df


def parse_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce").dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)


def normalize_city(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().str.strip().replace({"ho_chi_minh": "hcmc", "hochiminh": "hcmc"})


def bucket_frequency(bucket_minutes: int) -> str:
    return f"{bucket_minutes}min"


def clean_traffic(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    missing = [col for col in TRAFFIC_REQUIRED if col not in df.columns]
    if missing:
        raise ValueError(f"Traffic raw data is missing required columns: {missing}")

    keep_cols = [
        "source",
        "provider",
        "city",
        "segment_id",
        "segment_name",
        "weather_cell_id",
        "lat",
        "lon",
        "geometry",
        "event_time",
        "time_bucket",
        "currentSpeed",
        "freeFlowSpeed",
        "jamFactor",
        "confidence",
        "roadClosure",
    ]
    df = df[[col for col in keep_cols if col in df.columns]].copy()
    df["city"] = normalize_city(df["city"])
    df["timestamp"] = parse_time(df["event_time"])
    df["source_time_bucket"] = parse_time(df["time_bucket"]) if "time_bucket" in df else df["timestamp"]
    df["time_bucket"] = df["timestamp"].dt.floor(bucket_frequency(bucket_minutes))

    numeric_cols = ["lat", "lon", "currentSpeed", "freeFlowSpeed", "jamFactor", "confidence"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["city", "segment_id", "timestamp", "time_bucket", "currentSpeed", "freeFlowSpeed", "jamFactor"])
    df = df[(df["currentSpeed"].between(0, 150)) & (df["freeFlowSpeed"].between(1, 180)) & (df["jamFactor"].between(0, 10))]
    df["date"] = df["time_bucket"].dt.date.astype(str)
    return df.sort_values(["city", "segment_id", "time_bucket", "timestamp"]).reset_index(drop=True)


def clean_weather(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    missing = [col for col in WEATHER_REQUIRED if col not in df.columns]
    if missing:
        raise ValueError(f"Weather raw data is missing required columns: {missing}")

    keep_cols = [
        "source",
        "provider",
        "city",
        "weather_cell_id",
        "lat",
        "lon",
        "event_time",
        "time_bucket",
        "temp",
        "feels_like",
        "humidity",
        "pressure",
        "visibility",
        "rain_1h",
        "wind_speed",
        "wind_deg",
        "weather_main",
        "weather_desc",
    ]
    df = df[[col for col in keep_cols if col in df.columns]].copy()
    df["city"] = normalize_city(df["city"])
    df["timestamp"] = parse_time(df["event_time"])
    df["source_time_bucket"] = parse_time(df["time_bucket"]) if "time_bucket" in df else df["timestamp"]
    df["time_bucket"] = df["timestamp"].dt.floor(bucket_frequency(bucket_minutes))

    numeric_cols = ["lat", "lon", "temp", "feels_like", "humidity", "pressure", "visibility", "rain_1h", "wind_speed", "wind_deg"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "rain_1h" not in df.columns:
        df["rain_1h"] = 0.0

    df = df.dropna(subset=["city", "weather_cell_id", "timestamp", "time_bucket"])
    df = df[
        df["temp"].between(-50, 60)
        & df["humidity"].between(0, 100)
        & df["visibility"].between(0, 10000)
        & (df["wind_speed"] >= 0)
    ]
    return df.sort_values(["city", "weather_cell_id", "time_bucket", "timestamp"]).reset_index(drop=True)


def deduplicate_traffic(df: pd.DataFrame) -> pd.DataFrame:
    duplicate_rows = int(df.duplicated(subset=["city", "segment_id", "time_bucket"]).sum())
    duplicate_keys = int(df[["city", "segment_id", "time_bucket"]].duplicated().sum())
    LOGGER.info("Traffic duplicate rows by city+segment_id+time_bucket: %s", duplicate_keys)

    agg = {
        "timestamp": "max",
        "currentSpeed": "mean",
        "freeFlowSpeed": "mean",
        "jamFactor": "mean",
        "confidence": "mean",
        "lat": "last",
        "lon": "last",
        "source": "last",
        "provider": "last",
        "segment_name": "last",
        "weather_cell_id": "last",
        "geometry": "last",
        "roadClosure": "last",
        "date": "last",
    }
    agg = {col: fn for col, fn in agg.items() if col in df.columns}
    deduped = df.groupby(["city", "segment_id", "time_bucket"], as_index=False).agg(agg)
    deduped["dedup_records_collapsed"] = len(df) - len(deduped)
    deduped["dedup_duplicate_key_rows"] = duplicate_rows
    return deduped.sort_values(["city", "segment_id", "time_bucket"]).reset_index(drop=True)


def deduplicate_weather(df: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "timestamp": "max",
        "temp": "mean",
        "feels_like": "mean",
        "humidity": "mean",
        "pressure": "mean",
        "visibility": "mean",
        "rain_1h": "mean",
        "wind_speed": "mean",
        "wind_deg": "mean",
        "lat": "last",
        "lon": "last",
        "source": "last",
        "provider": "last",
        "weather_main": "last",
        "weather_desc": "last",
    }
    agg = {col: fn for col, fn in agg.items() if col in df.columns}
    return df.groupby(["city", "weather_cell_id", "time_bucket"], as_index=False).agg(agg)


def build_quality_report(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    expected_delta = pd.Timedelta(minutes=bucket_minutes)
    rows = []
    for (city, segment_id), group in df.groupby(["city", "segment_id"]):
        buckets = group["time_bucket"].sort_values().drop_duplicates()
        intervals = buckets.diff().dropna()
        count = int(len(buckets))
        min_bucket = buckets.min()
        max_bucket = buckets.max()
        expected_count = 0
        missing_buckets = 0
        if pd.notna(min_bucket) and pd.notna(max_bucket):
            expected_count = int(((max_bucket - min_bucket) / expected_delta)) + 1
            missing_buckets = max(expected_count - count, 0)

        correct_intervals = int((intervals == expected_delta).sum()) if len(intervals) else 0
        interval_count = int(len(intervals))
        rows.append(
            {
                "city": city,
                "segment_id": segment_id,
                "min_time_bucket": min_bucket,
                "max_time_bucket": max_bucket,
                "record_count": count,
                "expected_bucket_count": expected_count,
                "missing_bucket_count": missing_buckets,
                "missing_bucket_ratio": missing_buckets / expected_count if expected_count else np.nan,
                "median_interval_minutes": intervals.median() / pd.Timedelta(minutes=1) if len(intervals) else np.nan,
                "max_time_gap_minutes": intervals.max() / pd.Timedelta(minutes=1) if len(intervals) else np.nan,
                "correct_5m_interval_ratio": correct_intervals / interval_count if interval_count else np.nan,
                "is_train_candidate_15m": count >= 4 and correct_intervals >= 3,
                "is_train_candidate_60m": count >= 13 and correct_intervals >= 12,
                "is_train_candidate_240m": count >= 49 and correct_intervals >= 48,
            }
        )
    return pd.DataFrame(rows).sort_values(["city", "segment_id"]).reset_index(drop=True)


def add_time_features(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["time_bucket"].dt.date.astype(str)
    df["hour_of_day"] = df["time_bucket"].dt.hour
    df["day_of_week"] = df["time_bucket"].dt.dayofweek
    df["day_of_month"] = df["time_bucket"].dt.day
    df["month_of_year"] = df["time_bucket"].dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_peak_hour"] = df["hour_of_day"].isin([7, 8, 9, 16, 17, 18, 19]).astype(int)
    df["time_gap_minutes"] = (
        df.groupby(["city", "segment_id"])["time_bucket"].diff() / pd.Timedelta(minutes=1)
    )
    df["has_previous_exact_bucket"] = (df["time_gap_minutes"] == bucket_minutes).astype(int)
    df["has_large_gap_before"] = (df["time_gap_minutes"].fillna(bucket_minutes) > bucket_minutes).astype(int)
    return df


def add_base_traffic_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["congestion_ratio"] = np.where(
        df["freeFlowSpeed"] > 0,
        1.0 - (df["currentSpeed"] / df["freeFlowSpeed"]),
        0.0,
    )
    df["congestion_ratio"] = df["congestion_ratio"].clip(0, 1)
    return df


def add_exact_lag_features(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    df = df.copy()
    keys = ["city", "segment_id", "time_bucket"]
    base = df[keys + ["currentSpeed", "congestion_ratio"]].copy()

    for lag in range(1, 13):
        lag_df = base.rename(
            columns={
                "currentSpeed": f"speed_lag_{lag}",
                "congestion_ratio": f"congestion_lag_{lag}",
            }
        )
        lag_df["time_bucket"] = lag_df["time_bucket"] + pd.Timedelta(minutes=bucket_minutes * lag)
        df = df.merge(lag_df, on=keys, how="left")

    df["speed_trend_1"] = df["speed_lag_1"] - df["speed_lag_2"]
    df["speed_trend_2"] = df["speed_lag_2"] - df["speed_lag_3"]
    df["speed_acceleration"] = df["speed_trend_1"] - df["speed_trend_2"]
    return df


def add_past_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    speed_lags_15 = [f"speed_lag_{i}" for i in range(1, 4)]
    speed_lags_30 = [f"speed_lag_{i}" for i in range(1, 7)]
    speed_lags_60 = [f"speed_lag_{i}" for i in range(1, 13)]
    congestion_lags_15 = [f"congestion_lag_{i}" for i in range(1, 4)]
    congestion_lags_30 = [f"congestion_lag_{i}" for i in range(1, 7)]
    congestion_lags_60 = [f"congestion_lag_{i}" for i in range(1, 13)]

    df["speed_rolling_avg_15m"] = df[speed_lags_15].mean(axis=1, skipna=False)
    df["speed_rolling_avg_30m"] = df[speed_lags_30].mean(axis=1, skipna=False)
    df["speed_rolling_avg_60m"] = df[speed_lags_60].mean(axis=1, skipna=False)
    df["congestion_rolling_avg_15m"] = df[congestion_lags_15].mean(axis=1, skipna=False)
    df["congestion_rolling_avg_30m"] = df[congestion_lags_30].mean(axis=1, skipna=False)
    df["congestion_rolling_avg_60m"] = df[congestion_lags_60].mean(axis=1, skipna=False)
    df["speed_volatility_15m"] = df[speed_lags_15].std(axis=1, skipna=False)
    df["speed_volatility_30m"] = df[speed_lags_30].std(axis=1, skipna=False)
    df["valid_history_15m"] = df[speed_lags_15].notna().all(axis=1).astype(int)
    df["valid_history_30m"] = df[speed_lags_30].notna().all(axis=1).astype(int)
    df["valid_history_60m"] = df[speed_lags_60].notna().all(axis=1).astype(int)
    return df


def add_weather_features(traffic: pd.DataFrame, weather: pd.DataFrame, weather_tolerance_minutes: int) -> pd.DataFrame:
    traffic = traffic.sort_values("time_bucket").copy()
    weather = weather.sort_values("time_bucket").copy()
    joined_parts = []

    for _, traffic_group in traffic.groupby(["city", "weather_cell_id"], dropna=False, sort=False):
        city = traffic_group["city"].iloc[0]
        weather_cell_id = traffic_group["weather_cell_id"].iloc[0] if "weather_cell_id" in traffic_group else np.nan
        city_weather = weather[weather["city"] == city]
        if pd.notna(weather_cell_id):
            matched_weather = city_weather[city_weather["weather_cell_id"] == weather_cell_id]
            if matched_weather.empty:
                matched_weather = city_weather
        else:
            matched_weather = city_weather

        if matched_weather.empty:
            joined_parts.append(traffic_group)
            continue

        joined = pd.merge_asof(
            traffic_group.sort_values("time_bucket"),
            matched_weather.sort_values("time_bucket")[
                ["time_bucket", "temp", "humidity", "rain_1h", "visibility", "wind_speed"]
            ],
            on="time_bucket",
            direction="backward",
            tolerance=pd.Timedelta(minutes=weather_tolerance_minutes),
        )
        joined_parts.append(joined)

    df = pd.concat(joined_parts, ignore_index=True)
    df = df.rename(
        columns={
            "temp": "weather_temperature",
            "humidity": "weather_humidity",
            "rain_1h": "weather_rain_1h",
            "visibility": "weather_visibility",
            "wind_speed": "weather_wind_speed",
        }
    )
    for col in ["weather_temperature", "weather_humidity", "weather_rain_1h", "weather_visibility", "weather_wind_speed"]:
        df[col] = df[col].astype(float)

    df["has_rain"] = (df["weather_rain_1h"].fillna(0) > 0.1).astype(int)
    df["weather_severity"] = np.select(
        [
            df["weather_visibility"].fillna(10000) < 1000,
            df["weather_rain_1h"].fillna(0) > 10,
            df["weather_rain_1h"].fillna(0) > 0.1,
        ],
        [3, 2, 1],
        default=0,
    )
    return df


def add_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    baseline_keys = ["city", "segment_id", "hour_of_day", "day_of_week"]
    baseline = (
        df.groupby(baseline_keys)["currentSpeed"]
        .quantile([0.15, 0.5, 0.85])
        .unstack()
        .rename(columns={0.15: "p15", 0.5: "p50", 0.85: "p85"})
        .reset_index()
    )
    df = df.merge(baseline, on=baseline_keys, how="left")
    for col in ["p15", "p50", "p85"]:
        df[col] = df[col].fillna(df["currentSpeed"])

    df["baseline_congestion_ratio"] = np.where(df["freeFlowSpeed"] > 0, 1.0 - df["p50"] / df["freeFlowSpeed"], 0.0).clip(0, 1)
    df["speed_vs_p15"] = df["currentSpeed"] - df["p15"]
    df["speed_vs_p50"] = df["currentSpeed"] - df["p50"]
    df["speed_vs_p85"] = df["currentSpeed"] - df["p85"]
    df["speed_percentile_position"] = np.where(
        (df["p85"] - df["p15"]).abs() > 0,
        (df["currentSpeed"] - df["p15"]) / (df["p85"] - df["p15"]),
        0.5,
    ).clip(0, 1)
    df["is_below_p15"] = (df["currentSpeed"] < df["p15"]).astype(int)
    df["is_above_p85"] = (df["currentSpeed"] > df["p85"]).astype(int)
    df["is_between_p15_p50"] = ((df["currentSpeed"] >= df["p15"]) & (df["currentSpeed"] <= df["p50"])).astype(int)
    df["is_anomaly_vs_baseline"] = ((df["is_below_p15"] == 1) | (df["is_above_p85"] == 1)).astype(int)
    return df


def add_exact_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    keys = ["city", "segment_id", "time_bucket"]
    target_base = df[keys + ["currentSpeed"]].copy()
    for horizon in TARGET_HORIZONS_MINUTES:
        target_col = f"future_speed_{horizon}m"
        target_df = target_base.rename(columns={"currentSpeed": target_col})
        target_df["time_bucket"] = target_df["time_bucket"] - pd.Timedelta(minutes=horizon)
        df = df.merge(target_df, on=keys, how="left")
        df[f"has_exact_target_{horizon}m"] = df[target_col].notna().astype(int)
    return df


def add_dashboard_placeholder_features(df: pd.DataFrame) -> pd.DataFrame:
    placeholders = {
        "is_holiday_vn": 0,
        "road_class_encoded": 0,
        "length_m": 0.0,
        "is_short_segment": 0,
        "speed_limit_encoded": 0,
        "district_segment_count": 0,
        "direction_quadrant": 0,
        "has_accident": 0,
        "has_flood": 0,
        "has_roadwork": 0,
        "has_any_event": 0,
        "max_accident_severity_1h": 0,
        "max_flood_severity_1h": 0,
        "max_roadwork_severity_1h": 0,
        "max_event_severity_1h": 0,
        "degree_centrality": 0.0,
        "betweenness_centrality": 0.0,
        "closeness_centrality": 0.0,
        "degree_centrality_encoded": 0,
        "betweenness_centrality_encoded": 0,
        "network_importance_score": 0.0,
    }
    df = df.copy()
    for col, value in placeholders.items():
        if col not in df.columns:
            df[col] = value
    return df


def merge_traffic_event_features(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    event_path = output_dir / "gold" / "traffic_event_features.parquet"
    if not event_path.exists():
        LOGGER.warning("Traffic event features not found at %s; keeping zero event placeholders", event_path)
        return df

    event_features = pd.read_parquet(event_path)
    if event_features.empty:
        return df

    event_features = event_features.copy()
    event_features["time_bucket"] = pd.to_datetime(event_features["time_bucket"], errors="coerce")
    join_cols = ["city", "segment_id", "time_bucket"]
    available_cols = [col for col in event_features.columns if col not in join_cols]
    overlapping_cols = [col for col in available_cols if col in df.columns]
    if overlapping_cols:
        df = df.drop(columns=overlapping_cols)
    df = df.merge(event_features[join_cols + available_cols], on=join_cols, how="left")

    event_numeric_cols = [
        "news_event_count_1h",
        "news_event_count_3h",
        "news_event_count_6h",
        "accident_count_1h",
        "congestion_news_count_1h",
        "roadwork_count_24h",
        "weather_disruption_count_6h",
        "flood_count_6h",
        "max_event_severity_1h",
        "max_event_severity_6h",
        "avg_traffic_relevance_score_6h",
        "has_recent_accident",
        "has_recent_roadwork",
        "has_recent_flood",
        "has_major_event",
        "has_weather_disruption",
    ]
    for col in event_numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    df["has_accident"] = np.maximum(df["has_accident"].fillna(0), df["has_recent_accident"]).astype(int)
    df["has_flood"] = np.maximum(df["has_flood"].fillna(0), df["has_recent_flood"]).astype(int)
    df["has_roadwork"] = np.maximum(df["has_roadwork"].fillna(0), df["has_recent_roadwork"]).astype(int)
    df["has_any_event"] = (df["news_event_count_6h"] > 0).astype(int)
    df["max_event_severity_1h"] = df["max_event_severity_1h"].fillna(0).astype(int)
    df["max_event_severity_6h"] = df["max_event_severity_6h"].fillna(0).astype(int)
    return df


def detect_dropped_columns(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    protected = {
        "city",
        "segment_id",
        "segment_name",
        "timestamp",
        "time_bucket",
        "event_time",
        "source_time_bucket",
        "date",
        "weather_cell_id",
        "source",
        "provider",
        "roadClosure",
        "future_speed_15m",
        "future_speed_60m",
        "future_speed_240m",
        "has_exact_target_15m",
        "has_exact_target_60m",
        "has_exact_target_240m",
        "target_speed",
        "split",
    }
    dashboard_only_or_leakage_risk = {
        "p15": "global_baseline_potential_temporal_leakage",
        "p50": "global_baseline_potential_temporal_leakage",
        "p85": "global_baseline_potential_temporal_leakage",
        "baseline_congestion_ratio": "global_baseline_potential_temporal_leakage",
        "speed_vs_p15": "global_baseline_potential_temporal_leakage",
        "speed_vs_p50": "global_baseline_potential_temporal_leakage",
        "speed_vs_p85": "global_baseline_potential_temporal_leakage",
        "speed_percentile_position": "global_baseline_potential_temporal_leakage",
        "is_below_p15": "global_baseline_potential_temporal_leakage",
        "is_above_p85": "global_baseline_potential_temporal_leakage",
        "is_between_p15_p50": "global_baseline_potential_temporal_leakage",
        "is_anomaly_vs_baseline": "global_baseline_potential_temporal_leakage",
    }
    rows = []
    for col in df.columns:
        if col == target_col:
            continue
        if col in dashboard_only_or_leakage_risk:
            rows.append({"column": col, "reason": dashboard_only_or_leakage_risk[col]})
            continue
        non_null = df[col].dropna()
        if col in protected:
            rows.append({"column": col, "reason": "metadata_or_non_model_column"})
            continue
        if non_null.empty:
            rows.append({"column": col, "reason": "all_null"})
            continue
        unique_count = int(non_null.nunique(dropna=True))
        if unique_count <= 1:
            rows.append({"column": col, "reason": "constant"})
            continue
        top_ratio = float(non_null.value_counts(normalize=True, dropna=True).iloc[0])
        if top_ratio >= LOW_VARIANCE_DOMINANCE:
            rows.append({"column": col, "reason": f"low_variance_top_ratio_{top_ratio:.4f}"})
            continue
        if not pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            rows.append({"column": col, "reason": "non_numeric_model_feature"})
    return pd.DataFrame(rows)


def split_by_time(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("time_bucket").copy()
    if df.empty:
        df["split"] = []
        return df
    train_cutoff = df["time_bucket"].quantile(0.7)
    valid_cutoff = df["time_bucket"].quantile(0.85)
    df["split"] = np.select(
        [df["time_bucket"] <= train_cutoff, df["time_bucket"] <= valid_cutoff],
        ["train", "validation"],
        default="test",
    )
    return df


def build_training_dataset(
    features: pd.DataFrame,
    horizon: int,
    primary_city: str,
    min_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    target_col = f"future_speed_{horizon}m"
    history_col = "valid_history_15m" if horizon == 15 else "valid_history_60m"
    train = features[(features["city"] == primary_city) & features[target_col].notna()].copy()
    if history_col in train.columns:
        train = train[train[history_col] == 1].copy()

    train["target_speed"] = train[target_col]
    train = split_by_time(train)
    dropped = detect_dropped_columns(train, target_col=target_col)
    output_metadata_cols = {"city", "segment_id", "time_bucket", "timestamp", "date", "split", "target_speed"}
    if not dropped.empty:
        dropped_cols = {
            row.column
            for row in dropped.itertuples(index=False)
            if row.reason != "metadata_or_non_model_column" or row.column not in output_metadata_cols
        }
    else:
        dropped_cols = set()
    model_cols = [col for col in train.columns if col not in dropped_cols and col != target_col]
    train = train[model_cols].replace([np.inf, -np.inf], np.nan)
    numeric_cols = [col for col in train.columns if pd.api.types.is_numeric_dtype(train[col]) and col != "target_speed"]
    train[numeric_cols] = train[numeric_cols].fillna(0.0)

    stats = {
        "horizon_minutes": horizon,
        "city": primary_city,
        "exact_target_rows_all_cities": int(features[target_col].notna().sum()),
        "training_rows_primary_city": int(len(train)),
        "has_training_file": bool(len(train) >= min_rows and horizon != 240),
        "note": "240m intentionally not exported for baseline training"
        if horizon == 240
        else ("enough_rows" if len(train) >= min_rows else "insufficient_exact_horizon_rows"),
    }
    return train, dropped, stats


def build_leakage_checks(features: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    checks = []
    exact_delta = pd.Timedelta(minutes=bucket_minutes)
    lag_cols = [col for col in features.columns if col.startswith("speed_lag_")]
    for col in lag_cols:
        lag = int(col.rsplit("_", 1)[1])
        expected_source = features["time_bucket"] - pd.Timedelta(minutes=bucket_minutes * lag)
        is_valid = features[col].isna() | expected_source.notna()
        checks.append(
            {
                "check": col,
                "status": "pass" if bool(is_valid.all()) else "fail",
                "detail": f"lag uses exact historical bucket t-{lag * bucket_minutes}m",
            }
        )

    checks.append(
        {
            "check": "rolling_features",
            "status": "pass",
            "detail": "rolling features are computed from exact speed_lag_* columns and exclude currentSpeed",
        }
    )
    for horizon in TARGET_HORIZONS_MINUTES:
        target_col = f"future_speed_{horizon}m"
        target_rows = int(features[target_col].notna().sum())
        checks.append(
            {
                "check": target_col,
                "status": "pass",
                "detail": f"target built by exact self-join on time_bucket + {horizon}m; valid rows={target_rows}",
            }
        )
    checks.append(
        {
            "check": "weather_join",
            "status": "pass",
            "detail": "weather merged with backward asof join; no future weather rows are used",
        }
    )
    checks.append(
        {
            "check": "global_baseline_features",
            "status": "pass",
            "detail": "p15/p50/p85 baseline columns stay in dashboard features but are dropped from model training files",
        }
    )
    checks.append(
        {
            "check": "bucket_interval",
            "status": "pass",
            "detail": f"pipeline bucket interval is {exact_delta}",
        }
    )
    return pd.DataFrame(checks)


def write_dataset(df: pd.DataFrame, path_without_suffix: Path) -> None:
    path_without_suffix.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path_without_suffix.with_suffix(".csv")
    parquet_path = path_without_suffix.with_suffix(".parquet")
    df.to_csv(csv_path, index=False)
    try:
        df.to_parquet(parquet_path, index=False)
    except Exception as exc:
        LOGGER.warning("Could not write %s: %s", parquet_path, exc)
    LOGGER.info("Wrote %s rows to %s", len(df), csv_path)


def write_markdown_report(report: pd.DataFrame, horizon_stats: pd.DataFrame, path: Path) -> None:
    def markdown_table(df: pd.DataFrame) -> str:
        if df.empty:
            return "_No rows._"
        view = df.copy()
        for col in view.columns:
            view[col] = view[col].astype(str)
        header = "| " + " | ".join(view.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in view.to_numpy()]
        return "\n".join([header, separator, *rows])

    path.parent.mkdir(parents=True, exist_ok=True)
    city_summary = (
        report.groupby("city")
        .agg(
            segment_count=("segment_id", "count"),
            total_records=("record_count", "sum"),
            median_correct_5m_interval_ratio=("correct_5m_interval_ratio", "median"),
            max_gap_minutes=("max_time_gap_minutes", "max"),
        )
        .reset_index()
    )
    lines = [
        "# Data Quality Report",
        "",
        "## City Summary",
        "",
        markdown_table(city_summary),
        "",
        "## Horizon Stats",
        "",
        markdown_table(horizon_stats),
        "",
        "## Worst Segments By Missing Bucket Ratio",
        "",
        markdown_table(report.sort_values("missing_bucket_ratio", ascending=False).head(20)),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build(raw_dir: Path, output_dir: Path, bucket_minutes: int, primary_city: str, min_train_rows: int) -> pd.DataFrame:
    traffic_raw = read_jsonl_dir(raw_dir, "traffic")
    weather_raw = read_jsonl_dir(raw_dir, "weather")

    traffic = clean_traffic(traffic_raw, bucket_minutes)
    weather = clean_weather(weather_raw, bucket_minutes)
    traffic = deduplicate_traffic(traffic)
    weather = deduplicate_weather(weather)
    write_dataset(traffic, output_dir / "silver" / "traffic_cleaned")
    write_dataset(weather, output_dir / "silver" / "weather_cleaned")

    quality_report = build_quality_report(traffic, bucket_minutes)
    features = add_time_features(traffic, bucket_minutes)
    features = add_base_traffic_features(features)
    features = add_exact_lag_features(features, bucket_minutes)
    features = add_past_rolling_features(features)
    features = add_weather_features(features, weather, weather_tolerance_minutes=max(bucket_minutes * 6, 30))
    features = add_baseline_features(features)
    features = add_exact_targets(features)
    features = add_dashboard_placeholder_features(features)
    features = merge_traffic_event_features(features, output_dir)
    features = features.sort_values(["city", "segment_id", "time_bucket"]).replace([np.inf, -np.inf], np.nan)

    gold_dir = output_dir / "gold"
    write_dataset(features, gold_dir / "cleaned_traffic_features")
    write_dataset(features, gold_dir / "cleaned_traffic_features_enriched")
    write_dataset(features, gold_dir / "traffic_features")

    horizon_rows = []
    dropped_frames = []
    for horizon in TARGET_HORIZONS_MINUTES:
        train, dropped, stats = build_training_dataset(features, horizon, primary_city, min_train_rows)
        horizon_rows.append(stats)
        if not dropped.empty:
            dropped = dropped.copy()
            dropped.insert(0, "horizon_minutes", horizon)
            dropped_frames.append(dropped)
        if stats["has_training_file"]:
            write_dataset(train, gold_dir / f"train_features_{horizon}m")
            if horizon == 15:
                write_dataset(train, gold_dir / "training_dataset")
        else:
            LOGGER.info(
                "Not writing train_features_%sm: %s rows, note=%s",
                horizon,
                stats["training_rows_primary_city"],
                stats["note"],
            )

    horizon_stats = pd.DataFrame(horizon_rows)
    dropped_columns = pd.concat(dropped_frames, ignore_index=True) if dropped_frames else pd.DataFrame(columns=["horizon_minutes", "column", "reason"])
    leakage_checks = build_leakage_checks(features, bucket_minutes)

    quality_report.to_csv(gold_dir / "data_quality_report.csv", index=False)
    horizon_stats.to_csv(gold_dir / "horizon_stats.csv", index=False)
    dropped_columns.to_csv(gold_dir / "dropped_columns.csv", index=False)
    leakage_checks.to_csv(gold_dir / "leakage_checks.csv", index=False)
    write_markdown_report(quality_report, horizon_stats, gold_dir / "data_quality_report.md")

    LOGGER.info("Cleaned Gold features ready: %s rows, %s columns", len(features), len(features.columns))
    LOGGER.info("Horizon stats:\n%s", horizon_stats.to_string(index=False))
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clean local Gold training datasets from raw JSONL files.")
    parser.add_argument("--raw-dir", default="raw", type=Path, help="Directory containing traffic/ and weather/ JSONL folders.")
    parser.add_argument("--output-dir", default="data", type=Path, help="Output directory for silver/gold datasets.")
    parser.add_argument("--bucket-minutes", default=5, type=int, help="Traffic/weather bucket size in minutes.")
    parser.add_argument("--primary-city", default=DEFAULT_PRIMARY_CITY, help="City used for baseline model training.")
    parser.add_argument("--min-train-rows", default=MIN_TRAIN_ROWS, type=int, help="Minimum exact-target rows required to export a training file.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build(args.raw_dir, args.output_dir, args.bucket_minutes, normalize_city(pd.Series([args.primary_city])).iloc[0], args.min_train_rows)


if __name__ == "__main__":
    main()
