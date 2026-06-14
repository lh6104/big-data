"""Traffic data endpoints (real-time and forecast)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, traffic_features
from api.services.model_inference import ModelUnavailableError, model_status, normalize_horizon, predict_for_segment
from intelligence.what_if_simulator import simulate_traffic_scenario

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


class ModelPredictionResponse(BaseModel):
    """Demo model prediction response."""
    segment_id: str
    horizon: str
    predicted_speed: Optional[float]
    current_speed: Optional[float]
    current_jam_factor: Optional[float]
    model_name: str
    model_artifact: str
    model_source: str
    data_source: str
    input_source: str
    is_fallback: bool
    required_feature_count: int
    available_feature_count: int
    filled_feature_count: int
    feature_fill_strategy: Optional[str] = None
    missing_features: List[str] = Field(default_factory=list)
    latest_timestamp: Optional[str] = None
    warning: Optional[str] = None
    confidence_band: Optional[List[float]] = None
    reliability_level: Optional[str] = None
    feature_coverage_ratio: Optional[float] = None
    data_freshness_seconds: Optional[int] = None


class TrafficSimulationRequest(BaseModel):
    """What-if simulation request."""
    segment_id: str
    horizon: str = "15m"
    rain_1h_mm: Optional[float] = None
    event_type: Optional[str] = None
    is_peak_hour: bool = False


class TrafficSimulationResponse(BaseModel):
    """What-if simulation response."""
    segment_id: str
    horizon: str
    baseline_speed: float
    simulated_speed: float
    speed_delta: float
    speed_delta_pct: float
    baseline_risk: dict[str, Any]
    simulated_risk: dict[str, Any]
    applied_scenario: dict[str, Any]


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


@router.get("/model/status")
def get_model_status(load_models: bool = Query(False, description="Attempt to load model artifacts")):
    """Get demo model artifact readiness and metadata."""
    return model_status(load_models=load_models)


@router.get("/predict/{segment_id}", response_model=ModelPredictionResponse)
def get_speed_forecast(
    segment_id: str,
    horizon: str = Query("15m", description="Forecast horizon (15m or 60m)")
):
    """Get demo model speed forecast for a segment.

    Args:
        segment_id: Traffic segment ID
        horizon: Forecast horizon (15m or 60m)

    Returns:
        Speed forecast with model/fallback metadata
    """
    try:
        normalize_horizon(horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        prediction = predict_for_segment(segment_id, horizon)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payload = prediction.__dict__.copy()
    if payload.get("confidence_band") is not None:
        payload["confidence_band"] = list(payload["confidence_band"])
    return ModelPredictionResponse(**payload)


@router.post("/simulate", response_model=TrafficSimulationResponse)
def simulate_traffic(request: TrafficSimulationRequest):
    """Run a lightweight what-if simulation for rain/event/peak-hour scenarios."""
    try:
        normalize_horizon(request.horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest[latest["segment_id"].astype(str) == str(request.segment_id)]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Segment '{request.segment_id}' was not found in local data")

    try:
        prediction = predict_for_segment(request.segment_id, request.horizon)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    scenario = request.model_dump(exclude={"segment_id", "horizon"}, exclude_none=True)
    scenario["horizon"] = normalize_horizon(request.horizon)
    result = simulate_traffic_scenario(rows.iloc[-1], prediction, scenario)
    return TrafficSimulationResponse(
        segment_id=result.segment_id,
        horizon=result.horizon,
        baseline_speed=result.baseline_speed,
        simulated_speed=result.simulated_speed,
        speed_delta=result.speed_delta,
        speed_delta_pct=result.speed_delta_pct,
        baseline_risk={
            "risk_score": result.baseline_risk.risk_score,
            "risk_level": result.baseline_risk.risk_level,
            "components": result.baseline_risk.components,
            "triggered_rules": result.baseline_risk.triggered_rules,
        },
        simulated_risk={
            "risk_score": result.simulated_risk.risk_score,
            "risk_level": result.simulated_risk.risk_level,
            "components": result.simulated_risk.components,
            "triggered_rules": result.simulated_risk.triggered_rules,
        },
        applied_scenario=result.applied_scenario,
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
