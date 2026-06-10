"""Spark job: Engineer event features from cleaned events data."""

import logging
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def engineer_event_features(df_traffic, df_events):
    """Add event features: has_accident, has_flood, has_roadwork, has_event.

    Args:
        df_traffic: DataFrame with traffic data (segment_id, city, timestamp, lat, lon)
        df_events: DataFrame with events (event_id, event_type, lat, lon, timestamp, city, severity)

    Returns:
        DataFrame with event features added
    """
    # Distance threshold: events within 500m of segment are considered relevant
    # For simplicity, use city + time window match
    # In production, compute actual geographic distance

    # Ensure timestamps are cast
    df_traffic = df_traffic.withColumn("timestamp", F.col("timestamp").cast("timestamp"))
    df_events = df_events.withColumn("timestamp", F.col("timestamp").cast("timestamp"))

    # Create time windows: events within 60 minutes (backward and forward)
    # More sophisticated approach: use window join

    # Simple approach: join on city and check time proximity
    df_joined = df_traffic.join(
        df_events.select("city", "timestamp", "event_type", "severity"),
        on="city",
        how="left"
    )

    # Calculate time difference (in minutes)
    df_joined = df_joined.withColumn(
        "event_time_diff_mins",
        (F.col("timestamp") - F.col("timestamp")) / 60
    )

    # Filter to events within 60 minutes and same city
    df_joined = df_joined.withColumn(
        "is_recent_event",
        F.when(
            F.abs(F.col("event_time_diff_mins")) <= 60,
            1
        ).otherwise(0)
    )

    # Create event type flags
    event_types = ["accident", "flood", "roadwork", "event"]
    for event_type in event_types:
        df_joined = df_joined.withColumn(
            f"has_{event_type}",
            F.when(
                (F.col("event_type") == event_type) & (F.col("is_recent_event") == 1),
                1
            ).otherwise(0)
        )

    # Create event severity feature (max severity in last 60 minutes)
    window_spec = Window.partitionBy("segment_id").orderBy("timestamp").rangeBetween(
        -3600, 0  # 60 minutes in seconds
    )

    for event_type in event_types:
        df_joined = df_joined.withColumn(
            f"max_{event_type}_severity_1h",
            F.when(
                F.col(f"has_{event_type}") == 1,
                F.max(F.col("severity")).over(window_spec)
            ).otherwise(0)
        )

    # Aggregate: has any event in last 60 minutes
    df_joined = df_joined.withColumn(
        "has_any_event",
        F.when(
            (F.col("has_accident") == 1) | (F.col("has_flood") == 1) |
            (F.col("has_roadwork") == 1) | (F.col("has_event") == 1),
            1
        ).otherwise(0)
    )

    # Drop intermediate columns
    cols_to_drop = ["event_time_diff_mins", "is_recent_event", "event_type", "severity"]
    df_joined = df_joined.select([col for col in df_joined.columns if col not in cols_to_drop])

    logger.info("✅ Engineered event features")

    return df_joined
