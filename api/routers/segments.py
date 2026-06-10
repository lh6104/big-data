"""Road segment metadata endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

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
    # In production, query silver_traffic_cleaned + Redis cache
    return SegmentGeoJSON(
        features=[
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[105.8 + i * 0.01, 20.8 + i * 0.01] for i in range(3)],
                },
                "properties": {
                    "segment_id": f"seg_{i}",
                    "jam_factor": 5 - i,
                    "current_speed": 30 + i * 5,
                    "free_flow_speed": 50,
                },
            }
            for i in range(3)
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
    # In production, query silver_traffic_osm_mapped
    return Segment(
        segment_id=segment_id,
        city="hanoi",
        road_class="primary",
        district="ba_dinh",
        length_m=850.0,
        speed_limit=60,
        lat=20.85,
        lon=105.82,
        timestamp=datetime.utcnow(),
    )


@router.get("/{segment_id}/upstream")
def get_upstream_sensors(segment_id: str):
    """Get upstream sensor chain for Live Corridor Tracking.

    Args:
        segment_id: Segment ID

    Returns:
        List of upstream segments feeding into this one
    """
    # In production, query Neo4j for upstream road graph
    return {
        "segment_id": segment_id,
        "upstream_segments": [
            {
                "segment_id": f"seg_upstream_{i}",
                "distance_m": (i + 1) * 500,
                "current_speed": 35 - i * 3,
            }
            for i in range(3)
        ],
    }
