"""Transparent segment and corridor risk scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SegmentRisk:
    risk_score: float
    risk_level: str
    components: dict[str, float]
    triggered_rules: list[str]


def _float_value(row: Any, name: str, default: float = 0.0) -> float:
    value = row.get(name, default) if hasattr(row, "get") else getattr(row, name, default)
    try:
        if value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _risk_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def score_segment_risk(row: Any, prediction: Any | None = None, reliability: Any | None = None) -> SegmentRisk:
    """Score congestion risk on a 0..100 scale using plan v4 cognitive weights."""
    current_speed = _float_value(row, "currentSpeed", _float_value(row, "current_speed"))
    free_flow = _float_value(row, "freeFlowSpeed", _float_value(row, "free_flow_speed", max(current_speed, 1.0)))
    jam_factor = _float_value(row, "jamFactor", _float_value(row, "current_jam_factor"))
    predicted_speed = (
        float(getattr(prediction, "predicted_speed"))
        if prediction is not None and getattr(prediction, "predicted_speed", None) is not None
        else current_speed
    )

    congestion_ratio = max(0.0, min(1.0, 1.0 - (current_speed / free_flow))) if free_flow > 0 else min(jam_factor / 10.0, 1.0)
    prediction_drop_ratio = max(0.0, min(1.0, (current_speed - predicted_speed) / current_speed)) if current_speed > 0 else 0.0
    upstream_congestion = max(0.0, min(1.0, _float_value(row, "upstream_congestion_score") / 10.0))
    rain_severity = max(0.0, min(1.0, _float_value(row, "weather_rain_1h") / 30.0 + _float_value(row, "weather_severity") / 10.0))
    event_severity = max(
        0.0,
        min(
            1.0,
            _float_value(row, "max_event_severity_1h") / 10.0
            + _float_value(row, "accident_count_1h") * 0.25
            + _float_value(row, "news_event_count_1h") * 0.08,
        ),
    )
    coverage = float(getattr(reliability, "feature_coverage_ratio", 1.0) if reliability is not None else 1.0)
    data_uncertainty = max(0.0, min(1.0, 1.0 - coverage))

    components = {
        "congestion_ratio": congestion_ratio,
        "prediction_drop_ratio": prediction_drop_ratio,
        "upstream_congestion_score": upstream_congestion,
        "rain_severity": rain_severity,
        "event_severity": event_severity,
        "data_uncertainty": data_uncertainty,
    }
    score = 100.0 * (
        0.35 * congestion_ratio
        + 0.25 * prediction_drop_ratio
        + 0.15 * upstream_congestion
        + 0.10 * rain_severity
        + 0.10 * event_severity
        + 0.05 * data_uncertainty
    )
    score = round(max(0.0, min(100.0, score)), 3)
    triggered_rules = [name for name, value in components.items() if value >= 0.5]
    return SegmentRisk(
        risk_score=score,
        risk_level=_risk_level(score),
        components={key: round(value, 4) for key, value in components.items()},
        triggered_rules=triggered_rules,
    )
