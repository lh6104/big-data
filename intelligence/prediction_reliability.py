"""Prediction reliability scoring for API responses and alert decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


RESIDUAL_BAND_BY_HORIZON = {
    "15m": 5.0,
    "60m": 7.5,
    "240m": 12.0,
}


@dataclass(frozen=True)
class PredictionReliability:
    feature_coverage_ratio: float
    reliability_level: str
    confidence_band: tuple[float, float] | None
    data_freshness_seconds: int | None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _freshness_seconds(latest_timestamp: str | None, now: datetime | None = None) -> int | None:
    parsed = _parse_timestamp(latest_timestamp)
    if parsed is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0, int((current - parsed).total_seconds()))


def assess_prediction_reliability(prediction: Any, now: datetime | None = None) -> PredictionReliability:
    """Assess whether a prediction is suitable for alerting/demo decisions."""
    required = int(getattr(prediction, "required_feature_count", 0) or 0)
    available = int(getattr(prediction, "available_feature_count", 0) or 0)
    coverage = available / required if required else 0.0
    freshness = _freshness_seconds(getattr(prediction, "latest_timestamp", None), now=now)
    is_fallback = bool(getattr(prediction, "is_fallback", False))

    if is_fallback or coverage < 0.7 or (freshness is not None and freshness > 3600):
        level = "low"
    elif coverage < 0.9 or freshness is None or freshness > 600:
        level = "medium"
    else:
        level = "high"

    predicted_speed = getattr(prediction, "predicted_speed", None)
    if predicted_speed is None:
        confidence_band = None
    else:
        horizon = str(getattr(prediction, "horizon", "15m"))
        base_band = RESIDUAL_BAND_BY_HORIZON.get(horizon, 8.0)
        coverage_penalty = (1.0 - min(max(coverage, 0.0), 1.0)) * base_band
        fallback_penalty = base_band if is_fallback else 0.0
        half_width = base_band + coverage_penalty + fallback_penalty
        speed = float(predicted_speed)
        confidence_band = (round(max(0.0, speed - half_width), 3), round(speed + half_width, 3))

    return PredictionReliability(
        feature_coverage_ratio=round(coverage, 4),
        reliability_level=level,
        confidence_band=confidence_band,
        data_freshness_seconds=freshness,
    )
