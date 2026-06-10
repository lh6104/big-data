"""Load raw historical data from raw/ folder → Bronze Iceberg tables."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, BooleanType, TimestampType

logger = logging.getLogger(__name__)


def get_raw_data_paths(raw_dir: str):
    """Discover all raw JSONL files (handles multiple naming patterns)."""
    raw_path = Path(raw_dir)

    traffic_files = list(raw_path.glob("traffic/*.jsonl"))
    weather_files = list(raw_path.glob("weather/*.jsonl"))

    logger.info(f"Found {len(traffic_files)} traffic files")
    logger.info(f"Found {len(weather_files)} weather files")

    return traffic_files, weather_files


def load_traffic_raw(spark, raw_dir: str, warehouse_path: str):
    """Load all traffic JSONL files → bronze_traffic_raw."""
    try:
        logger.info("Loading raw traffic data...")

        traffic_files, _ = get_raw_data_paths(raw_dir)

        if not traffic_files:
            logger.warning("No traffic files found")
            return 0

        # Read all traffic files (handles both tomtom_* and traffic_raw_* patterns)
        traffic_paths = [str(f) for f in traffic_files]
        df_traffic = spark.read.json(traffic_paths)

        # Standardize schema
        df_traffic = df_traffic.select(
            F.col("source").cast(StringType()),
            F.col("provider").cast(StringType()),
            F.col("city").cast(StringType()),
            F.col("segment_id").cast(StringType()),
            F.col("segment_name").cast(StringType()),
            F.col("weather_cell_id").cast(StringType()),
            F.col("lat").cast(DoubleType()),
            F.col("lon").cast(DoubleType()),
            F.col("event_time").cast(TimestampType()),
            F.col("ingestion_time").cast(TimestampType()),
            F.col("time_bucket").cast(TimestampType()),
            F.col("currentSpeed").cast(DoubleType()),
            F.col("freeFlowSpeed").cast(DoubleType()),
            F.col("jamFactor").cast(DoubleType()),
            F.col("confidence").cast(DoubleType()),
            F.col("roadClosure").cast(BooleanType()),
            F.current_timestamp().alias("_loaded_at"),
            F.year(F.col("time_bucket")).alias("_year"),
            F.month(F.col("time_bucket")).alias("_month"),
            F.dayofmonth(F.col("time_bucket")).alias("_day"),
        )

        # Deduplicate
        df_traffic = df_traffic.dropDuplicates(["segment_id", "time_bucket", "source"])

        # Write to Iceberg
        table_path = f"{warehouse_path}/bronze_traffic_raw"
        df_traffic.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", table_path) \
            .partitionBy("_year", "_month", "_day") \
            .save()

        row_count = df_traffic.count()
        logger.info(f"Loaded {row_count} traffic records")

        return row_count

    except Exception as e:
        logger.error(f"Error loading traffic data: {e}", exc_info=True)
        raise


def load_weather_raw(spark, raw_dir: str, warehouse_path: str):
    """Load all weather JSONL files → bronze_weather_raw."""
    try:
        logger.info("Loading raw weather data...")

        _, weather_files = get_raw_data_paths(raw_dir)

        if not weather_files:
            logger.warning("No weather files found")
            return 0

        # Read all weather files
        weather_paths = [str(f) for f in weather_files]
        df_weather = spark.read.json(weather_paths)

        # Standardize schema
        df_weather = df_weather.select(
            F.col("source").cast(StringType()),
            F.col("provider").cast(StringType()),
            F.col("city").cast(StringType()),
            F.col("weather_cell_id").cast(StringType()),
            F.col("lat").cast(DoubleType()),
            F.col("lon").cast(DoubleType()),
            F.col("event_time").cast(TimestampType()),
            F.col("ingestion_time").cast(TimestampType()),
            F.col("time_bucket").cast(TimestampType()),
            F.col("temp").cast(DoubleType()),
            F.col("feels_like").cast(DoubleType()),
            F.col("humidity").cast(IntegerType()),
            F.col("pressure").cast(IntegerType()),
            F.col("visibility").cast(IntegerType()),
            F.col("rain_1h").cast(DoubleType()),
            F.col("wind_speed").cast(DoubleType()),
            F.col("wind_deg").cast(IntegerType()),
            F.col("weather_main").cast(StringType()),
            F.col("weather_desc").cast(StringType()),
            F.current_timestamp().alias("_loaded_at"),
            F.year(F.col("time_bucket")).alias("_year"),
            F.month(F.col("time_bucket")).alias("_month"),
            F.dayofmonth(F.col("time_bucket")).alias("_day"),
        )

        # Deduplicate
        df_weather = df_weather.dropDuplicates(["city", "time_bucket", "source"])

        # Write to Iceberg
        table_path = f"{warehouse_path}/bronze_weather_raw"
        df_weather.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", table_path) \
            .partitionBy("_year", "_month", "_day") \
            .save()

        row_count = df_weather.count()
        logger.info(f"Loaded {row_count} weather records")

        return row_count

    except Exception as e:
        logger.error(f"Error loading weather data: {e}", exc_info=True)
        raise


def main(raw_dir: str, warehouse_path: str):
    """Load all raw data to Bronze."""
    try:
        from processing.utils.spark_session import get_spark_session

        logger.info("Starting raw data load to Bronze...")
        spark = get_spark_session("load-raw-data")

        traffic_count = load_traffic_raw(spark, raw_dir, warehouse_path)
        weather_count = load_weather_raw(spark, raw_dir, warehouse_path)

        logger.info(f"✅ Raw data load complete: {traffic_count} traffic + {weather_count} weather records")
        spark.stop()

        return traffic_count + weather_count

    except Exception as e:
        logger.error(f"Error in raw data load: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "raw"
    warehouse_path = sys.argv[2] if len(sys.argv) > 2 else "s3a://lakehouse"

    main(raw_dir, warehouse_path)
