"""Congestion hotspot endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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
    # In production, query gold_congestion_hotspots from Trino
    hotspots = [
        Hotspot(
            hotspot_id=f"hotspot_{city}_{i}",
            cluster_id=i,
            city=city,
            center_lat=20.8 + i * 0.05,
            center_lon=105.8 + i * 0.05,
            radius_km=0.8 + i * 0.2,
            num_segments=5 + i,
            avg_congestion=0.6 + i * 0.1,
            avg_jam_factor=6.5 - i,
            severity="high" if i % 3 == 0 else "medium",
            detected_at=datetime.utcnow(),
        )
        for i in range(3)
    ]

    if severity:
        hotspots = [h for h in hotspots if h.severity == severity]

    return hotspots
