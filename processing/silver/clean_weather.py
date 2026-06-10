"""Spark job: Clean weather data → silver_weather_cleaned."""

import logging
import sys
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def validate_weather_ranges(df):
    """Flag weather records with invalid ranges."""
    df_valid = df.withColumn(
        "is_invalid",
        (
            (F.col("temp") < -50) |  # Below -50°C
            (F.col("temp") > 60) |  # Above 60°C
            (F.col("humidity") < 0) | (F.col("humidity") > 100) |  # Invalid humidity
            (F.col("pressure") < 800) | (F.col("pressure") > 1100) |  # Invalid pressure
            (F.col("visibility") < 0) | (F.col("visibility") > 10000) |  # Invalid visibility
            (F.col("wind_speed") < 0)  # Negative wind speed
        ),
    )

    return df_valid


def standardize_timestamp(df):
    """Convert to UTC+7 and standardize format."""
    df_std = df.withColumn(
        "event_time_std",
        F.to_timestamp(
            F.date_format(F.col("event_time") + F.expr("INTERVAL 7 HOURS"), "yyyy-MM-dd HH:mm:ss"),
            "yyyy-MM-dd HH:mm:ss",
        ),
    )

    return df_std


def handle_missing_values(df):
    """Handle null values in weather data."""
    df_filled = df.withColumn(
        "has_null_values",
        F.col("temp").isNull() | F.col("humidity").isNull() | F.col("event_time").isNull(),
    )

    null_count = df_filled.filter(F.col("has_null_values")).count()
    logger.info(f"Records with null values: {null_count}")

    # Remove records with critical nulls
    df_clean = df_filled.filter(
        F.col("event_time").isNotNull() &
        F.col("city").isNotNull() &
        F.col("weather_cell_id").isNotNull()
    )

    return df_clean


def clean_weather(spark, warehouse_path: str):
    """Clean weather data: Bronze → Silver."""
    try:
        logger.info("Starting weather cleaning...")

        # Read from Bronze
        df_bronze = spark.read.format("iceberg").load(f"{warehouse_path}/bronze_weather_raw")

        logger.info(f"Bronze records: {df_bronze.count()}")

        # 1. Handle missing values
        df = handle_missing_values(df_bronze)
        logger.info(f"After null handling: {df.count()}")

        # 2. Standardize timestamps
        df = standardize_timestamp(df)

        # 3. Validate ranges
        df = validate_weather_ranges(df)
        initial_count = df.count()
        df_valid = df.filter(F.col("is_invalid") == False)
        invalid_count = initial_count - df_valid.count()
        logger.info(f"Invalid records: {invalid_count} ({100*invalid_count/initial_count:.1f}%)")

        # 4. Select final columns
        df_clean = df_valid.select(
            F.col("source"),
            F.col("provider"),
            F.col("city"),
            F.col("weather_cell_id"),
            F.col("lat"),
            F.col("lon"),
            F.col("event_time_std").alias("event_time"),
            F.col("time_bucket"),
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
            F.col("_loaded_at"),
            F.year(F.col("time_bucket")).alias("_year"),
            F.month(F.col("time_bucket")).alias("_month"),
            F.dayofmonth(F.col("time_bucket")).alias("_day"),
        )

        # 5. Write to Silver
        table_path = f"{warehouse_path}/silver_weather_cleaned"
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
        logger.error(f"Error cleaning weather: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import logging as log_module
    log_module.basicConfig(level=log_module.INFO)

    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    from processing.utils.spark_session import get_spark_session
    spark = get_spark_session("clean-weather")
    clean_weather(spark, warehouse_path)
    spark.stop()
