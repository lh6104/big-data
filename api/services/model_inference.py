"""Demo speed-model inference backed by local training artifacts."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api.services.local_data import PROJECT_ROOT, latest_by_segment, traffic_features
from intelligence.prediction_reliability import assess_prediction_reliability


DEFAULT_MODEL_DIR = "results/cta_model_pack_final_v1_20260613T162016Z"
LEGACY_MODEL_DIR = "results/cta_training_outputs_balanced_v3_latest"
MODEL_ARTIFACT_CANDIDATES = {
    "15m": [
        "models/selected_model_15m_lightgbm.joblib",
        "selected_model_15m_speed_lightgbm_main.joblib",
        "best_model_15m_speed_extra_trees.joblib",
    ],
    "60m": [
        "models/selected_model_60m_lightgbm.joblib",
        "selected_model_60m_speed_lightgbm_main.joblib",
        "best_model_60m_speed_extra_trees.joblib",
    ],
    "240m": [
        "models/selected_model_240m_lightgbm.joblib",
        "selected_model_240m_speed_lightgbm_main.joblib",
        "best_model_240m_speed_extra_trees.joblib",
    ],
}
MODEL_TASKS = {"15m": "15m_speed", "60m": "60m_speed", "240m": "240m_speed"}
NON_FEATURE_COLUMNS = {
    "target",
    "target_speed",
    "target_speed_15m",
    "target_speed_60m",
    "timestamp",
    "time_bucket",
    "time_bucket_local",
    "prediction",
    "predicted_speed_kph",
    "actual_target_speed_kph",
    "horizon",
    "task",
    "model",
}


class ModelUnavailableError(RuntimeError):
    """Raised when a requested model cannot be used for inference."""


@dataclass
class ModelPrediction:
    segment_id: str
    horizon: str
    predicted_speed: float | None
    current_speed: float | None
    current_jam_factor: float | None
    model_name: str
    model_artifact: str
    model_source: str
    data_source: str
    input_source: str
    is_fallback: bool
    required_feature_count: int
    available_feature_count: int
    filled_feature_count: int
    feature_fill_strategy: str | None
    missing_features: list[str]
    latest_timestamp: str | None
    warning: str | None = None
    confidence_band: tuple[float, float] | None = None
    reliability_level: str | None = None
    feature_coverage_ratio: float | None = None
    data_freshness_seconds: int | None = None


def normalize_horizon(horizon: str | int) -> str:
    text = str(horizon).strip().lower()
    if text in {"15", "15m", "15min", "15mins"}:
        return "15m"
    if text in {"60", "60m", "60min", "60mins"}:
        return "60m"
    if text in {"240", "240m", "240min", "240mins", "4h"}:
        return "240m"
    raise ValueError("horizon must be 15m, 60m, or 240m")


def with_reliability(prediction: ModelPrediction) -> ModelPrediction:
    reliability = assess_prediction_reliability(prediction)
    prediction.confidence_band = reliability.confidence_band
    prediction.reliability_level = reliability.reliability_level
    prediction.feature_coverage_ratio = reliability.feature_coverage_ratio
    prediction.data_freshness_seconds = reliability.data_freshness_seconds
    return prediction


def model_dir() -> Path:
    configured = Path(os.getenv("CTA_MODEL_DIR") or os.getenv("MODEL_DIR") or DEFAULT_MODEL_DIR)
    root = configured if configured.is_absolute() else PROJECT_ROOT / configured
    if root.exists():
        return root
    if not os.getenv("CTA_MODEL_DIR") and not os.getenv("MODEL_DIR"):
        legacy = PROJECT_ROOT / LEGACY_MODEL_DIR
        if legacy.exists():
            return legacy
    return root


def artifact_name(horizon: str) -> str:
    root = model_dir()
    for name in MODEL_ARTIFACT_CANDIDATES[horizon]:
        if (root / name).exists():
            return name
    return MODEL_ARTIFACT_CANDIDATES[horizon][0]


def artifact_path(horizon: str) -> Path:
    return model_dir() / artifact_name(horizon)


def _artifact_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


@lru_cache(maxsize=3)
def _load_model_cached(model_dir_str: str, horizon: str) -> Any:
    root = Path(model_dir_str)
    artifact = next((name for name in MODEL_ARTIFACT_CANDIDATES[horizon] if (root / name).exists()), None)
    path = root / (artifact or MODEL_ARTIFACT_CANDIDATES[horizon][0])
    if not path.exists():
        raise ModelUnavailableError(f"Model artifact is missing: {path}")
    try:
        import joblib

        return joblib.load(path)
    except Exception as exc:  # pragma: no cover - dependency/schema dependent
        raise ModelUnavailableError(f"Could not load model artifact {path.name}: {exc}") from exc


def load_model(horizon: str) -> Any:
    return _load_model_cached(str(model_dir()), horizon)


def estimator_from_artifact(artifact: Any) -> Any:
    if isinstance(artifact, dict) and "model" in artifact:
        return artifact["model"]
    return artifact


def model_name_from_artifact(artifact: Any) -> str:
    if isinstance(artifact, dict):
        return str(artifact.get("selected_model") or artifact.get("model_name") or "model")
    return "extra_trees"


def _read_training_summary() -> list[dict[str, Any]]:
    manifest_path = model_dir() / "metadata" / "model_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            selected_metrics = manifest.get("selected_metrics", {})
            selected_models = manifest.get("selected_models", {})
            rows = []
            for horizon, metrics in selected_metrics.items():
                model_info = selected_models.get(horizon, {})
                rows.append(
                    {
                        "task": f"{horizon}_speed",
                        "selected_model": metrics.get("model", model_info.get("model_name", "")),
                        "mae": metrics.get("MAE", metrics.get("mae", 0.0)),
                        "rmse": metrics.get("RMSE", metrics.get("rmse", 0.0)),
                        "r2": metrics.get("R2", metrics.get("r2", 0.0)),
                        "rows": metrics.get("n", 0),
                        "feature_count": model_info.get("feature_count", 0),
                        "artifact": model_info.get("model_file", ""),
                    }
                )
            return rows
        except Exception:
            pass
    path = model_dir() / "training_summary.json"
    if not path.exists():
        path = model_dir() / "report_summary_selected_models.csv"
        if not path.exists():
            return []
        try:
            rows = pd.read_csv(path).to_dict(orient="records")
            artifact_manifest = model_dir() / "ml_upgrade_pack" / "selected_lightgbm_artifacts.csv"
            artifact_rows = {}
            if artifact_manifest.exists():
                try:
                    artifact_rows = {
                        str(item.get("horizon")): item
                        for item in pd.read_csv(artifact_manifest).to_dict(orient="records")
                    }
                except Exception:
                    artifact_rows = {}
            manifest_path = model_dir() / "ml_upgrade_pack" / "artifact_manifest.json"
            manifest_rows = {}
            if manifest_path.exists():
                try:
                    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_rows = {
                        str(item.get("horizon")): item
                        for item in payload
                        if isinstance(item, dict)
                    }
                except Exception:
                    manifest_rows = {}
            normalized = []
            for item in rows:
                task = str(item.get("task", ""))
                horizon = "15m" if "15m" in task else "60m" if "60m" in task else "240m" if "240m" in task else ""
                artifact_info = artifact_rows.get(horizon, {})
                manifest_info = manifest_rows.get(horizon, {})
                normalized.append(
                    {
                        **item,
                        "mae": item.get("mae", item.get("test_MAE", item.get("val_MAE", 0.0))),
                        "rmse": item.get("rmse", item.get("test_RMSE", item.get("val_RMSE", 0.0))),
                        "r2": item.get("r2", item.get("test_R2", item.get("val_R2", 0.0))),
                        "rows": manifest_info.get("test_rows", manifest_info.get("training_rows", item.get("rows", 0))),
                        "feature_count": artifact_info.get(
                            "required_feature_count",
                            manifest_info.get("required_feature_count", item.get("feature_count", 0)),
                        ),
                        "artifact": artifact_info.get("artifact", item.get("artifact", "")),
                    }
                )
            return normalized
        except Exception:
            return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else [payload]


def _read_metrics() -> pd.DataFrame:
    path = model_dir() / "metrics_all_models.csv"
    if not path.exists():
        path = model_dir() / "leaderboard_all_horizons.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_inference_examples() -> pd.DataFrame:
    path = model_dir() / "inference_examples.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def feature_columns_for_model(model: Any, horizon: str) -> list[str]:
    if isinstance(model, dict):
        names = (
            model.get("feature_cols")
            or model.get("feature_columns")
            or model.get("features")
            or model.get("expected_input_features")
        )
        if names is not None:
            return [str(name) for name in list(names) if str(name) not in NON_FEATURE_COLUMNS]
        model = estimator_from_artifact(model)

    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(name) for name in list(names) if str(name) not in NON_FEATURE_COLUMNS]

    for schema_path in [model_dir() / "metadata" / "feature_schema_used.json", model_dir() / "metadata" / "model_manifest.json"]:
        if not schema_path.exists():
            continue
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
            schema = payload.get("feature_schema", payload)
            features = list(schema.get("numeric_features", [])) + list(schema.get("categorical_features", []))
            if features:
                return [str(feature) for feature in features if str(feature) not in NON_FEATURE_COLUMNS]
        except Exception:
            pass

    path = model_dir() / "feature_importance_best_models.csv"
    model_filter = "extra_trees"
    feature_column = "feature"
    if not path.exists():
        path = model_dir() / "feature_importance_selected_models.csv"
        model_filter = "lightgbm_main"
    if path.exists():
        try:
            df = pd.read_csv(path)
            task = MODEL_TASKS[horizon]
            model_column = "model" if "model" in df.columns else "selected_model"
            features = df[(df["task"] == task) & (df[model_column] == model_filter)][feature_column].dropna().astype(str)
            return [feature for feature in features.drop_duplicates().tolist() if feature not in NON_FEATURE_COLUMNS]
        except Exception:
            pass
    raise ModelUnavailableError("Could not determine model feature columns")


def _scalar(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if pd.isna(value):
        return None
    return value


def _time_value(row: pd.Series, name: str) -> float | int | None:
    raw = row.get("time_bucket", row.get("timestamp"))
    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return None
    hour = int(ts.hour)
    minute = int(ts.minute)
    dow = int(ts.dayofweek)
    if name in {"local_hour", "hour_of_day"}:
        return hour
    if name == "local_minute":
        return minute
    if name in {"day_of_week", "local_dow"}:
        return dow
    if name == "month_of_year":
        return int(ts.month)
    if name == "day_of_month":
        return int(ts.day)
    if name == "is_weekend":
        return int(dow in {5, 6})
    if name == "is_peak_hour":
        return int(hour in {7, 8, 9, 16, 17, 18, 19})
    if name == "hour_sin":
        return math.sin(2 * math.pi * hour / 24)
    if name == "hour_cos":
        return math.cos(2 * math.pi * hour / 24)
    if name in {"day_of_week_sin", "dow_sin"}:
        return math.sin(2 * math.pi * dow / 7)
    if name in {"day_of_week_cos", "dow_cos"}:
        return math.cos(2 * math.pi * dow / 7)
    return None


def _derived_feature(row: pd.Series, feature: str) -> Any:
    aliases = {
        "current_speed_kph": "currentSpeed",
        "free_flow_speed_kph": "freeFlowSpeed",
        "current_jam_factor": "jamFactor",
        "jam_factor": "jamFactor",
        "latitude": "lat",
        "longitude": "lon",
        "city_key": "city",
        "road_name": "segment_name",
        "road": "segment_name",
        "road_class": "road_class_encoded",
        "is_vn_public_holiday": "is_holiday_vn",
        "weather_temperature_c": "weather_temperature",
        "weather_humidity_pct": "weather_humidity",
        "weather_wind_speed_mps": "weather_wind_speed",
        "weather_rain_1h_mm": "weather_rain_1h",
        "weather_visibility_m": "weather_visibility",
        "rain_flag": "has_rain",
        "weather_risk_score": "weather_severity",
        "eventctx_has_event_signal_v1": "has_any_event",
        "event_severity_score": "max_event_severity_1h",
        "district_name": "district",
        "speed_roll_mean_4": "speed_rolling_avg_15m",
        "speed_roll_mean_6": "speed_rolling_avg_30m",
        "speed_roll_mean_12": "speed_rolling_avg_60m",
        "speed_roll_std_4": "speed_volatility_15m",
        "speed_roll_std_6": "speed_volatility_30m",
        "speed_roll_std_12": "speed_volatility_30m",
        "congestion_roll_mean_4": "congestion_rolling_avg_15m",
        "congestion_roll_mean_6": "congestion_rolling_avg_30m",
        "congestion_roll_mean_12": "congestion_rolling_avg_60m",
        "jam_roll_mean_4": "congestion_rolling_avg_15m",
        "jam_roll_mean_12": "congestion_rolling_avg_60m",
    }
    if feature in aliases and aliases[feature] in row:
        return _scalar(row[aliases[feature]])
    if feature.startswith("jam_lag_"):
        alias = feature.replace("jam_lag_", "congestion_lag_")
        if alias in row:
            return _scalar(row[alias])
    if feature == "speed_ratio":
        speed = row.get("currentSpeed")
        free_flow = row.get("freeFlowSpeed")
        if pd.notna(speed) and pd.notna(free_flow) and float(free_flow) > 0:
            return float(speed) / float(free_flow)
    if feature == "rain_intensity_level":
        rain = row.get("weather_rain_1h", 0)
        if pd.notna(rain):
            rain_value = float(rain)
            if rain_value >= 10:
                return "heavy"
            if rain_value > 0:
                return "light"
        return "none"
    if feature == "weather_main":
        return "rain" if bool(row.get("has_rain", False)) else "clear"
    if feature == "event_type":
        if bool(row.get("has_accident", False)):
            return "accident"
        if bool(row.get("has_flood", False)):
            return "flood"
        if bool(row.get("has_roadwork", False)):
            return "roadwork"
        return "none"
    if feature in {"heavy_rain_flag", "rain_roll_sum_4", "rain_roll_sum_12", "rain_lag_1", "rain_lag_4"}:
        rain = row.get("weather_rain_1h", 0)
        if pd.notna(rain):
            return float(rain)
    if feature == "row_has_complete_lag_features":
        return int(bool(row.get("valid_history_60m", row.get("valid_history_30m", False))))
    time_value = _time_value(row, feature)
    if time_value is not None:
        return time_value
    return None


def _default_for_feature(feature: str) -> Any:
    text = feature.lower()
    categorical_tokens = [
        "city",
        "district",
        "road",
        "segment",
        "weather_main",
        "weather_desc",
        "source",
        "peak_period",
        "corridor",
        "rain_intensity",
        "event_type",
    ]
    if any(token in text for token in categorical_tokens):
        return "unknown"
    return 0.0


def _feature_frame(row: pd.Series, feature_columns: list[str]) -> tuple[pd.DataFrame, list[str]]:
    values: dict[str, Any] = {}
    missing: list[str] = []
    for feature in feature_columns:
        value = _scalar(row[feature]) if feature in row else None
        if value is None:
            value = _derived_feature(row, feature)
        if value is None:
            missing.append(feature)
            value = _default_for_feature(feature)
        values[feature] = value
    return pd.DataFrame([values], columns=feature_columns), missing


def _fallback_from_examples(segment_id: str, horizon: str, warning: str) -> ModelPrediction:
    examples = _read_inference_examples()
    task = MODEL_TASKS[horizon]
    row = examples[examples.get("task", pd.Series(dtype=str)) == task].head(1)
    if row.empty:
        raise ModelUnavailableError(warning)
    item = row.iloc[0]
    return with_reliability(ModelPrediction(
        segment_id=segment_id,
        horizon=horizon,
        predicted_speed=float(item.get("predicted_speed_kph")) if pd.notna(item.get("predicted_speed_kph")) else None,
        current_speed=float(item.get("current_speed_kph")) if pd.notna(item.get("current_speed_kph")) else None,
        current_jam_factor=float(item.get("current_jam_factor")) if pd.notna(item.get("current_jam_factor")) else None,
        model_name=str(item.get("model", "extra_trees")),
        model_artifact=artifact_name(horizon),
        model_source=str(model_dir().relative_to(PROJECT_ROOT)) if model_dir().is_relative_to(PROJECT_ROOT) else str(model_dir()),
        data_source="inference_examples",
        input_source="inference_examples",
        is_fallback=True,
        required_feature_count=0,
        available_feature_count=0,
        filled_feature_count=0,
        feature_fill_strategy=None,
        missing_features=[],
        latest_timestamp=str(item.get("time_bucket_local")) if pd.notna(item.get("time_bucket_local")) else None,
        warning=warning,
    ))


def predict_from_features(horizon: str | int, features: dict[str, Any]) -> ModelPrediction:
    normalized = normalize_horizon(horizon)
    artifact = load_model(normalized)
    estimator = estimator_from_artifact(artifact)
    feature_columns = feature_columns_for_model(artifact, normalized)
    frame = pd.DataFrame([features], columns=feature_columns)
    missing = [column for column in feature_columns if column not in features]
    for column in missing:
        frame[column] = _default_for_feature(column)
    prediction = float(estimator.predict(frame[feature_columns])[0])
    return with_reliability(ModelPrediction(
        segment_id=str(features.get("segment_id", "ad_hoc")),
        horizon=normalized,
        predicted_speed=round(prediction, 3),
        current_speed=float(features["currentSpeed"]) if "currentSpeed" in features else None,
        current_jam_factor=float(features["jamFactor"]) if "jamFactor" in features else None,
        model_name=model_name_from_artifact(artifact),
        model_artifact=artifact_name(normalized),
        model_source=str(model_dir().relative_to(PROJECT_ROOT)) if model_dir().is_relative_to(PROJECT_ROOT) else str(model_dir()),
        data_source="request_features",
        input_source="request_features",
        is_fallback=False,
        required_feature_count=len(feature_columns),
        available_feature_count=len(feature_columns) - len(missing),
        filled_feature_count=len(missing),
        feature_fill_strategy="missing_features_filled_with_zero_or_unknown" if missing else None,
        missing_features=missing[:50],
        latest_timestamp=None,
    ))


def _predict_from_gold_row(
    row: pd.Series,
    normalized: str,
    artifact: Any,
    estimator: Any,
    feature_columns: list[str],
) -> ModelPrediction:
    frame, missing = _feature_frame(row, feature_columns)
    prediction = float(estimator.predict(frame)[0])
    latest_timestamp = row.get("timestamp", row.get("time_bucket"))
    segment_id = str(row.get("segment_id", "unknown"))
    return with_reliability(ModelPrediction(
        segment_id=segment_id,
        horizon=normalized,
        predicted_speed=round(prediction, 3),
        current_speed=round(float(row["currentSpeed"]), 3) if "currentSpeed" in row and pd.notna(row["currentSpeed"]) else None,
        current_jam_factor=round(float(row["jamFactor"]), 3) if "jamFactor" in row and pd.notna(row["jamFactor"]) else None,
        model_name=model_name_from_artifact(artifact),
        model_artifact=artifact_name(normalized),
        model_source=str(model_dir().relative_to(PROJECT_ROOT)) if model_dir().is_relative_to(PROJECT_ROOT) else str(model_dir()),
        data_source="gold_local",
        input_source="latest_segment_features",
        is_fallback=False,
        required_feature_count=len(feature_columns),
        available_feature_count=len(feature_columns) - len(missing),
        filled_feature_count=len(missing),
        feature_fill_strategy="missing_features_filled_with_zero_or_unknown" if missing else None,
        missing_features=missing[:50],
        latest_timestamp=pd.to_datetime(latest_timestamp).isoformat() if pd.notna(latest_timestamp) else None,
        warning="Some required model features were filled for demo inference." if missing else None,
    ))


def predict_for_feature_row(row: pd.Series, horizon: str | int) -> ModelPrediction:
    """Predict from an already selected Gold feature row.

    This avoids reloading and re-filtering the full local Gold dataset for
    per-segment loops such as prototype predicted hotspot scoring.
    """
    normalized = normalize_horizon(horizon)
    artifact = load_model(normalized)
    estimator = estimator_from_artifact(artifact)
    feature_columns = feature_columns_for_model(artifact, normalized)
    try:
        return _predict_from_gold_row(row, normalized, artifact, estimator, feature_columns)
    except Exception as exc:
        segment_id = str(row.get("segment_id", "unknown"))
        return _fallback_from_examples(
            segment_id,
            normalized,
            f"Local gold row is not compatible with model schema; used bundled inference example. Detail: {exc}",
        )


def predict_for_feature_rows(rows: pd.DataFrame, horizon: str | int) -> list[ModelPrediction]:
    """Predict for multiple already selected Gold feature rows in one estimator call."""
    if rows.empty:
        return []
    normalized = normalize_horizon(horizon)
    artifact = load_model(normalized)
    estimator = estimator_from_artifact(artifact)
    feature_columns = feature_columns_for_model(artifact, normalized)

    frames: list[pd.DataFrame] = []
    missing_by_row: list[list[str]] = []
    source_rows: list[pd.Series] = []
    for _, row in rows.iterrows():
        frame, missing = _feature_frame(row, feature_columns)
        frames.append(frame)
        missing_by_row.append(missing)
        source_rows.append(row)

    if not frames:
        return []
    feature_frame = pd.concat(frames, ignore_index=True)
    predictions = estimator.predict(feature_frame[feature_columns])
    output: list[ModelPrediction] = []
    for row, missing, prediction in zip(source_rows, missing_by_row, predictions):
        latest_timestamp = row.get("timestamp", row.get("time_bucket"))
        output.append(
            with_reliability(ModelPrediction(
                segment_id=str(row.get("segment_id", "unknown")),
                horizon=normalized,
                predicted_speed=round(float(prediction), 3),
                current_speed=round(float(row["currentSpeed"]), 3)
                if "currentSpeed" in row and pd.notna(row["currentSpeed"])
                else None,
                current_jam_factor=round(float(row["jamFactor"]), 3)
                if "jamFactor" in row and pd.notna(row["jamFactor"])
                else None,
                model_name=model_name_from_artifact(artifact),
                model_artifact=artifact_name(normalized),
                model_source=str(model_dir().relative_to(PROJECT_ROOT))
                if model_dir().is_relative_to(PROJECT_ROOT)
                else str(model_dir()),
                data_source="gold_local",
                input_source="latest_segment_features_batch",
                is_fallback=False,
                required_feature_count=len(feature_columns),
                available_feature_count=len(feature_columns) - len(missing),
                filled_feature_count=len(missing),
                feature_fill_strategy="missing_features_filled_with_zero_or_unknown" if missing else None,
                missing_features=missing[:50],
                latest_timestamp=pd.to_datetime(latest_timestamp).isoformat() if pd.notna(latest_timestamp) else None,
                warning="Some required model features were filled for demo inference." if missing else None,
            ))
        )
    return output


def predict_for_segment(segment_id: str, horizon: str | int) -> ModelPrediction:
    normalized = normalize_horizon(horizon)
    try:
        artifact = load_model(normalized)
        estimator = estimator_from_artifact(artifact)
        feature_columns = feature_columns_for_model(artifact, normalized)
    except ModelUnavailableError:
        raise

    latest = latest_by_segment(traffic_features())
    rows = latest[latest["segment_id"].astype(str) == str(segment_id)]
    if rows.empty:
        return _fallback_from_examples(segment_id, normalized, f"No local gold row found for segment '{segment_id}'.")

    row = rows.sort_values("timestamp").iloc[-1]
    try:
        return _predict_from_gold_row(row, normalized, artifact, estimator, feature_columns)
    except Exception as exc:
        return _fallback_from_examples(
            segment_id,
            normalized,
            f"Local gold row is not compatible with model schema; used bundled inference example. Detail: {exc}",
        )


def model_status(load_models: bool = False) -> dict[str, Any]:
    root = model_dir()
    summary = _read_training_summary()
    metrics = _read_metrics()
    metrics_summary = []
    if not metrics.empty:
        selected_models = {str(item.get("selected_model")) for item in summary if item.get("selected_model")}
        if "slice" in metrics.columns:
            model_filter = selected_models or {"extra_trees"}
            metrics_summary = metrics[
                metrics["task"].isin(MODEL_TASKS.values())
                & metrics["model"].astype(str).isin(model_filter)
                & (metrics["slice"] == "all")
            ].to_dict(orient="records")
        elif "model" in metrics.columns:
            model_filter = selected_models or {"lightgbm_main", "extra_trees"}
            metrics_summary = metrics[
                metrics["task"].isin(MODEL_TASKS.values())
                & metrics["model"].astype(str).isin(model_filter)
            ].to_dict(orient="records")

    horizons = {}
    ready = True
    for horizon in MODEL_ARTIFACT_CANDIDATES:
        artifact_file = artifact_name(horizon)
        path = root / artifact_file
        info: dict[str, Any] = {
            "artifact": artifact_file,
            "exists": path.exists(),
            "size_bytes": _artifact_size(path),
            "loaded": False,
            "model_class": None,
            "feature_count": None,
            "model_name": None,
            "error": None,
        }
        if load_models and path.exists():
            try:
                artifact = load_model(horizon)
                model = estimator_from_artifact(artifact)
                info["loaded"] = True
                info["model_class"] = f"{type(model).__module__}.{type(model).__name__}"
                info["feature_count"] = len(feature_columns_for_model(artifact, horizon))
                info["model_name"] = model_name_from_artifact(artifact)
            except ModelUnavailableError as exc:
                info["error"] = str(exc)
        if not info["exists"] or info["error"]:
            ready = False
        horizons[horizon] = info

    if not load_models:
        ready = all(item["exists"] for item in horizons.values())

    return {
        "model_dir": str(root),
        "ready": ready,
        "load_models": load_models,
        "horizons": horizons,
        "training_summary": summary,
        "metrics_summary": metrics_summary,
    }
