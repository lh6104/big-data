"""Spark job: Engineer traffic features from current speed data."""

import logging
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def engineer_traffic_features(df):
    """Add traffic features: congestion ratio, rolling averages.

    Args:
        df: DataFrame with currentSpeed, freeFlowSpeed columns

    Returns:
        DataFrame with traffic features added
    """
    # Congestion ratio = 1 - (currentSpeed / freeFlowSpeed)
    df = df.withColumn(
        "congestion_ratio",
        F.when(
            F.col("freeFlowSpeed") > 0,
            1.0 - (F.col("currentSpeed") / F.col("freeFlowSpeed"))
        ).otherwise(0.0)
    )

    # Cap congestion ratio to [0, 1]
    df = df.withColumn(
        "congestion_ratio",
        F.when(F.col("congestion_ratio") < 0, 0.0)
        .when(F.col("congestion_ratio") > 1, 1.0)
        .otherwise(F.col("congestion_ratio"))
    )

    # Rolling average windows (partitioned by segment_id, ordered by timestamp)
    window_5min = Window.partitionBy("segment_id").orderBy("timestamp").rangeBetween(
        -300, 0  # 5 minutes in seconds
    )
    window_15min = Window.partitionBy("segment_id").orderBy("timestamp").rangeBetween(
        -900, 0  # 15 minutes in seconds
    )
    window_30min = Window.partitionBy("segment_id").orderBy("timestamp").rangeBetween(
        -1800, 0  # 30 minutes in seconds
    )

    # Rolling average of currentSpeed
    df = df.withColumn(
        "speed_rolling_avg_5m",
        F.avg(F.col("currentSpeed")).over(window_5min)
    )
    df = df.withColumn(
        "speed_rolling_avg_15m",
        F.avg(F.col("currentSpeed")).over(window_15min)
    )
    df = df.withColumn(
        "speed_rolling_avg_30m",
        F.avg(F.col("currentSpeed")).over(window_30min)
    )

    # Rolling average of congestion_ratio
    df = df.withColumn(
        "congestion_rolling_avg_5m",
        F.avg(F.col("congestion_ratio")).over(window_5min)
    )
    df = df.withColumn(
        "congestion_rolling_avg_15m",
        F.avg(F.col("congestion_ratio")).over(window_15min)
    )
    df = df.withColumn(
        "congestion_rolling_avg_30m",
        F.avg(F.col("congestion_ratio")).over(window_30min)
    )

    # Speed volatility (standard deviation over 15 minutes)
    df = df.withColumn(
        "speed_volatility_15m",
        F.stddev(F.col("currentSpeed")).over(window_15min)
    )

    # Fill NaN with 0
    numeric_cols = [
        "congestion_ratio", "speed_rolling_avg_5m", "speed_rolling_avg_15m",
        "speed_rolling_avg_30m", "congestion_rolling_avg_5m",
        "congestion_rolling_avg_15m", "congestion_rolling_avg_30m",
        "speed_volatility_15m"
    ]
    for col in numeric_cols:
        df = df.withColumn(col, F.when(F.isnan(F.col(col)), 0.0).otherwise(F.col(col)))
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(0.0)))

    logger.info(f"✅ Engineered traffic features")

    return df
