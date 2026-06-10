"""Road segment metadata endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, synthetic_geojson_line, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


class Segment(BaseModel):
    """Road segment details."""
    segment_id: str
    city: str
    road_class: str
    district: str
    length_m: float
    speed_limit: int
    lat: float
    lon: float
    timestamp: datetime


class SegmentGeoJSON(BaseModel):
    """GeoJSON feature for Leaflet mapping."""
    type: str = "FeatureCollection"
    features: List[dict]


@router.get("/geojson", response_model=SegmentGeoJSON)
def get_segments_geojson(city: str = Query("hanoi", description="City code")):
    """Get segments as GeoJSON for Leaflet map rendering.

    Args:
        city: City code

    Returns:
        GeoJSON FeatureCollection with segment polylines
    """
    city = normalize_city(city)
    try:
        latest = latest_by_segment(traffic_features(), city)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SegmentGeoJSON(
        features=[
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": synthetic_geojson_line(float(row.lat), float(row.lon)),
                },
                "properties": {
                    "segment_id": str(row.segment_id),
                    "jam_factor": round(float(row.jamFactor), 2),
                    "current_speed": round(float(row.currentSpeed), 2),
                    "free_flow_speed": round(float(row.freeFlowSpeed), 2),
                    "city": str(row.city),
                },
            }
            for row in latest.head(250).itertuples(index=False)
        ]
    )


@router.get("/{segment_id}", response_model=Segment)
def get_segment_details(segment_id: str):
    """Get detailed information for a segment.

    Args:
        segment_id: Segment ID

    Returns:
        Segment details
    """
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest[latest["segment_id"].astype(str) == segment_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' was not found in local data")
    row = rows.iloc[0]
    return Segment(
        segment_id=segment_id,
        city=str(row.get("city", "unknown")),
        road_class=str(row.get("road_class_encoded", "unknown")),
        district=str(row.get("district", "unknown")),
        length_m=float(row.get("length_m", 0.0)),
        speed_limit=int(row.get("speed_limit_encoded", 0)),
        lat=float(row.get("lat", 0.0)),
        lon=float(row.get("lon", 0.0)),
        timestamp=row["timestamp"].to_pydatetime(),
    )


@router.get("/{segment_id}/upstream")
def get_upstream_sensors(segment_id: str):
    """Get upstream sensor chain for Live Corridor Tracking.

    Args:
        segment_id: Segment ID

    Returns:
        List of upstream segments feeding into this one
    """
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest.sort_values("jamFactor", ascending=False).head(4)
    chain = []
    for row in rows.itertuples(index=False):
        speed = float(row.currentSpeed)
        status = "congested" if float(row.jamFactor) >= 6 else "slow" if float(row.jamFactor) >= 3 else "free"
        chain.append(
            {
                "id": str(row.segment_id),
                "segment_id": str(row.segment_id),
                "name": str(getattr(row, "segment_name", row.segment_id)),
                "road_class": str(getattr(row, "road_class_encoded", "unknown")),
                "speed_kmh": round(speed, 2),
                "current_speed": round(speed, 2),
                "status": status,
                "distance_m": (len(chain) + 1) * 500,
            }
        )

    return {
        "segment_id": segment_id,
        "updated_at": datetime.utcnow().isoformat(),
        "chain": chain,
        "upstream_segments": chain,
    }
