"""Alert management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, severity_from_jam, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


class SeverityLevel(str, Enum):
    """Alert severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Alert(BaseModel):
    """Traffic alert."""
    alert_id: str
    segment_id: str
    city: str
    severity: SeverityLevel
    reason: str
    predicted_speed: float
    baseline_p50: float
    created_at: datetime
    acknowledged: bool = False


class AlertUpdate(BaseModel):
    """Alert status update."""
    acknowledged: bool


class BulkAlertUpdate(BaseModel):
    """Bulk alert status update."""
    ids: List[str]
    acknowledged: bool = True


def _alert_from_row(row) -> Alert:
    jam = float(row.jamFactor)
    speed = float(row.currentSpeed)
    baseline = float(getattr(row, "p50", getattr(row, "freeFlowSpeed", speed)))
    severity_name = severity_from_jam(jam)
    reason = f"Jam factor {jam:.1f}; speed {speed:.1f} km/h versus baseline {baseline:.1f} km/h"
    return Alert(
        alert_id=f"alert_{row.city}_{row.segment_id}",
        segment_id=str(row.segment_id),
        city=str(row.city),
        severity=SeverityLevel(severity_name),
        reason=reason,
        predicted_speed=round(speed, 2),
        baseline_p50=round(baseline, 2),
        created_at=row.timestamp.to_pydatetime(),
        acknowledged=False,
    )


# Endpoints
@router.get("/active", response_model=List[Alert])
def get_active_alerts(
    city: Optional[str] = None,
    severity: Optional[SeverityLevel] = None,
    limit: int = 50,
):
    """Get active traffic alerts.

    Args:
        city: Optional city filter
        severity: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)
        limit: Maximum number of alerts

    Returns:
        List of active alerts
    """
    try:
        latest = latest_by_segment(traffic_features(), normalize_city(city) if city else None)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    latest = latest[latest["jamFactor"] >= 3].sort_values("jamFactor", ascending=False)
    alerts = [_alert_from_row(row) for row in latest.itertuples(index=False)]
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    return alerts[:limit]


@router.get("/{alert_id}", response_model=Alert)
def get_alert(alert_id: str):
    """Get single alert details.

    Args:
        alert_id: Alert ID

    Returns:
        Alert details
    """
    for alert in get_active_alerts(limit=1000):
        if alert.alert_id == alert_id:
            return alert
    raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' was not found in local data")


@router.patch("/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: str, update: AlertUpdate):
    """Acknowledge or resolve an alert.

    Args:
        alert_id: Alert ID
        update: Status update

    Returns:
        Updated alert
    """
    logger.info(f"Alert {alert_id} acknowledged: {update.acknowledged}")
    alert = get_alert(alert_id)
    alert.acknowledged = update.acknowledged
    return alert


@router.patch("/bulk-ack")
def bulk_acknowledge_alerts(update: BulkAlertUpdate):
    """Bulk acknowledge/resolve alerts.

    Args:
        alert_ids: List of alert IDs
        acknowledged: New status

    Returns:
        Number of alerts updated
    """
    logger.info(f"Bulk acknowledged {len(update.ids)} alerts: {update.acknowledged}")

    return {
        "updated_count": len(update.ids),
        "acknowledged": update.acknowledged,
    }
