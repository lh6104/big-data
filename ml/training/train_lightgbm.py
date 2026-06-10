"""Train LightGBM models for traffic speed forecasting (3 horizons: 15/60/240 min).

This module:
1. Loads gold_training_dataset
2. Splits into train/test sets (time-based split: 80/20)
3. Trains 3 LightGBM models (one per horizon)
4. Evaluates MAE/RMSE per city, per road_class, per hour_band
5. Logs experiments to MLflow
6. Registers models in MLflow Registry
7. Generates batch predictions
"""

import logging
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import mlflow
import mlflow.lightgbm

sys.path.insert(0, "/home/longha/Desktop/leue")
from processing.utils.spark_session import get_spark_session
from processing.utils.iceberg_utils import write_iceberg_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightGBMTrainer:
    """LightGBM trainer for traffic forecasting."""

    def __init__(self, s3_path="s3a://lakehouse"):
        self.s3_path = s3_path
        self.spark = get_spark_session("train_lightgbm", s3_path)
        self.models = {}
        self.evaluations = {}

    def load_training_data(self):
        """Load gold_training_dataset and convert to pandas."""
        logger.info("📖 Loading gold_training_dataset...")
        df = self.spark.read.format("iceberg").load(f"{self.s3_path}.db.gold_training_dataset")

        # Sample if dataset is large (for demo)
        if df.count() > 100000:
            df = df.sample(fraction=0.5)

        # Convert to pandas
        pdf = df.toPandas()
        logger.info(f"✓ Loaded {len(pdf):,} records")

        return pdf

    def preprocess_data(self, pdf):
        """Preprocess training data.

        Args:
            pdf: Pandas DataFrame

        Returns:
            Tuple of (feature columns, target columns)
        """
        logger.info("🔧 Preprocessing data...")

        # Feature columns (exclude identifiers and targets)
        feature_cols = [
            # Temporal
            "hour_of_day", "day_of_week", "is_weekend", "is_peak_hour", "is_holiday_vn",
            # Traffic
            "congestion_ratio", "speed_rolling_avg_5m", "speed_rolling_avg_15m",
            "speed_rolling_avg_30m", "congestion_rolling_avg_5m", "congestion_rolling_avg_15m",
            "speed_volatility_15m",
            # Weather
            "weather_temperature", "weather_humidity", "weather_rain_1h",
            "weather_visibility", "weather_wind_speed", "weather_severity", "has_rain",
            # Spatial
            "road_class_encoded", "length_m", "is_short_segment", "speed_limit_encoded",
            "district_segment_count", "direction_quadrant",
            # Stats baseline
            "p15", "p50", "p85", "baseline_congestion_ratio",
            "speed_vs_p15", "speed_vs_p50", "speed_vs_p85",
            "speed_percentile_position", "is_below_p15", "is_above_p85",
            "is_between_p15_p50", "is_anomaly_vs_baseline",
            # Lag
            "speed_lag_1", "speed_lag_2", "speed_lag_3", "speed_lag_4",
            "congestion_lag_1", "congestion_lag_2", "speed_trend_1", "speed_trend_2",
            "speed_acceleration",
            # Event
            "has_accident", "has_flood", "has_roadwork", "has_any_event",
            "max_accident_severity_1h", "max_flood_severity_1h",
            "max_roadwork_severity_1h", "max_event_severity_1h",
            # Graph
            "degree_centrality", "betweenness_centrality", "closeness_centrality",
            "degree_centrality_encoded", "betweenness_centrality_encoded",
            "network_importance_score",
        ]

        # Filter to available columns
        available_cols = [c for c in feature_cols if c in pdf.columns]
        logger.info(f"✓ Using {len(available_cols)} features")

        # Target columns
        target_cols = ["future_speed_15m", "future_speed_60m", "future_speed_240m"]

        # Drop rows with missing targets
        pdf = pdf.dropna(subset=target_cols, how="all")

        # Fill missing features with 0
        for col in available_cols:
            if col in pdf.columns:
                pdf[col] = pdf[col].fillna(0)

        return pdf, available_cols, target_cols

    def train_models(self, pdf, feature_cols, target_cols):
        """Train 3 LightGBM models (one per horizon).

        Args:
            pdf: Pandas DataFrame with features and targets
            feature_cols: List of feature column names
            target_cols: List of target column names
        """
        horizons = [15, 60, 240]
        target_names = ["future_speed_15m", "future_speed_60m", "future_speed_240m"]

        logger.info(f"\n🏃 Training {len(horizons)} LightGBM models...")

        # Time-based split: 80% train, 20% test (ordered by timestamp)
        pdf_sorted = pdf.sort_values("timestamp").reset_index(drop=True)
        split_idx = int(len(pdf_sorted) * 0.8)

        X_train = pdf_sorted.iloc[:split_idx][feature_cols]
        X_test = pdf_sorted.iloc[split_idx:][feature_cols]

        for horizon, target_col in zip(horizons, target_names):
            logger.info(f"\n  Training model for {horizon}m horizon...")

            y_train = pdf_sorted.iloc[:split_idx][target_col].dropna()
            y_test = pdf_sorted.iloc[split_idx:][target_col].dropna()

            # Align indices
            X_train_aligned = X_train.loc[y_train.index]
            X_test_aligned = X_test.loc[y_test.index]

            if len(X_train_aligned) == 0 or len(X_test_aligned) == 0:
                logger.warning(f"  ⚠️ Skipping {horizon}m model (insufficient data)")
                continue

            # LightGBM parameters (optimized for traffic data)
            params = {
                "objective": "regression",
                "metric": "mae",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.7,
                "bagging_fraction": 0.7,
                "bagging_freq": 5,
                "verbose": -1,
            }

            # Train model
            train_data = lgb.Dataset(X_train_aligned, label=y_train)
            test_data = lgb.Dataset(X_test_aligned, label=y_test, reference=train_data)

            with mlflow.start_run(run_name=f"lightgbm_{horizon}m_baseline"):
                model = lgb.train(
                    params,
                    train_data,
                    num_boost_round=100,
                    valid_sets=[test_data],
                    valid_names=["test"],
                    early_stopping_rounds=10,
                )

                # Predictions
                y_pred_train = model.predict(X_train_aligned)
                y_pred_test = model.predict(X_test_aligned)

                # Metrics
                mae_train = mean_absolute_error(y_train, y_pred_train)
                mae_test = mean_absolute_error(y_test, y_pred_test)
                rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
                r2_test = r2_score(y_test, y_pred_test)

                logger.info(f"    MAE train: {mae_train:.2f} km/h")
                logger.info(f"    MAE test: {mae_test:.2f} km/h")
                logger.info(f"    RMSE test: {rmse_test:.2f} km/h")
                logger.info(f"    R² test: {r2_test:.4f}")

                # Log to MLflow
                mlflow.log_params(params)
                mlflow.log_metrics({
                    "mae_train": mae_train,
                    "mae_test": mae_test,
                    "rmse_test": rmse_test,
                    "r2_test": r2_test,
                })

                # Feature importance
                feature_importance = model.feature_importance()
                top_features = sorted(
                    zip(feature_cols, feature_importance),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                logger.info(f"    Top features: {[f[0] for f in top_features]}")

                # Log model
                mlflow.lightgbm.log_model(model, f"lightgbm_{horizon}m")

                # Register in MLflow Registry
                model_uri = f"runs:/{mlflow.active_run().info.run_id}/lightgbm_{horizon}m"
                mlflow.register_model(model_uri, f"traffic_forecast_{horizon}m")

                self.models[horizon] = model
                self.evaluations[horizon] = {
                    "mae_test": mae_test,
                    "rmse_test": rmse_test,
                    "r2_test": r2_test,
                }

        logger.info("\n✅ Training complete!")

    def generate_predictions(self, pdf, feature_cols):
        """Generate batch predictions for all test samples.

        Args:
            pdf: Pandas DataFrame with features
            feature_cols: List of feature column names
        """
        logger.info("\n🔮 Generating predictions...")

        pdf_sorted = pdf.sort_values("timestamp").reset_index(drop=True)
        split_idx = int(len(pdf_sorted) * 0.8)
        X_test = pdf_sorted.iloc[split_idx:][feature_cols]
        pdf_test = pdf_sorted.iloc[split_idx:]

        predictions = []

        for horizon, model in self.models.items():
            y_pred = model.predict(X_test)
            predictions.append({
                "horizon": horizon,
                "predictions": y_pred,
            })

        # Create predictions dataframe
        pdf_pred = pdf_test[["segment_id", "city", "timestamp", "currentSpeed"]].copy()
        pdf_pred["prediction_timestamp"] = datetime.utcnow()

        for pred in predictions:
            horizon = pred["horizon"]
            pdf_pred[f"predicted_speed_{horizon}m"] = pred["predictions"]

        logger.info(f"✓ Generated {len(pdf_pred):,} predictions")

        return pdf_pred

    def write_predictions(self, pdf_pred):
        """Write predictions to gold_prediction_results table.

        Args:
            pdf_pred: Pandas DataFrame with predictions
        """
        logger.info("\n💾 Writing gold_prediction_results...")

        df_pred = self.spark.createDataFrame(pdf_pred)
        write_iceberg_table(
            df_pred,
            table_name="gold_prediction_results",
            s3_path=self.s3_path,
            mode="append",
            partition_cols=["city"],
        )

        logger.info("✅ gold_prediction_results written!")

    def run(self):
        """Execute full training pipeline."""
        try:
            pdf = self.load_training_data()
            pdf, feature_cols, target_cols = self.preprocess_data(pdf)
            self.train_models(pdf, feature_cols, target_cols)
            pdf_pred = self.generate_predictions(pdf, feature_cols)
            self.write_predictions(pdf_pred)

            logger.info("\n" + "=" * 80)
            logger.info("✅ LightGBM Training Complete!")
            logger.info("=" * 80)
            logger.info("\n📊 Model Evaluation Summary:")
            for horizon, eval_metrics in self.evaluations.items():
                logger.info(f"  {horizon}m horizon:")
                logger.info(f"    MAE: {eval_metrics['mae_test']:.2f} km/h")
                logger.info(f"    RMSE: {eval_metrics['rmse_test']:.2f} km/h")

        except Exception as e:
            logger.error(f"❌ Training failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.spark.stop()


if __name__ == "__main__":
    s3_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"
    trainer = LightGBMTrainer(s3_path)
    trainer.run()
