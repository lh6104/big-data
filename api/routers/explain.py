"""Model explainability endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging
from typing import Any, List

import numpy as np
import pandas as pd

from api.services.local_data import DataUnavailableError, latest_by_segment, traffic_features, train_features
from api.services.model_inference import (
    ModelUnavailableError,
    _feature_frame,
    artifact_name,
    estimator_from_artifact,
    feature_columns_for_model,
    load_model,
    model_dir,
    model_name_from_artifact,
    normalize_horizon,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class Feature(BaseModel):
    """Feature contribution to prediction."""
    name: str
    value: float | str | bool | None
    baseline_value: float | str | bool | None = None
    shap_value: float
    direction: str


class PredictionExplanation(BaseModel):
    """Model-derived explanation for a prediction."""
    prediction_id: str
    segment_id: str
    horizon: str
    predicted_speed: float
    current_speed: float | None
    current_jam_factor: float | None
    model_name: str
    model_artifact: str
    model_source: str
    data_source: str
    attribution_method: str
    required_feature_count: int
    available_feature_count: int
    filled_feature_count: int
    missing_features: List[str]
    top_features: List[Feature]
    weather_context: dict
    baseline_context: dict


def _jsonable(value: Any) -> float | str | bool | None:
    if value is None:
        return None
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if pd.isna(value):
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _optional_float(row: Any, key: str, *, zero_is_missing: bool = True) -> float | None:
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if zero_is_missing and numeric == 0.0:
        return None
    return numeric


def _baseline_values(horizon_minutes: int, feature_columns: list[str]) -> dict[str, Any]:
    try:
        train = train_features(horizon_minutes)
    except DataUnavailableError:
        train = pd.DataFrame()

    baselines: dict[str, Any] = {}
    if train.empty:
        return baselines

    for feature in feature_columns:
        if feature not in train.columns:
            continue
        series = train[feature].replace([np.inf, -np.inf], np.nan).dropna()
        if series.empty:
            continue
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
            baselines[feature] = float(series.median())
        else:
            mode = series.astype(str).mode()
            baselines[feature] = mode.iloc[0] if not mode.empty else str(series.iloc[0])
    return baselines


@router.get("/{prediction_id}/explain", response_model=PredictionExplanation)
def explain_prediction(
    prediction_id: str,
    horizon: str = Query("15m", description="Forecast horizon (15m or 60m)"),
    top_n: int = Query(8, ge=3, le=20, description="Number of feature contributions to return"),
):
    """Get a model-derived explanation for a prediction.

    Args:
        prediction_id: Prediction ID (segment_id_timestamp)
        horizon: Forecast horizon
        top_n: Number of feature contributions

    Returns:
        Model prediction explanation with top contributing features
    """
    try:
        normalized_horizon = normalize_horizon(horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        artifact = load_model(normalized_horizon)
        estimator = estimator_from_artifact(artifact)
        feature_columns = feature_columns_for_model(artifact, normalized_horizon)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    segment_id = prediction_id.split(":", 1)[0]
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = latest[latest["segment_id"].astype(str) == str(segment_id)]
    if rows.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No local feature row found for prediction or segment '{prediction_id}'",
        )

    row = rows.sort_values("timestamp").iloc[-1]
    frame, missing = _feature_frame(row, feature_columns)
    try:
        predicted_speed = float(estimator.predict(frame)[0])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not explain model prediction: {exc}") from exc

    horizon_minutes = 15 if normalized_horizon == "15m" else 60
    baselines = _baseline_values(horizon_minutes, feature_columns)
    contributions: list[Feature] = []
    for feature in feature_columns:
        if feature not in frame.columns:
            continue
        baseline_value = baselines.get(feature)
        if baseline_value is None:
            continue
        perturbed = frame.copy()
        perturbed.loc[0, feature] = baseline_value
        try:
            baseline_prediction = float(estimator.predict(perturbed)[0])
        except Exception:
            continue
        contribution = predicted_speed - baseline_prediction
        if abs(contribution) < 0.001:
            continue
        contributions.append(
            Feature(
                name=feature,
                value=_jsonable(frame.loc[0, feature]),
                baseline_value=_jsonable(baseline_value),
                shap_value=round(contribution, 3),
                direction="raises_speed" if contribution > 0 else "lowers_speed",
            )
        )

    contributions = sorted(contributions, key=lambda item: abs(item.shap_value), reverse=True)[:top_n]
    current_speed = row.get("currentSpeed")
    current_jam_factor = row.get("jamFactor")
    weather_temperature = _optional_float(row, "weather_temperature")
    weather_humidity = _optional_float(row, "weather_humidity")
    weather_visibility = _optional_float(row, "weather_visibility")
    weather_rain = _optional_float(row, "weather_rain_1h", zero_is_missing=False)
    if weather_temperature is None and weather_humidity is None and weather_visibility is None:
        weather_rain = None

    return PredictionExplanation(
        prediction_id=prediction_id,
        segment_id=str(row["segment_id"]),
        horizon=normalized_horizon,
        predicted_speed=round(predicted_speed, 3),
        current_speed=round(float(current_speed), 3) if pd.notna(current_speed) else None,
        current_jam_factor=round(float(current_jam_factor), 3) if pd.notna(current_jam_factor) else None,
        model_name=model_name_from_artifact(artifact),
        model_artifact=artifact_name(normalized_horizon),
        model_source=str(model_dir()),
        data_source="gold_local",
        attribution_method="single_feature_baseline_perturbation",
        required_feature_count=len(feature_columns),
        available_feature_count=len(feature_columns) - len(missing),
        filled_feature_count=len(missing),
        missing_features=missing[:50],
        top_features=contributions,
        weather_context={
            "temperature": weather_temperature,
            "humidity": weather_humidity,
            "rain_1h": weather_rain,
            "visibility": weather_visibility,
            "source": "OpenWeatherMap",
            "fallback": "neutral_weather_features" if weather_temperature is None and weather_humidity is None and weather_visibility is None else None,
        },
        baseline_context={
            "p15": _optional_float(row, "p15"),
            "p50": _optional_float(row, "p50") or _optional_float(row, "speed_rolling_avg_60m"),
            "p85": _optional_float(row, "p85"),
            "typical_hour_avg": _optional_float(row, "speed_rolling_avg_60m"),
            "mode": "training-median-baseline",
        },
    )
