"""Alert management endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
import logging

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


# Endpoints
@router.get("/active", response_model=List[Alert])
def get_active_alerts(
    city: Optional[str] = Query(None, description="Filter by city"),
    severity: Optional[SeverityLevel] = Query(None, description="Filter by severity"),
    limit: int = Query(50, description="Limit number of alerts")
):
    """Get active traffic alerts.

    Args:
        city: Optional city filter
        severity: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)
        limit: Maximum number of alerts

    Returns:
        List of active alerts
    """
    # In production, query gold_alerts from Trino
    # Filter by acknowledged=false

    alerts = [
        Alert(
            alert_id=f"alert_{i}",
            segment_id=f"seg_{i}",
            city=city or "hanoi",
            severity=SeverityLevel.CRITICAL if i % 5 == 0 else SeverityLevel.HIGH,
            reason=f"Speed below baseline by {20 + i}%",
            predicted_speed=18.5 + i,
            baseline_p50=40.0,
            created_at=datetime.utcnow(),
            acknowledged=False,
        )
        for i in range(min(limit, 3))
    ]

    return alerts


@router.get("/{alert_id}", response_model=Alert)
def get_alert(alert_id: str):
    """Get single alert details.

    Args:
        alert_id: Alert ID

    Returns:
        Alert details
    """
    # In production, query from gold_alerts
    return Alert(
        alert_id=alert_id,
        segment_id="seg_001",
        city="hanoi",
        severity=SeverityLevel.HIGH,
        reason="Speed 22 km/h is <70% of baseline p50 (40 km/h)",
        predicted_speed=22.0,
        baseline_p50=40.0,
        created_at=datetime.utcnow(),
        acknowledged=False,
    )


@router.patch("/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: str, update: AlertUpdate):
    """Acknowledge or resolve an alert.

    Args:
        alert_id: Alert ID
        update: Status update

    Returns:
        Updated alert
    """
    # In production, update gold_alerts table
    logger.info(f"Alert {alert_id} acknowledged: {update.acknowledged}")

    return Alert(
        alert_id=alert_id,
        segment_id="seg_001",
        city="hanoi",
        severity=SeverityLevel.HIGH,
        reason="Speed 22 km/h is <70% of baseline p50 (40 km/h)",
        predicted_speed=22.0,
        baseline_p50=40.0,
        created_at=datetime.utcnow(),
        acknowledged=update.acknowledged,
    )


@router.patch("/bulk-ack")
def bulk_acknowledge_alerts(alert_ids: List[str], acknowledged: bool = True):
    """Bulk acknowledge/resolve alerts.

    Args:
        alert_ids: List of alert IDs
        acknowledged: New status

    Returns:
        Number of alerts updated
    """
    # In production, bulk update gold_alerts
    logger.info(f"Bulk acknowledged {len(alert_ids)} alerts: {acknowledged}")

    return {
        "updated_count": len(alert_ids),
        "acknowledged": acknowledged,
    }
