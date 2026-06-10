"""SHAP explainability endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

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
    # In production, query gold_prediction_results.shap_explanation
    return PredictionExplanation(
        prediction_id=prediction_id,
        segment_id="seg_001",
        predicted_speed=28.5,
        top_features=[
            Feature(name="current_speed", value=32.0, shap_value=15.3),
            Feature(name="congestion_ratio", value=0.35, shap_value=-8.2),
            Feature(name="hour_of_day", value=17, shap_value=-5.1),
            Feature(name="is_peak_hour", value=1, shap_value=-3.5),
            Feature(name="has_accident", value=1, shap_value=-2.1),
        ],
        weather_context={
            "temperature": 28,
            "humidity": 75,
            "rain_1h": 0.5,
            "visibility": 8,
        },
        baseline_context={
            "p15": 20,
            "p50": 40,
            "p85": 50,
            "typical_hour_avg": 36,
        },
    )
