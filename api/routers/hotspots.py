"""Congestion hotspot endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, List, Optional
from datetime import datetime
from functools import lru_cache
import logging
import time
from pathlib import Path

import yaml

from api.services.local_data import DataUnavailableError, PROJECT_ROOT, latest_by_segment, normalize_city, traffic_features
from api.services.model_inference import ModelUnavailableError, normalize_horizon, predict_for_feature_row, predict_for_feature_rows

logger = logging.getLogger(__name__)

router = APIRouter()
PREDICTED_HOTSPOT_CACHE_TTL_SECONDS = 30.0
_PREDICTED_HOTSPOT_CACHE: dict[tuple[str, str, bool], tuple[float, list["PredictedHotspot"]]] = {}


class Hotspot(BaseModel):
    """Congestion hotspot cluster."""
    hotspot_id: str
    cluster_id: int
    city: str
    center_lat: float
    center_lon: float
    radius_km: float
    num_segments: int
    avg_congestion: float
    avg_jam_factor: float
    severity: str  # low, medium, high
    detected_at: datetime


class PredictedHotspot(BaseModel):
    """Segment-level prototype predicted congestion risk."""
    segment_id: str
    road_name: str
    city: str
    current_speed: float
    predicted_speed: float
    free_flow_speed: float
    current_speed_kph: float
    predicted_speed_kph: float
    free_flow_speed_kph: float
    speed_drop_pct: float
    predicted_free_flow_ratio: Optional[float] = None
    risk_score: float
    horizon: str
    risk_level: str
    triggered_rules: list[str]
    reason: str
    context_explanation: dict[str, Any]
    latest_timestamp: Optional[str] = None
    geometry: Optional[Any] = None
    model_name: str
    required_feature_count: int
    available_feature_count: int
    filled_feature_count: int
    feature_coverage_ratio: float
    is_fallback: bool
    scoring_profile: str = "prototype_explainable_risk_scoring_v1"


DEFAULT_RISK_CONFIG = {
    "low_speed_kph": 20,
    "free_flow_ratio_threshold": 0.5,
    "speed_drop_pct_threshold": 30,
    "high_risk_threshold": 60,
    "critical_risk_threshold": 80,
    "weights": {
        "low_speed": 35,
        "free_flow_ratio": 25,
        "speed_drop": 20,
        "current_jam": 10,
        "context_multiplier": 10,
    },
}


@lru_cache(maxsize=1)
def risk_config() -> dict[str, Any]:
    """Load transparent risk scoring thresholds for the prototype endpoint."""
    path = PROJECT_ROOT / "config" / "risk_scoring.yaml"
    if not path.exists():
        return DEFAULT_RISK_CONFIG
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    config = {**DEFAULT_RISK_CONFIG, **loaded}
    config["weights"] = {**DEFAULT_RISK_CONFIG["weights"], **(loaded.get("weights") or {})}
    return config


def _float_attr(row: Any, name: str, default: float = 0.0) -> float:
    value = row.get(name, default) if hasattr(row, "get") else getattr(row, name, default)
    try:
        if value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool_attr(row: Any, name: str) -> bool:
    value = row.get(name, False) if hasattr(row, "get") else getattr(row, name, False)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _context_component(row: Any) -> tuple[float, dict[str, Any]]:
    rain_1h = _float_attr(row, "weather_rain_1h")
    weather_severity = _float_attr(row, "weather_severity")
    heavy_rain = _bool_attr(row, "has_rain") and (rain_1h >= 10 or weather_severity >= 2)
    nearby_event_count = _float_attr(row, "news_event_count_1h")
    nearby_accident_count = _float_attr(row, "accident_count_1h")
    nearby_roadwork_count = _float_attr(row, "roadwork_count_24h")
    event_severity = _float_attr(row, "max_event_severity_1h")
    event_risk_score = min(1.0, (nearby_accident_count * 0.45) + (nearby_event_count * 0.15) + (event_severity / 10.0))
    weather_risk_score = min(1.0, (weather_severity / 10.0) + (0.35 if heavy_rain else 0.0))
    component = max(event_risk_score, weather_risk_score)
    return component, {
        "weather": f"heavy_rain_flag={str(heavy_rain).lower()}, rain_1h_mm={round(rain_1h, 3)}, weather_severity={round(weather_severity, 3)}",
        "event": (
            f"nearby_event_count_1h={int(nearby_event_count)}, "
            f"nearby_accident_count_1h={int(nearby_accident_count)}, "
            f"nearby_roadwork_count_24h={int(nearby_roadwork_count)}, "
            f"event_severity_max_1h={round(event_severity, 3)}, "
            f"event_risk_score={round(event_risk_score, 3)}"
        ),
        "event_context_status": "prototype_from_gold_event_features",
        "weather_context_status": "prototype_from_gold_weather_features",
    }


def _risk_level(score: float, config: dict[str, Any]) -> str:
    critical = float(config["critical_risk_threshold"])
    high = float(config["high_risk_threshold"])
    if score >= critical:
        return "critical"
    if score >= high:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _score_prediction(row: Any, prediction: Any) -> dict[str, Any]:
    config = risk_config()
    weights = config["weights"]
    predicted_speed = float(prediction.predicted_speed)
    current_speed = _float_attr(row, "currentSpeed", prediction.current_speed or 0.0)
    free_flow_speed = _float_attr(row, "freeFlowSpeed")
    current_jam = _float_attr(row, "jamFactor", prediction.current_jam_factor or 0.0)
    low_speed_threshold = float(config["low_speed_kph"])
    ratio_threshold = float(config["free_flow_ratio_threshold"])
    drop_threshold = float(config["speed_drop_pct_threshold"])

    predicted_ratio = predicted_speed / free_flow_speed if free_flow_speed > 0 else None
    speed_drop_pct = ((current_speed - predicted_speed) / current_speed * 100.0) if current_speed > 0 else 0.0
    low_speed_component = 1.0 if predicted_speed < low_speed_threshold else 0.0
    free_flow_component = 1.0 if predicted_ratio is not None and predicted_ratio < ratio_threshold else 0.0
    speed_drop_component = 1.0 if speed_drop_pct > drop_threshold else 0.0
    current_jam_component = min(max(current_jam / 10.0, 0.0), 1.0)
    context_component, context = _context_component(row)

    score = (
        float(weights["low_speed"]) * low_speed_component
        + float(weights["free_flow_ratio"]) * free_flow_component
        + float(weights["speed_drop"]) * speed_drop_component
        + float(weights["current_jam"]) * current_jam_component
        + float(weights["context_multiplier"]) * context_component
    )
    score = min(max(score, 0.0), 100.0)
    triggered_rules: list[str] = []
    if low_speed_component:
        triggered_rules.append("predicted_speed_below_20")
    if free_flow_component:
        triggered_rules.append("predicted_speed_below_half_free_flow")
    if speed_drop_component:
        triggered_rules.append("speed_drop_above_30pct")
    if current_jam_component >= 0.6:
        triggered_rules.append("current_jam_factor_high")
    if context_component > 0:
        triggered_rules.append("context_risk_signal_present")

    feature_coverage_ratio = (
        prediction.available_feature_count / prediction.required_feature_count
        if prediction.required_feature_count
        else 0.0
    )
    context.update(
        {
            "segment": (
                f"road_class={row.get('road_class_encoded', 'unknown') if hasattr(row, 'get') else getattr(row, 'road_class_encoded', 'unknown')}, "
                f"district={row.get('district', 'unknown') if hasattr(row, 'get') else getattr(row, 'district', 'unknown')}"
            ),
            "forecast": (
                f"horizon={prediction.horizon}, model={prediction.model_name}, "
                f"partial_feature_fill={str(prediction.filled_feature_count > 0).lower()}"
            ),
            "feature_coverage_ratio": round(feature_coverage_ratio, 4),
        }
    )
    return {
        "current_speed": current_speed,
        "predicted_speed": predicted_speed,
        "free_flow_speed": free_flow_speed,
        "speed_drop_pct": speed_drop_pct,
        "predicted_free_flow_ratio": predicted_ratio,
        "risk_score": score,
        "risk_level": _risk_level(score, config),
        "triggered_rules": triggered_rules,
        "context_explanation": context,
        "feature_coverage_ratio": feature_coverage_ratio,
    }


@router.get("", response_model=List[Hotspot])
def get_hotspots(
    city: str = Query("hanoi", description="Filter by city"),
    severity: str = Query(None, description="Filter by severity (low, medium, high)")
):
    """Get current congestion hotspots.

    Args:
        city: City code
        severity: Optional severity filter

    Returns:
        List of detected hotspot clusters
    """
    city = normalize_city(city)
    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    congested = latest[latest["jamFactor"] >= 3].copy()
    if congested.empty:
        return []

    congested["cluster_id"] = congested["segment_name"].fillna(congested["segment_id"]).astype(str).str[:12]
    hotspots = []
    for idx, (_, group) in enumerate(congested.groupby("cluster_id")):
        avg_jam = float(group["jamFactor"].mean())
        sev = "critical" if avg_jam >= 8 else "high" if avg_jam >= 6 else "medium"
        hotspots.append(
            Hotspot(
                hotspot_id=f"hotspot_{city}_{idx}",
                cluster_id=idx,
                city=city or str(group["city"].iloc[0]),
                center_lat=round(float(group["lat"].mean()), 6),
                center_lon=round(float(group["lon"].mean()), 6),
                radius_km=0.8,
                num_segments=int(group["segment_id"].nunique()),
                avg_congestion=round(float((group["freeFlowSpeed"] - group["currentSpeed"]).clip(lower=0).mean()), 3),
                avg_jam_factor=round(avg_jam, 2),
                severity=sev,
                detected_at=group["timestamp"].max().to_pydatetime(),
            )
        )

    if severity:
        hotspots = [h for h in hotspots if h.severity == severity.lower()]

    return sorted(hotspots, key=lambda item: item.avg_jam_factor, reverse=True)


@router.get("/predicted", response_model=List[PredictedHotspot])
def get_predicted_hotspots(
    city: str = Query("hanoi", description="Filter by city"),
    horizon: str = Query("15m", description="Forecast horizon (15m or 60m)"),
    include_geometry: bool = Query(False, description="Include raw segment geometry in each predicted hotspot response"),
):
    """Get prototype explainable risk scores from local Gold data and forecast output.

    This endpoint is designed for capstone decision-support demonstration. It is
    not a calibrated production incident or congestion risk engine.
    """
    city = normalize_city(city)
    try:
        horizon = normalize_horizon(horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cache_key = (city, horizon, include_geometry)
    cached = _PREDICTED_HOTSPOT_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] <= PREDICTED_HOTSPOT_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    hotspots: list[PredictedHotspot] = []
    try:
        predictions = {prediction.segment_id: prediction for prediction in predict_for_feature_rows(latest, horizon)}
    except (ModelUnavailableError, DataUnavailableError):
        raise
    except Exception as exc:  # pragma: no cover - fallback keeps prototype endpoint demoable
        logger.warning("Batch predicted hotspot inference failed, falling back to per-row inference: %s", exc)
        predictions = {}

    for _, row in latest.iterrows():
        segment_id = str(row.get("segment_id"))
        try:
            prediction = predictions.get(segment_id) or predict_for_feature_row(row, horizon)
        except (ModelUnavailableError, DataUnavailableError) as exc:
            logger.warning("Skipping predicted hotspot for %s: %s", segment_id, exc)
            continue
        except Exception as exc:  # pragma: no cover - defensive per-segment isolation
            logger.warning("Skipping predicted hotspot for %s after unexpected error: %s", segment_id, exc)
            continue

        if prediction.predicted_speed is None:
            continue

        risk = _score_prediction(row, prediction)
        if risk["risk_level"] == "low":
            continue

        geometry = None
        if include_geometry:
            geometry = row.get("geometry")
            if geometry != geometry:  # NaN guard without importing pandas here.
                geometry = None

        hotspots.append(
            PredictedHotspot(
                segment_id=segment_id,
                road_name=str(row.get("segment_name", segment_id) or segment_id),
                city=city or str(row.get("city", "")),
                current_speed=round(risk["current_speed"], 3),
                predicted_speed=round(risk["predicted_speed"], 3),
                free_flow_speed=round(risk["free_flow_speed"], 3),
                current_speed_kph=round(risk["current_speed"], 3),
                predicted_speed_kph=round(risk["predicted_speed"], 3),
                free_flow_speed_kph=round(risk["free_flow_speed"], 3),
                speed_drop_pct=round(risk["speed_drop_pct"], 3),
                predicted_free_flow_ratio=round(risk["predicted_free_flow_ratio"], 4)
                if risk["predicted_free_flow_ratio"] is not None
                else None,
                risk_score=round(risk["risk_score"], 2),
                horizon=horizon,
                risk_level=risk["risk_level"],
                triggered_rules=risk["triggered_rules"],
                reason=", ".join(risk["triggered_rules"]),
                context_explanation=risk["context_explanation"],
                latest_timestamp=prediction.latest_timestamp,
                geometry=geometry,
                model_name=prediction.model_name,
                required_feature_count=prediction.required_feature_count,
                available_feature_count=prediction.available_feature_count,
                filled_feature_count=prediction.filled_feature_count,
                feature_coverage_ratio=round(risk["feature_coverage_ratio"], 4),
                is_fallback=prediction.is_fallback,
            )
        )

    result = sorted(hotspots, key=lambda item: (-item.risk_score, item.predicted_speed))
    _PREDICTED_HOTSPOT_CACHE[cache_key] = (now, result)
    return result
