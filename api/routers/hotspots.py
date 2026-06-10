"""Congestion hotspot endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, traffic_features

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
