"""Spark job: Engineer temporal features for traffic predictions."""

import logging
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def engineer_temporal_features(df):
    """Add temporal features: hour, day_of_week, is_weekend, is_peak_hour, is_holiday_vn.

    Args:
        df: DataFrame with 'timestamp' column (UTC+7)

    Returns:
        DataFrame with temporal features added
    """
    df = df.withColumn("timestamp", F.col("timestamp").cast("timestamp"))

    # Extract time components
    df = df.withColumn("hour_of_day", F.hour(F.col("timestamp")))
    df = df.withColumn("day_of_week", F.dayofweek(F.col("timestamp")) - 1)  # 0=Monday
    df = df.withColumn("day_of_month", F.dayofmonth(F.col("timestamp")))
    df = df.withColumn("month_of_year", F.month(F.col("timestamp")))
    df = df.withColumn("week_of_year", F.weekofyear(F.col("timestamp")))
    df = df.withColumn("date", F.to_date(F.col("timestamp")))

    # Categorical features
    df = df.withColumn(
        "is_weekend",
        F.when(F.col("day_of_week").isin([5, 6]), 1).otherwise(0)  # Saturday=5, Sunday=6
    )

    # Peak hours in Vietnam: 7-9am, 11am-1pm, 5-7pm
    df = df.withColumn(
        "is_peak_hour",
        F.when(
            F.col("hour_of_day").isin([7, 8, 9, 11, 12, 13, 17, 18, 19]),
            1
        ).otherwise(0)
    )

    # Vietnamese holidays (hardcoded for 2024-2026)
    vietnamese_holidays = [
        "2024-01-01",  # New Year
        "2024-02-10",  # Lunar New Year
        "2024-02-11",
        "2024-02-12",
        "2024-02-13",
        "2024-04-18",  # Hung Kings' Festival
        "2024-04-30",  # Reunification Day
        "2024-05-01",  # International Labor Day
        "2024-09-02",  # National Day
        "2024-09-03",
        "2025-01-01",
        "2025-01-29",  # Lunar New Year
        "2025-01-30",
        "2025-01-31",
        "2025-02-01",
        "2025-02-02",
        "2025-04-18",
        "2025-04-30",
        "2025-05-01",
        "2025-09-02",
        "2025-09-03",
        "2026-01-01",
        "2026-02-17",  # Lunar New Year
        "2026-02-18",
        "2026-02-19",
        "2026-02-20",
        "2026-02-21",
        "2026-04-18",
        "2026-04-30",
        "2026-05-01",
        "2026-09-02",
        "2026-09-03",
    ]

    holiday_dates = [F.lit(d) for d in vietnamese_holidays]
    df = df.withColumn(
        "is_holiday_vn",
        F.when(F.col("date").cast("string").isin(vietnamese_holidays), 1).otherwise(0)
    )

    logger.info(f"✅ Engineered temporal features: {df.columns}")

    return df
