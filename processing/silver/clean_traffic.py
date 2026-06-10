"""Spark job: Clean traffic data → silver_traffic_cleaned."""

import logging
import sys
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

logger = logging.getLogger(__name__)


def validate_coordinates(df, hanoi_bbox, hcmc_bbox):
    """Filter records outside HN/HCM bounding boxes."""
    hcmc_min_lat, hcmc_max_lat, hcmc_min_lon, hcmc_max_lon = hcmc_bbox
    hn_min_lat, hn_max_lat, hn_min_lon, hn_max_lon = hanoi_bbox

    # Keep only records in Hanoi or HCMC
    df_valid = df.filter(
        (
            (F.col("city") == "hanoi") &
            (F.col("lat").between(hn_min_lat, hn_max_lat)) &
            (F.col("lon").between(hn_min_lon, hn_max_lon))
        ) |
        (
            (F.col("city") == "hcmc") &
            (F.col("lat").between(hcmc_min_lat, hcmc_max_lat)) &
            (F.col("lon").between(hcmc_min_lon, hcmc_max_lon))
        )
    )

    return df_valid


def detect_outliers(df):
    """Flag outlier records (speed, jamFactor)."""
    df_clean = df.withColumn(
        "is_outlier",
        (
            (F.col("currentSpeed") < 0) |  # Negative speed
            (F.col("currentSpeed") > 150) |  # > 150 km/h
            (F.col("jamFactor") < 0) |  # Negative jam factor
            (F.col("jamFactor") > 10)  # > 10 jam factor
        ),
    )

    return df_clean


def standardize_timestamp(df):
    """Convert to UTC+7 and standardize format."""
    # Assume timestamps are already in UTC, just add +7 offset
    df_std = df.withColumn(
        "event_time_std",
        F.to_timestamp(
            F.date_format(F.col("event_time") + F.expr("INTERVAL 7 HOURS"), "yyyy-MM-dd HH:mm:ss"),
            "yyyy-MM-dd HH:mm:ss",
        ),
    )

    return df_std


def handle_missing_values(df):
    """Handle null values and flag records."""
    df_filled = df.withColumn(
        "has_null_speed",
        F.col("currentSpeed").isNull(),
    ).withColumn(
        "has_null_timestamp",
        F.col("event_time").isNull(),
    ).withColumn(
        "has_null_segment_id",
        F.col("segment_id").isNull(),
    )

    # Log null counts
    null_speed = df_filled.filter(F.col("has_null_speed")).count()
    null_time = df_filled.filter(F.col("has_null_timestamp")).count()
    null_segment = df_filled.filter(F.col("has_null_segment_id")).count()

    logger.info(f"Null values - Speed: {null_speed}, Time: {null_time}, Segment: {null_segment}")

    # Remove critical nulls, keep flags for analysis
    df_clean = df_filled.filter(
        F.col("currentSpeed").isNotNull() &
        F.col("event_time").isNotNull() &
        F.col("segment_id").isNotNull()
    )

    return df_clean


def clean_traffic(spark, warehouse_path: str):
    """Clean traffic data: Bronze → Silver."""
    try:
        logger.info("Starting traffic cleaning...")

        # Read from Bronze
        df_bronze = spark.read.format("iceberg").load(f"{warehouse_path}/bronze_traffic_raw")

        logger.info(f"Bronze records: {df_bronze.count()}")

        # 1. Handle missing values
        df = handle_missing_values(df_bronze)
        logger.info(f"After null handling: {df.count()}")

        # 2. Standardize timestamps
        df = standardize_timestamp(df)

        # 3. Validate coordinates
        hanoi_bbox = (20.9, 21.1, 105.7, 106.0)
        hcmc_bbox = (10.5, 10.9, 106.5, 107.0)
        df = validate_coordinates(df, hanoi_bbox, hcmc_bbox)
        logger.info(f"After coord validation: {df.count()}")

        # 4. Detect outliers
        df = detect_outliers(df)
        initial_count = df.count()
        df_no_outliers = df.filter(F.col("is_outlier") == False)
        outlier_count = initial_count - df_no_outliers.count()
        logger.info(f"Outliers detected: {outlier_count} ({100*outlier_count/initial_count:.1f}%)")

        # 5. Select final columns
        df_clean = df_no_outliers.select(
            F.col("source"),
            F.col("provider"),
            F.col("city"),
            F.col("segment_id"),
            F.col("segment_name"),
            F.col("weather_cell_id"),
            F.col("lat"),
            F.col("lon"),
            F.col("event_time_std").alias("event_time"),
            F.col("time_bucket"),
            F.col("currentSpeed").cast(DoubleType()),
            F.col("freeFlowSpeed").cast(DoubleType()),
            F.col("jamFactor").cast(DoubleType()),
            F.col("confidence").cast(DoubleType()),
            F.col("roadClosure"),
            F.col("_loaded_at"),
            F.year(F.col("time_bucket")).alias("_year"),
            F.month(F.col("time_bucket")).alias("_month"),
            F.dayofmonth(F.col("time_bucket")).alias("_day"),
        )

        # 6. Write to Silver
        table_path = f"{warehouse_path}/silver_traffic_cleaned"
        df_clean.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", table_path) \
            .partitionBy("_year", "_month", "_day") \
            .save()

        clean_count = df_clean.count()
        logger.info(f"✅ Cleaned records written: {clean_count}")
        logger.info(f"Data quality: {100*clean_count/initial_count:.1f}% retained")

        return clean_count

    except Exception as e:
        logger.error(f"Error cleaning traffic: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import logging as log_module
    log_module.basicConfig(level=log_module.INFO)

    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    from processing.utils.spark_session import get_spark_session
    spark = get_spark_session("clean-traffic")
    clean_traffic(spark, warehouse_path)
    spark.stop()
