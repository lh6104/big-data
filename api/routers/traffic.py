"""Traffic data endpoints (real-time and forecast)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

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
    if city not in ["hanoi", "hcmc"]:
        raise HTTPException(status_code=400, detail=f"Unknown city: {city}")

    # In production, query Redis cache or Trino
    # For now, return mock data
    return TrafficStatus(
        city=city,
        total_segments=450 if city == "hanoi" else 380,
        avg_speed=35.5,
        congestion_ratio=0.42,
        max_jam_factor=7.8,
        critical_segment_count=12,
        timestamp=datetime.utcnow(),
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

    # In production, query gold_prediction_results from Trino
    # For now, return mock data
    return SpeedForecast(
        segment_id=segment_id,
        city="hanoi",
        horizon_minutes=horizon,
        predicted_speed=32.5 if horizon == 15 else 28.3,
        confidence=0.92,
        baseline_p50=40.0,
        baseline_p85=50.0,
        timestamp=datetime.utcnow(),
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
    # In production, query silver_traffic_cleaned with pagination
    return [
        TrafficSegment(
            segment_id=f"seg_{i}",
            city=city,
            current_speed=25 + i % 30,
            free_flow_speed=50.0,
            jam_factor=5.0 - (i % 8),
            timestamp=datetime.utcnow(),
            road_class="primary",
            district="dist_1",
        )
        for i in range(min(limit, 10))
    ]
