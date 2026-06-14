"""System status endpoint backed by local runtime and generated reports."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter

from api.services.local_data import DATA_DIR, PROJECT_ROOT, DataUnavailableError, latest_by_segment, traffic_features
from api.services.model_inference import ModelUnavailableError, model_status, predict_for_segment

router = APIRouter()
START_TIME = time.monotonic()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _endpoint_p95(report: dict[str, Any] | None, path_fragment: str) -> float | None:
    if not report:
        return None
    for item in report.get("endpoints", []):
        if path_fragment in str(item.get("endpoint", "")):
            value = item.get("p95_ms")
            return float(value) if isinstance(value, (int, float)) else None
    return None


def _gold_data_status() -> dict[str, Any]:
    try:
        df = traffic_features().copy()
        latest = latest_by_segment(df)
    except DataUnavailableError as exc:
        return {
            "status": "not_available",
            "error": str(exc),
            "gold_row_count": 0,
            "segment_count": 0,
            "latest_data_timestamp": None,
            "data_freshness_minutes": None,
        }

    df["timestamp"] = pd.to_datetime(df.get("timestamp", df.get("time_bucket")), errors="coerce")
    max_ts = df["timestamp"].dropna().max() if "timestamp" in df else pd.NaT
    latest_iso = None
    freshness_minutes = None
    if pd.notna(max_ts):
        latest_dt = max_ts.to_pydatetime()
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        latest_iso = latest_dt.isoformat()
        freshness_minutes = round(max(0.0, (_utcnow() - latest_dt).total_seconds() / 60.0), 2)

    return {
        "status": "ok" if not latest.empty else "degraded",
        "gold_row_count": int(len(df)),
        "segment_count": int(latest["segment_id"].nunique()) if "segment_id" in latest else 0,
        "latest_data_timestamp": latest_iso,
        "data_freshness_minutes": freshness_minutes,
        "data_source": str((DATA_DIR / "gold").relative_to(PROJECT_ROOT))
        if (DATA_DIR / "gold").is_relative_to(PROJECT_ROOT)
        else str(DATA_DIR / "gold"),
    }


def _model_status_summary() -> dict[str, Any]:
    status = model_status(load_models=True)
    horizons = status.get("horizons", {})
    first_loaded = next((item for item in horizons.values() if item.get("loaded")), None)
    coverage_values: list[float] = []
    try:
        latest = latest_by_segment(traffic_features(), "hanoi").head(20)
        for row in latest.itertuples(index=False):
            try:
                prediction = predict_for_segment(str(row.segment_id), "15m")
            except (ModelUnavailableError, DataUnavailableError):
                continue
            if prediction.required_feature_count:
                coverage_values.append(prediction.available_feature_count / prediction.required_feature_count)
    except DataUnavailableError:
        pass

    avg_coverage = round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else None
    return {
        "loaded": bool(first_loaded),
        "ready": bool(status.get("ready")),
        "model_name": first_loaded.get("model_name") if first_loaded else None,
        "model_family": first_loaded.get("model_class") if first_loaded else None,
        "required_feature_count": first_loaded.get("feature_count") if first_loaded else None,
        "average_feature_coverage_ratio": avg_coverage,
        "feature_coverage_status": "measured_on_latest_hanoi_sample" if coverage_values else "not_measured",
        "horizons": horizons,
    }


def _performance_status() -> dict[str, Any]:
    report = _read_json(PROJECT_ROOT / "docs" / "performance_report.json")
    extra = report.get("extra_metrics", {}) if report else {}
    model_runtime = extra.get("model_runtime", {}) if isinstance(extra, dict) else {}
    api_memory = extra.get("api_memory_after_model_load", {}) if isinstance(extra, dict) else {}
    frontend_build = extra.get("frontend_build", {}) if isinstance(extra, dict) else {}
    if not isinstance(model_runtime, dict):
        model_runtime = {}
    if not isinstance(api_memory, dict):
        api_memory = {}
    if not isinstance(frontend_build, dict):
        frontend_build = {}
    return {
        "last_benchmark_at": report.get("generated_at") if report else None,
        "forecast_p95_ms": _endpoint_p95(report, "/traffic/predict/HN_005?horizon=15m"),
        "dashboard_summary_p95_ms": _endpoint_p95(report, "/dashboard/summary"),
        "predicted_hotspots_p95_ms": _endpoint_p95(report, "/hotspots/predicted"),
        "model_load_time_ms": model_runtime.get("model_load_time_ms"),
        "model_inference_time_ms": model_runtime.get("model_inference_time_ms"),
        "api_memory_after_model_load_mb": api_memory.get("total_rss_mb"),
        "frontend_build_status": frontend_build.get("status"),
        "frontend_build_detail": frontend_build.get("detail"),
        "status": "measured" if report else "not_measured",
    }


def _streaming_status() -> dict[str, Any]:
    report = _read_json(PROJECT_ROOT / "docs" / "streaming_demo_report.json")
    if not report:
        return {
            "kafka_enabled": False,
            "status": "not_enabled_in_demo",
            "last_demo_at": None,
        }
    return {
        "kafka_enabled": bool(report.get("kafka_enabled")),
        "status": report.get("overall_status", "not_available"),
        "last_demo_at": report.get("generated_at"),
        "report": "docs/streaming_demo_report.md",
    }


def _configured(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return bool(lowered) and not lowered.startswith("replace-with")


def _local_stack_status() -> dict[str, Any]:
    return {
        "status": "configured",
        "components": {
            "redis": {"status": "configured", "url": os.getenv("REDIS_URL", "redis://localhost:6379/0")},
            "kafka": {"status": "configured", "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")},
            "schema_registry": {"status": "configured", "url": os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")},
            "minio": {"status": "configured", "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000")},
            "postgres": {"status": "configured", "database": os.getenv("POSTGRES_DB", "traffic_analytics")},
        },
    }


def _cloud_status() -> dict[str, Any]:
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    s3_bucket = os.getenv("S3_BUCKET")
    s3_region = os.getenv("AWS_REGION", "ap-southeast-1")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    s3_configured = _configured(aws_key) and _configured(aws_secret) and _configured(s3_bucket)
    neo4j_configured = _configured(neo4j_uri) and _configured(neo4j_user) and _configured(neo4j_password)
    return {
        "status": "configured" if s3_configured and neo4j_configured else "partial" if s3_configured or neo4j_configured else "not_configured",
        "s3": {
            "status": "configured" if s3_configured else "not_configured",
            "bucket": s3_bucket if _configured(s3_bucket) else None,
            "region": s3_region,
            "warehouse": os.getenv("S3_WAREHOUSE") if _configured(os.getenv("S3_WAREHOUSE")) else None,
            "verification": "configuration_only",
        },
        "neo4j_aura": {
            "status": "configured" if neo4j_configured else "not_configured",
            "uri": neo4j_uri if _configured(neo4j_uri) else None,
            "database": os.getenv("NEO4J_DATABASE") if _configured(os.getenv("NEO4J_DATABASE")) else None,
            "verification": "use scripts/check_neo4j_aura.py for live connectivity",
        },
    }


@router.get("/status")
def get_system_status() -> dict[str, Any]:
    """Return demo-operability status without claiming production telemetry."""
    return {
        "api": {
            "status": "ok",
            "uptime_seconds": round(time.monotonic() - START_TIME, 2),
            "generated_at": _utcnow().isoformat(),
        },
        "data": _gold_data_status(),
        "model": _model_status_summary(),
        "performance": _performance_status(),
        "streaming": _streaming_status(),
        "local_stack": _local_stack_status(),
        "cloud": _cloud_status(),
    }
