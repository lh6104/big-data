"""Spark job: Engineer stats baseline features from TomTom Stats lookup."""

import logging
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def engineer_stats_baseline_features(df_traffic, df_stats_lookup):
    """Add baseline stats features: p15, p50, p85, baseline_ratio, etc.

    Args:
        df_traffic: DataFrame with traffic data (segment_id, city, timestamp, currentSpeed, hour_of_day, day_of_week)
        df_stats_lookup: DataFrame with TomTom stats (segment_id, hour_of_day, day_of_week, p15, p50, p85)

    Returns:
        DataFrame with stats baseline features added
    """
    # Join traffic with stats lookup on (segment_id, hour_of_day, day_of_week)
    df_joined = df_traffic.join(
        df_stats_lookup.select("segment_id", "hour_of_day", "day_of_week", "p15", "p50", "p85"),
        on=["segment_id", "hour_of_day", "day_of_week"],
        how="left"
    )

    # Fill missing percentiles with median of all segments
    # In production, compute global medians per hour_of_day, day_of_week
    df_joined = df_joined.withColumn(
        "p15",
        F.coalesce(F.col("p15"), F.lit(20.0))  # Default 20 km/h
    )
    df_joined = df_joined.withColumn(
        "p50",
        F.coalesce(F.col("p50"), F.lit(30.0))  # Default 30 km/h
    )
    df_joined = df_joined.withColumn(
        "p85",
        F.coalesce(F.col("p85"), F.lit(40.0))  # Default 40 km/h
    )

    # Baseline congestion ratio
    df_joined = df_joined.withColumn(
        "baseline_congestion_ratio",
        F.when(
            F.col("p50") > 0,
            1.0 - (F.col("freeFlowSpeed") * 0.8 / F.col("p50"))
        ).otherwise(0.5)
    )

    # Speed vs percentiles
    df_joined = df_joined.withColumn(
        "speed_vs_p15",
        F.col("currentSpeed") - F.col("p15")
    )
    df_joined = df_joined.withColumn(
        "speed_vs_p50",
        F.col("currentSpeed") - F.col("p50")
    )
    df_joined = df_joined.withColumn(
        "speed_vs_p85",
        F.col("currentSpeed") - F.col("p85")
    )

    # Percentile of current speed within p15-p85 range
    df_joined = df_joined.withColumn(
        "speed_percentile_position",
        F.when(F.col("currentSpeed") <= F.col("p15"), 0.0)
        .when(F.col("currentSpeed") >= F.col("p85"), 1.0)
        .otherwise(
            (F.col("currentSpeed") - F.col("p15")) / (F.col("p85") - F.col("p15"))
        )
    )

    # Flag: below p15 (very slow)
    df_joined = df_joined.withColumn(
        "is_below_p15",
        F.when(F.col("currentSpeed") < F.col("p15"), 1).otherwise(0)
    )

    # Flag: above p85 (fast)
    df_joined = df_joined.withColumn(
        "is_above_p85",
        F.when(F.col("currentSpeed") > F.col("p85"), 1).otherwise(0)
    )

    # Flag: between p15 and p50 (slow but not critical)
    df_joined = df_joined.withColumn(
        "is_between_p15_p50",
        F.when(
            (F.col("currentSpeed") >= F.col("p15")) & (F.col("currentSpeed") < F.col("p50")),
            1
        ).otherwise(0)
    )

    # Outlier detection vs baseline
    df_joined = df_joined.withColumn(
        "is_anomaly_vs_baseline",
        F.when(
            F.abs(F.col("currentSpeed") - F.col("p50")) > 2 * F.col("p50"),
            1
        ).otherwise(0)
    )

    logger.info("✅ Engineered stats baseline features")

    return df_joined
