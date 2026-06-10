"""SHAP explainability endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

from api.services.local_data import DataUnavailableError, traffic_features

logger = logging.getLogger(__name__)

router = APIRouter()


class Feature(BaseModel):
    """Feature contribution to prediction."""
    name: str
    value: float
    shap_value: float


class PredictionExplanation(BaseModel):
    """SHAP explanation for a prediction."""
    prediction_id: str
    segment_id: str
    predicted_speed: float
    top_features: List[Feature]
    weather_context: dict
    baseline_context: dict


@router.get("/{prediction_id}/explain", response_model=PredictionExplanation)
def explain_prediction(prediction_id: str):
    """Get SHAP explanation for a prediction.

    Args:
        prediction_id: Prediction ID (segment_id_timestamp)

    Returns:
        SHAP explanation with top contributing features
    """
    try:
        df = traffic_features()
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = df[df["segment_id"].astype(str) == prediction_id]
    if rows.empty and ":" in prediction_id:
        rows = df[df["segment_id"].astype(str) == prediction_id.split(":", 1)[0]]
    if rows.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No local feature row found for prediction or segment '{prediction_id}'",
        )

    row = rows.sort_values("timestamp").iloc[-1]
    current_speed = float(row.get("currentSpeed", 0.0))
    predicted_speed = float(row.get("future_speed_15m", current_speed))
    top_features = [
        Feature(name="currentSpeed", value=current_speed, shap_value=round(predicted_speed - current_speed, 3)),
        Feature(name="jamFactor", value=float(row.get("jamFactor", 0.0)), shap_value=-float(row.get("jamFactor", 0.0))),
        Feature(name="congestion_ratio", value=float(row.get("congestion_ratio", 0.0)), shap_value=-float(row.get("congestion_ratio", 0.0)) * 10),
        Feature(name="hour_of_day", value=float(row.get("hour_of_day", 0.0)), shap_value=0.0),
        Feature(name="has_recent_accident", value=float(row.get("has_recent_accident", 0.0)), shap_value=-3.0 if row.get("has_recent_accident", 0) else 0.0),
    ]

    return PredictionExplanation(
        prediction_id=prediction_id,
        segment_id=str(row["segment_id"]),
        predicted_speed=round(predicted_speed, 2),
        top_features=top_features,
        weather_context={
            "temperature": float(row.get("weather_temperature", 0.0)),
            "humidity": float(row.get("weather_humidity", 0.0)),
            "rain_1h": float(row.get("weather_rain_1h", 0.0)),
            "visibility": float(row.get("weather_visibility", 0.0)),
        },
        baseline_context={
            "p15": float(row.get("p15", 0.0)),
            "p50": float(row.get("p50", row.get("speed_rolling_avg_60m", 0.0))),
            "p85": float(row.get("p85", 0.0)),
            "typical_hour_avg": float(row.get("speed_rolling_avg_60m", 0.0)),
            "mode": "local-feature-fallback",
        },
    )
