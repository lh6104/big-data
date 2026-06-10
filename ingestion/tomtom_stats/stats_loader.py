"""TomTom Traffic Stats loader - Parse API results → Iceberg table."""

import logging
import asyncio
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class TomTomStatsLoader:
    """Load TomTom stats into Iceberg bronze table."""

    def __init__(self, spark, warehouse_path: str):
        """Initialize loader."""
        self.spark = spark
        self.warehouse_path = warehouse_path
        self.table_name = "bronze_tomtom_stats_lookup"

    def load_stats(self, stats_dict: Dict) -> int:
        """
        Load stats dictionary into Iceberg table.
        Returns row count written.
        """
        try:
            if not stats_dict:
                logger.warning("No stats to load")
                return 0

            # Convert stats dictionary to list of dicts for Spark
            rows = []
            for segment_id, stat_data in stats_dict.items():
                rows.append({
                    "segment_id": segment_id,
                    "p15_percentile": float(stat_data.get("p15", 0)),
                    "p50_percentile": float(stat_data.get("p50", 0)),
                    "p85_percentile": float(stat_data.get("p85", 0)),
                    "source": stat_data.get("source", "tomtom-stats"),
                    "fetched_at": stat_data.get("fetched_at", datetime.utcnow().isoformat()),
                    "_ingested_at": datetime.utcnow().isoformat(),
                    "_year": datetime.utcnow().year,
                    "_month": datetime.utcnow().month,
                    "_day": datetime.utcnow().day,
                })

            # Create DataFrame
            df = self.spark.createDataFrame(rows)

            # Write to Iceberg
            table_path = f"{self.warehouse_path}/{self.table_name}"
            df.write \
                .format("iceberg") \
                .mode("append") \
                .option("path", table_path) \
                .partitionBy("_year", "_month", "_day") \
                .save()

            row_count = len(rows)
            logger.info(f"Loaded {row_count} stats rows into {self.table_name}")

            return row_count

        except Exception as e:
            logger.error(f"Error loading stats: {e}", exc_info=True)
            raise

    def create_table_if_not_exists(self) -> None:
        """Create Iceberg table schema if it doesn't exist."""
        try:
            from pyspark.sql.types import StructType, StructField, StringType, DoubleType

            schema = StructType([
                StructField("segment_id", StringType(), False),
                StructField("p15_percentile", DoubleType(), True),
                StructField("p50_percentile", DoubleType(), True),
                StructField("p85_percentile", DoubleType(), True),
                StructField("source", StringType(), False),
                StructField("fetched_at", StringType(), True),
                StructField("_ingested_at", StringType(), False),
                StructField("_year", StringType(), False),
                StructField("_month", StringType(), False),
                StructField("_day", StringType(), False),
            ])

            # Create empty dataframe with schema
            df_empty = self.spark.createDataFrame([], schema)

            table_path = f"{self.warehouse_path}/{self.table_name}"
            df_empty.write \
                .format("iceberg") \
                .mode("ignore") \
                .option("path", table_path) \
                .partitionBy("_year", "_month", "_day") \
                .save()

            logger.info(f"Table {self.table_name} created")

        except Exception as e:
            logger.warning(f"Could not create table (may already exist): {e}")


async def load_tomtom_stats(api_key: str, warehouse_path: str):
    """
    Main entry point: Fetch TomTom stats and load into Iceberg.
    """
    try:
        from processing.utils.spark_session import get_spark_session
        from ingestion.tomtom_stats.stats_client import fetch_tomtom_stats

        logger.info("Starting TomTom Traffic Stats pipeline...")
        spark = get_spark_session("tomtom-stats-loader")

        # Create table if needed
        loader = TomTomStatsLoader(spark, warehouse_path)
        loader.create_table_if_not_exists()

        # Fetch stats from API
        stats = await fetch_tomtom_stats(api_key, ["hanoi", "hcmc"])

        # Load into Iceberg
        row_count = loader.load_stats(stats)

        logger.info(f"TomTom stats pipeline complete: {row_count} rows loaded")
        spark.stop()

        return row_count

    except Exception as e:
        logger.error(f"Error in TomTom stats pipeline: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(level=logging.INFO)

    api_key = os.getenv("TOMTOM_API_KEY", "")
    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    if not api_key:
        logger.warning("TOMTOM_API_KEY not set, skipping API fetch")
        # Can still test table creation without API key

    asyncio.run(load_tomtom_stats(api_key, warehouse_path))
