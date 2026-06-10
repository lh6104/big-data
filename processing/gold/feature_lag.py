"""Spark job: Engineer lag features from historical traffic data."""

import logging
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def engineer_lag_features(df):
    """Add lag features: speed from 5, 10, 15 minutes ago.

    Args:
        df: DataFrame with segment_id, timestamp, currentSpeed (ordered by segment_id, timestamp)

    Returns:
        DataFrame with lag features added
    """
    # Window: ordered by timestamp within each segment
    window_spec = Window.partitionBy("segment_id").orderBy("timestamp")

    # Create lag features (each lag = 5 minutes apart)
    # Lag 1: 5 minutes ago
    df = df.withColumn(
        "speed_lag_1",
        F.lag(F.col("currentSpeed")).over(window_spec)
    )

    # Lag 2: 10 minutes ago
    df = df.withColumn(
        "speed_lag_2",
        F.lag(F.col("currentSpeed"), 2).over(window_spec)
    )

    # Lag 3: 15 minutes ago
    df = df.withColumn(
        "speed_lag_3",
        F.lag(F.col("currentSpeed"), 3).over(window_spec)
    )

    # Lag 4: 20 minutes ago
    df = df.withColumn(
        "speed_lag_4",
        F.lag(F.col("currentSpeed"), 4).over(window_spec)
    )

    # Congestion ratio lags
    df = df.withColumn(
        "congestion_lag_1",
        F.lag(F.col("congestion_ratio")).over(window_spec)
    )

    df = df.withColumn(
        "congestion_lag_2",
        F.lag(F.col("congestion_ratio"), 2).over(window_spec)
    )

    # Speed trend (difference from previous observation)
    df = df.withColumn(
        "speed_trend_1",
        F.col("currentSpeed") - F.col("speed_lag_1")
    )

    df = df.withColumn(
        "speed_trend_2",
        F.col("speed_lag_1") - F.col("speed_lag_2")
    )

    # Acceleration/deceleration
    df = df.withColumn(
        "speed_acceleration",
        F.col("speed_trend_1") - F.col("speed_trend_2")
    )

    # Fill NaN lag features with forward fill (previous observation)
    lag_cols = ["speed_lag_1", "speed_lag_2", "speed_lag_3", "speed_lag_4", "congestion_lag_1", "congestion_lag_2"]
    for col in lag_cols:
        df = df.withColumn(
            col,
            F.when(F.isnan(F.col(col)), 0.0)
            .when(F.col(col).isNull(), 0.0)
            .otherwise(F.col(col))
        )

    # Fill trend features
    trend_cols = ["speed_trend_1", "speed_trend_2", "speed_acceleration"]
    for col in trend_cols:
        df = df.withColumn(
            col,
            F.when(F.isnan(F.col(col)), 0.0)
            .when(F.col(col).isNull(), 0.0)
            .otherwise(F.col(col))
        )

    logger.info("✅ Engineered lag features")

    return df
