"""Spark job: Match traffic ↔ weather by nearest time → silver_traffic_weather_matched."""

import logging
import sys
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def match_traffic_weather_asof(spark, warehouse_path: str, max_time_diff_minutes: int = 30):
    """
    Match traffic records to nearest weather record by time.

    For each traffic record:
    - Find weather records for same city
    - Match to nearest timestamp (within ±max_time_diff_minutes)
    - Join all traffic + weather columns
    """
    try:
        logger.info("Starting traffic ↔ weather matching...")

        # Read cleaned data
        df_traffic = spark.read.format("iceberg").load(f"{warehouse_path}/silver_traffic_cleaned")
        df_weather = spark.read.format("iceberg").load(f"{warehouse_path}/silver_weather_cleaned")

        logger.info(f"Traffic records: {df_traffic.count()}")
        logger.info(f"Weather records: {df_weather.count()}")

        # Add timestamp columns for joining
        df_traffic = df_traffic.select(
            "*",
            F.unix_timestamp(F.col("time_bucket")).alias("traffic_unix_ts"),
        )

        df_weather = df_weather.select(
            "*",
            F.unix_timestamp(F.col("time_bucket")).alias("weather_unix_ts"),
        ).select(
            F.col("city"),
            F.col("weather_cell_id"),
            F.col("event_time").alias("weather_event_time"),
            F.col("time_bucket").alias("weather_time_bucket"),
            F.col("temp"),
            F.col("feels_like"),
            F.col("humidity"),
            F.col("pressure"),
            F.col("visibility"),
            F.col("rain_1h"),
            F.col("wind_speed"),
            F.col("wind_deg"),
            F.col("weather_main"),
            F.col("weather_desc"),
            F.col("weather_unix_ts"),
        )

        # For each traffic record, find nearest weather by city + time
        # Window: partitioned by city, ordered by absolute time difference
        window_spec = Window.partitionBy(F.col("city")).orderBy(
            F.abs(F.col("traffic_unix_ts") - F.col("weather_unix_ts"))
        )

        # Cross join traffic + weather, then pick nearest per traffic record
        df_crossed = df_traffic.join(
            df_weather,
            on=F.col("traffic.city") == F.col("weather.city"),
            how="inner"
        )

        # Rename columns to avoid ambiguity
        df_traffic_renamed = df_traffic.select(
            [F.col(c).alias(f"traffic_{c}" if c != "city" else "city") for c in df_traffic.columns]
        )

        df_weather_renamed = df_weather.select(
            [F.col(c).alias(f"weather_{c}" if c not in ["city"] else c) for c in df_weather.columns]
        )

        # Cross join
        df_joined = df_traffic_renamed.join(
            df_weather_renamed,
            on="city",
            how="inner"
        )

        # Calculate time difference
        df_joined = df_joined.withColumn(
            "time_diff_seconds",
            F.abs(F.col("traffic_unix_ts") - F.col("weather_unix_ts")),
        ).withColumn(
            "time_diff_minutes",
            F.col("time_diff_seconds") / 60,
        )

        # Filter to within max time difference
        df_filtered = df_joined.filter(F.col("time_diff_minutes") <= max_time_diff_minutes)

        # Window to pick nearest per traffic record
        window_nearest = Window.partitionBy("traffic_segment_id", "traffic_time_bucket").orderBy(
            "time_diff_minutes"
        )

        df_matched = df_filtered.withColumn(
            "row_num",
            F.row_number().over(window_nearest),
        ).filter(
            F.col("row_num") == 1
        ).drop("row_num", "traffic_unix_ts", "weather_unix_ts", "time_diff_seconds")

        # Select final columns
        df_final = df_matched.select(
            # Traffic columns
            F.col("traffic_source").alias("source"),
            F.col("traffic_provider").alias("provider"),
            F.col("city"),
            F.col("traffic_segment_id").alias("segment_id"),
            F.col("traffic_segment_name").alias("segment_name"),
            F.col("traffic_lat").alias("lat"),
            F.col("traffic_lon").alias("lon"),
            F.col("traffic_event_time").alias("event_time"),
            F.col("traffic_time_bucket").alias("time_bucket"),
            F.col("traffic_currentSpeed").alias("currentSpeed"),
            F.col("traffic_freeFlowSpeed").alias("freeFlowSpeed"),
            F.col("traffic_jamFactor").alias("jamFactor"),
            F.col("traffic_confidence").alias("confidence"),
            # Weather columns
            F.col("weather_cell_id"),
            F.col("weather_event_time"),
            F.col("temp"),
            F.col("feels_like"),
            F.col("humidity"),
            F.col("pressure"),
            F.col("visibility"),
            F.col("rain_1h"),
            F.col("wind_speed"),
            F.col("wind_deg"),
            F.col("weather_main"),
            F.col("time_diff_minutes"),
            # Partitioning
            F.year(F.col("traffic_time_bucket")).alias("_year"),
            F.month(F.col("traffic_time_bucket")).alias("_month"),
            F.dayofmonth(F.col("traffic_time_bucket")).alias("_day"),
        )

        # Write to Silver
        table_path = f"{warehouse_path}/silver_traffic_weather_matched"
        df_final.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", table_path) \
            .partitionBy("_year", "_month", "_day") \
            .save()

        matched_count = df_final.count()
        logger.info(f"✅ Matched records written: {matched_count}")
        logger.info(f"Average time difference: {df_final.agg(F.avg('time_diff_minutes')).collect()[0][0]:.1f} minutes")

        return matched_count

    except Exception as e:
        logger.error(f"Error matching traffic ↔ weather: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import logging as log_module
    log_module.basicConfig(level=log_module.INFO)

    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    from processing.utils.spark_session import get_spark_session
    spark = get_spark_session("match-traffic-weather")
    match_traffic_weather_asof(spark, warehouse_path)
    spark.stop()
