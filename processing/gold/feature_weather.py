"""Spark job: Engineer weather features via asof join."""

import logging
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def engineer_weather_features(df_traffic, df_weather):
    """Add weather features via asof join on (city, timestamp).

    Args:
        df_traffic: DataFrame with traffic data (segment_id, city, timestamp, lat, lon)
        df_weather: DataFrame with weather data (city, timestamp, temp, humidity, rain_1h, visibility, wind_speed)

    Returns:
        DataFrame with weather features added
    """
    # Ensure timestamps are timestamps
    df_traffic = df_traffic.withColumn("timestamp", F.col("timestamp").cast("timestamp"))
    df_weather = df_weather.withColumn("timestamp", F.col("timestamp").cast("timestamp"))

    # AsOf join: for each traffic record, find the nearest weather record within the same city
    # We'll use a window-based approach since Spark doesn't have true asof join

    from pyspark.sql.window import Window

    # Window to find the most recent weather data within last 30 minutes
    weather_window = Window.partitionBy("city").orderBy(
        F.col("timestamp").desc()
    ).rowsBetween(Window.unboundedPreceding, 0)

    # Select weather features and rank them by recency
    df_weather_ranked = df_weather.withColumn(
        "weather_rank",
        F.row_number().over(weather_window)
    ).filter(F.col("weather_rank") == 1)  # Most recent weather per city

    # Join traffic with most recent weather per city
    df_joined = df_traffic.join(
        df_weather_ranked.select("city", "timestamp", "temperature", "humidity", "rain_1h", "visibility", "wind_speed"),
        on=["city"],
        how="left"
    )

    # If no exact timestamp match within city, use closest weather timestamp
    # This is a simple approach; production might use window-based matching

    # Rename weather columns and fill nulls
    weather_features = ["temperature", "humidity", "rain_1h", "visibility", "wind_speed"]
    for feat in weather_features:
        if feat in df_joined.columns:
            df_joined = df_joined.withColumn(
                f"weather_{feat}",
                F.coalesce(F.col(feat), F.lit(0.0))
            ).drop(feat)
        else:
            df_joined = df_joined.withColumn(f"weather_{feat}", F.lit(0.0))

    # Create categorical weather feature: rain/no rain
    df_joined = df_joined.withColumn(
        "has_rain",
        F.when(F.col("weather_rain_1h") > 0.1, 1).otherwise(0)
    )

    # Weather severity categories
    df_joined = df_joined.withColumn(
        "weather_severity",
        F.when(F.col("weather_visibility") < 1, 3)  # Fog/low visibility
        .when(F.col("weather_rain_1h") > 10, 2)  # Heavy rain
        .when(F.col("weather_rain_1h") > 0.1, 1)  # Light rain
        .otherwise(0)  # Clear
    )

    logger.info("✅ Engineered weather features via asof join")

    return df_joined
