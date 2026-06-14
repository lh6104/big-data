"""Lightweight what-if traffic simulation for demo and API use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence.risk_scoring import SegmentRisk, score_segment_risk


@dataclass(frozen=True)
class SimulationResult:
    segment_id: str
    horizon: str
    baseline_speed: float
    simulated_speed: float
    speed_delta: float
    speed_delta_pct: float
    baseline_risk: SegmentRisk
    simulated_risk: SegmentRisk
    applied_scenario: dict[str, Any]


def _as_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "to_dict"):
        return row.to_dict()
    if hasattr(row, "_asdict"):
        return row._asdict()
    if isinstance(row, dict):
        return dict(row)
    return dict(getattr(row, "__dict__", {}))


def simulate_traffic_scenario(row: Any, baseline_prediction: Any, scenario: dict[str, Any]) -> SimulationResult:
    """Apply simple interpretable deltas for rain/event/peak-hour scenarios."""
    values = _as_dict(row)
    baseline_speed = float(getattr(baseline_prediction, "predicted_speed", None) or values.get("currentSpeed", 0.0) or 0.0)
    simulated = baseline_speed

    rain_1h = float(scenario.get("rain_1h_mm") or scenario.get("rain_1h") or 0.0)
    if rain_1h > 0:
        values["weather_rain_1h"] = rain_1h
        values["weather_severity"] = max(float(values.get("weather_severity", 0.0) or 0.0), min(10.0, rain_1h / 3.0))
        simulated *= max(0.65, 1.0 - min(rain_1h, 40.0) * 0.008)

    event_type = str(scenario.get("event_type") or "none").lower()
    if event_type in {"accident", "flood", "roadwork"}:
        values["news_event_count_1h"] = max(float(values.get("news_event_count_1h", 0.0) or 0.0), 1.0)
        values["max_event_severity_1h"] = max(float(values.get("max_event_severity_1h", 0.0) or 0.0), 7.0)
        simulated *= {"accident": 0.72, "flood": 0.78, "roadwork": 0.86}[event_type]

    if bool(scenario.get("is_peak_hour", False)):
        values["is_peak_hour"] = 1
        simulated *= 0.9

    simulated = round(max(0.0, simulated), 3)
    fake_prediction = type("ScenarioPrediction", (), {"predicted_speed": simulated})()
    baseline_risk = score_segment_risk(values, baseline_prediction)
    simulated_risk = score_segment_risk(values, fake_prediction)
    delta = round(simulated - baseline_speed, 3)
    delta_pct = round((delta / baseline_speed * 100.0), 3) if baseline_speed > 0 else 0.0
    return SimulationResult(
        segment_id=str(values.get("segment_id", "unknown")),
        horizon=str(getattr(baseline_prediction, "horizon", scenario.get("horizon", "15m"))),
        baseline_speed=round(baseline_speed, 3),
        simulated_speed=simulated,
        speed_delta=delta,
        speed_delta_pct=delta_pct,
        baseline_risk=baseline_risk,
        simulated_risk=simulated_risk,
        applied_scenario=scenario,
    )
