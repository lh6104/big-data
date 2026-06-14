"""Reason generation for smart congestion alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SmartAlertReason:
    why: list[str]
    recommended_action: str
    confidence_level: str
    affected_segments: list[str]


def reason_about_alert(row: Any, severity: str, risk: Any | None = None, reliability: Any | None = None) -> SmartAlertReason:
    segment_id = str(row.get("segment_id", "unknown") if hasattr(row, "get") else getattr(row, "segment_id", "unknown"))
    jam = float(row.get("jamFactor", 0.0) if hasattr(row, "get") else getattr(row, "jamFactor", 0.0))
    speed = float(row.get("currentSpeed", 0.0) if hasattr(row, "get") else getattr(row, "currentSpeed", 0.0))
    baseline = float(row.get("p50", row.get("freeFlowSpeed", speed)) if hasattr(row, "get") else getattr(row, "p50", speed))
    why = [f"Jam factor is {jam:.1f} with speed {speed:.1f} km/h versus baseline {baseline:.1f} km/h"]

    if risk is not None:
        why.append(f"Risk score is {risk.risk_score:.1f}/100 ({risk.risk_level})")
        if risk.triggered_rules:
            why.append("Triggered risk signals: " + ", ".join(risk.triggered_rules[:3]))
    if reliability is not None:
        why.append(f"Prediction reliability is {reliability.reliability_level}")

    if severity in {"CRITICAL", "HIGH"}:
        action = "Prioritize monitoring this corridor and suggest an alternative route."
    elif severity == "MEDIUM":
        action = "Monitor the segment and keep route alternatives ready."
    else:
        action = "Track the segment; no immediate intervention required."

    confidence = getattr(reliability, "reliability_level", "medium") if reliability is not None else "medium"
    return SmartAlertReason(
        why=why,
        recommended_action=action,
        confidence_level=str(confidence),
        affected_segments=[segment_id],
    )
