"""Road segment metadata endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, List, Optional
from datetime import datetime
import logging
import ast
import json

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, synthetic_geojson_line, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


DEMO_COVERAGE_TARGETS = {"hanoi": 150, "hcmc": 140}
DEMO_CORRIDORS: dict[str, list[dict[str, Any]]] = {
    "hanoi": [
        {"name": "Demo Ring Road 3", "points": [(21.0360, 105.7818), (21.0244, 105.7814), (21.0076, 105.7888), (20.9988, 105.7994), (20.9849, 105.7989)]},
        {"name": "Demo Nguyen Trai - Tran Phu", "points": [(21.0022, 105.8195), (20.9956, 105.8220), (20.9800, 105.7870), (20.9690, 105.7750)]},
        {"name": "Demo Giai Phong", "points": [(21.0062, 105.8460), (20.9940, 105.8424), (20.9761, 105.8410), (20.9588, 105.8208)]},
        {"name": "Demo Vo Chi Cong - Nhat Tan", "points": [(21.0521, 105.7852), (21.0600, 105.8100), (21.0905, 105.8178), (21.1210, 105.8200)]},
        {"name": "Demo Hoan Kiem River", "points": [(21.0397, 105.8847), (21.0276, 105.9002), (21.0005, 105.8917), (20.9990, 105.8798)]},
        {"name": "Demo Cau Giay Core", "points": [(21.0368, 105.7846), (21.0320, 105.8006), (21.0230, 105.8100), (21.0189, 105.8320)]},
        {"name": "Demo Tay Ho - Ba Dinh", "points": [(21.0645, 105.8355), (21.0524, 105.8373), (21.0372, 105.8146), (21.0280, 105.8340)]},
        {"name": "Demo Long Bien - Co Linh", "points": [(21.0470, 105.8760), (21.0397, 105.8847), (21.0276, 105.9002), (21.0005, 105.8917)]},
        {"name": "Demo Ha Dong - To Huu", "points": [(20.9731, 105.7816), (20.9953, 105.7857), (21.0030, 105.8010), (21.0142, 105.7939)]},
    ],
    "hcmc": [
        {"name": "Demo Vo Van Kiet", "points": [(10.7556, 106.6803), (10.7675, 106.7061), (10.7757, 106.7004), (10.7810, 106.7350)]},
        {"name": "Demo Dien Bien Phu - Hanoi Highway", "points": [(10.7904, 106.6975), (10.8015, 106.7148), (10.8230, 106.7600), (10.8621, 106.7948)]},
        {"name": "Demo Nguyen Van Linh", "points": [(10.7298, 106.7014), (10.7280, 106.7050), (10.7405, 106.7420), (10.7671, 106.7729)]},
        {"name": "Demo Cong Hoa - Truong Chinh", "points": [(10.8012, 106.6525), (10.8010, 106.6800), (10.7904, 106.6975), (10.8015, 106.7148)]},
        {"name": "Demo Nguyen Huu Canh - Mai Chi Tho", "points": [(10.7901, 106.7197), (10.7810, 106.7350), (10.7765, 106.7570), (10.8020, 106.7700)]},
        {"name": "Demo Cach Mang Thang Tam", "points": [(10.7769, 106.7009), (10.7890, 106.6820), (10.8012, 106.6525), (10.8230, 106.6280)]},
        {"name": "Demo Pham Van Dong", "points": [(10.8015, 106.7148), (10.8200, 106.7050), (10.8400, 106.6950), (10.8621, 106.6880)]},
        {"name": "Demo District 7 - Thu Thiem", "points": [(10.7298, 106.7014), (10.7450, 106.7180), (10.7650, 106.7350), (10.7901, 106.7197)]},
    ],
}


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


def _geometry_coordinates(row) -> list[list[float]]:
    geometry = getattr(row, "geometry", None)
    if isinstance(geometry, str) and geometry:
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            try:
                geometry = ast.literal_eval(geometry)
            except (ValueError, SyntaxError):
                geometry = None
    if isinstance(geometry, dict):
        coords = geometry.get("coordinates") or []
        normalized = []
        for point in coords:
            if isinstance(point, dict):
                lat = point.get("latitude")
                lon = point.get("longitude")
                if lat is not None and lon is not None:
                    normalized.append([float(lon), float(lat)])
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                normalized.append([float(point[0]), float(point[1])])
        if len(normalized) >= 2:
            return normalized
    return synthetic_geojson_line(float(row.lat), float(row.lon))


def _line_chunks(points: list[tuple[float, float]], chunks_per_leg: int = 6) -> list[list[list[float]]]:
    chunks: list[list[list[float]]] = []
    for start, end in zip(points, points[1:]):
        start_lat, start_lon = start
        end_lat, end_lon = end
        for idx in range(chunks_per_leg):
            a = idx / chunks_per_leg
            b = (idx + 1) / chunks_per_leg
            lat1 = start_lat + (end_lat - start_lat) * a
            lon1 = start_lon + (end_lon - start_lon) * a
            lat2 = start_lat + (end_lat - start_lat) * b
            lon2 = start_lon + (end_lon - start_lon) * b
            chunks.append([[lon1, lat1], [lon2, lat2]])
    return chunks


def _status_template(latest, idx: int) -> tuple[float, float, float]:
    if latest.empty:
        return 35.0, 45.0, 2.0
    row = latest.iloc[idx % len(latest)]
    current = float(row.get("currentSpeed", 35.0))
    free_flow = float(row.get("freeFlowSpeed", max(current, 45.0)))
    jam = float(row.get("jamFactor", 2.0))
    return current, free_flow, jam


def _demo_coverage_features(city: str, existing_ids: set[str], latest) -> list[dict]:
    target = DEMO_COVERAGE_TARGETS.get(city, 0)
    needed = max(0, target - len(existing_ids))
    if needed <= 0:
        return []

    features: list[dict] = []
    corridors = DEMO_CORRIDORS.get(city, [])
    for corridor_idx, corridor in enumerate(corridors, start=1):
        for chunk_idx, coordinates in enumerate(_line_chunks(corridor["points"]), start=1):
            if len(features) >= needed:
                return features
            segment_id = f"{city.upper()}_DEMO_{corridor_idx:02d}_{chunk_idx:02d}"
            if segment_id in existing_ids:
                continue
            current, free_flow, jam = _status_template(latest, len(features))
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "segment_id": segment_id,
                        "jam_factor": round(jam, 2),
                        "current_speed": round(current, 2),
                        "free_flow_speed": round(free_flow, 2),
                        "city": city,
                        "coverage_source": "demo_coverage_interpolated",
                        "is_demo_coverage": True,
                        "segment_name": corridor["name"],
                    },
                }
            )
    return features


@router.get("/geojson", response_model=SegmentGeoJSON)
def get_segments_geojson(
    city: str = Query("hanoi", description="City code"),
    include_demo_coverage: bool = Query(False, description="Add clearly marked interpolated demo coverage lines"),
):
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

    features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": _geometry_coordinates(row),
                },
                "properties": {
                    "segment_id": str(row.segment_id),
                    "jam_factor": round(float(row.jamFactor), 2),
                    "current_speed": round(float(row.currentSpeed), 2),
                    "free_flow_speed": round(float(row.freeFlowSpeed), 2),
                    "city": str(row.city),
                    "coverage_source": "local_gold",
                    "is_demo_coverage": False,
                    "segment_name": str(getattr(row, "segment_name", row.segment_id)),
                    "source": str(getattr(row, "source", "unknown")),
                    "provider": str(getattr(row, "provider", "unknown")),
                    "latest_timestamp": str(getattr(row, "timestamp", "")),
                    "confidence": round(float(getattr(row, "confidence", 1.0)), 3)
                    if getattr(row, "confidence", None) == getattr(row, "confidence", None)
                    else 1.0,
                },
            }
            for row in latest.head(250).itertuples(index=False)
    ]
    if include_demo_coverage:
        existing_ids = {str(feature["properties"]["segment_id"]) for feature in features}
        features.extend(_demo_coverage_features(city or "", existing_ids, latest))

    return SegmentGeoJSON(features=features)


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
