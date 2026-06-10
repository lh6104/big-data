"""Traffic data endpoints (real-time and forecast)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, train_features, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class TrafficSegment(BaseModel):
    """Traffic segment data."""
    segment_id: str
    city: str
    current_speed: float
    free_flow_speed: float
    jam_factor: float
    timestamp: datetime
    road_class: str
    district: str


class TrafficStatus(BaseModel):
    """City-level traffic status."""
    city: str
    total_segments: int
    avg_speed: float
    congestion_ratio: float
    max_jam_factor: float
    critical_segment_count: int
    timestamp: datetime


class SpeedForecast(BaseModel):
    """Speed forecast for a segment."""
    segment_id: str
    city: str
    horizon_minutes: int
    predicted_speed: float
    confidence: float
    baseline_p50: float
    baseline_p85: float
    timestamp: datetime


# Endpoints
@router.get("/current/{city}", response_model=TrafficStatus)
def get_current_traffic(city: str):
    """Get current traffic status for a city.

    Args:
        city: City code (hanoi, hcmc)

    Returns:
        Current traffic status with aggregated metrics
    """
    city = normalize_city(city)
    if city not in ["hanoi", "hcmc"]:
        raise HTTPException(status_code=400, detail=f"Unknown city: {city}")

    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        raise HTTPException(status_code=404, detail=f"No local traffic data found for city '{city}'")

    total_segments = int(latest["segment_id"].nunique())
    avg_speed = float(latest["currentSpeed"].mean())
    max_jam = float(latest["jamFactor"].max())
    congestion_ratio = float((latest["jamFactor"] >= 3).mean())
    critical_count = int((latest["jamFactor"] >= 6).sum())
    timestamp = latest["timestamp"].max().to_pydatetime()

    return TrafficStatus(
        city=city,
        total_segments=total_segments,
        avg_speed=round(avg_speed, 2),
        congestion_ratio=round(congestion_ratio, 4),
        max_jam_factor=round(max_jam, 2),
        critical_segment_count=critical_count,
        timestamp=timestamp,
    )


@router.get("/predict/{segment_id}", response_model=SpeedForecast)
def get_speed_forecast(
    segment_id: str,
    horizon: int = Query(15, description="Forecast horizon in minutes (15, 60, or 240)")
):
    """Get speed forecast for a segment.

    Args:
        segment_id: Traffic segment ID
        horizon: Forecast horizon (15, 60, or 240 minutes)

    Returns:
        Speed forecast with confidence interval
    """
    if horizon not in [15, 60, 240]:
        raise HTTPException(status_code=400, detail="Horizon must be 15, 60, or 240 minutes")

    try:
        df = train_features(60 if horizon == 60 else 15)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    segment_rows = df[df["segment_id"].astype(str) == segment_id]
    if segment_rows.empty:
        raise HTTPException(status_code=404, detail=f"No local training rows found for segment '{segment_id}'")

    latest = segment_rows.sort_values("timestamp").iloc[-1]
    current_speed = float(latest.get("currentSpeed", 0))
    if "target_speed" in latest:
        predicted_speed = float(latest["target_speed"])
    else:
        predicted_speed = current_speed
    baseline_p50 = float(latest.get("p50", latest.get("speed_rolling_avg_60m", current_speed)))
    baseline_p85 = float(latest.get("p85", max(baseline_p50, current_speed)))

    return SpeedForecast(
        segment_id=segment_id,
        city=str(latest.get("city", "unknown")),
        horizon_minutes=horizon,
        predicted_speed=round(predicted_speed, 2),
        confidence=0.65,
        baseline_p50=round(baseline_p50, 2),
        baseline_p85=round(baseline_p85, 2),
        timestamp=datetime.fromisoformat(str(latest["timestamp"])),
    )


@router.get("/segments", response_model=List[TrafficSegment])
def list_traffic_segments(
    city: str = Query("hanoi", description="Filter by city"),
    limit: int = Query(50, description="Limit number of results")
):
    """List traffic segments for a city.

    Args:
        city: City code
        limit: Maximum number of segments

    Returns:
        List of traffic segments
    """
    city = normalize_city(city)
    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    latest = latest.sort_values("jamFactor", ascending=False).head(limit)
    return [
        TrafficSegment(
            segment_id=str(row.segment_id),
            city=str(row.city),
            current_speed=round(float(row.currentSpeed), 2),
            free_flow_speed=round(float(row.freeFlowSpeed), 2),
            jam_factor=round(float(row.jamFactor), 2),
            timestamp=row.timestamp.to_pydatetime(),
            road_class=str(getattr(row, "road_class_encoded", "unknown")),
            district=str(getattr(row, "district", "unknown")),
        )
        for row in latest.itertuples(index=False)
    ]
