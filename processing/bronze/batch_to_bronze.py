"""Spark batch job: Load batch datasets into Bronze Iceberg tables."""

import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, year, month, dayofmonth
from processing.utils.spark_session import get_spark_session

logger = logging.getLogger(__name__)


def load_csv_to_bronze(
    spark: SparkSession,
    csv_path: str,
    output_table: str,
    warehouse_path: str,
    partition_by: list = None,
) -> None:
    """Load CSV file to Bronze table."""
    try:
        logger.info(f"Loading CSV: {csv_path} → {output_table}")

        df = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(csv_path)

        df_with_meta = df \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", lit(csv_path)) \
            .withColumn("_year", year(current_timestamp())) \
            .withColumn("_month", month(current_timestamp())) \
            .withColumn("_day", dayofmonth(current_timestamp()))

        write_op = df_with_meta.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", f"{warehouse_path}/{output_table}")

        if partition_by:
            write_op = write_op.partitionBy(*partition_by)
        else:
            write_op = write_op.partitionBy("_year", "_month", "_day")

        write_op.saveAsTable(output_table)
        logger.info(f"Loaded {df.count()} rows to {output_table}")

    except Exception as e:
        logger.error(f"Error loading CSV: {e}", exc_info=True)
        raise


def load_parquet_to_bronze(
    spark: SparkSession,
    parquet_path: str,
    output_table: str,
    warehouse_path: str,
) -> None:
    """Load Parquet file to Bronze table."""
    try:
        logger.info(f"Loading Parquet: {parquet_path} → {output_table}")

        df = spark.read.parquet(parquet_path)

        df_with_meta = df \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", lit(parquet_path)) \
            .withColumn("_year", year(current_timestamp())) \
            .withColumn("_month", month(current_timestamp())) \
            .withColumn("_day", dayofmonth(current_timestamp()))

        df_with_meta.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", f"{warehouse_path}/{output_table}") \
            .partitionBy("_year", "_month", "_day") \
            .saveAsTable(output_table)

        logger.info(f"Loaded {df.count()} rows to {output_table}")

    except Exception as e:
        logger.error(f"Error loading Parquet: {e}", exc_info=True)
        raise


def import_hcmc_traffic(spark: SparkSession, csv_path: str, warehouse_path: str) -> None:
    """Import HCMC traffic dataset from Kaggle."""
    try:
        logger.info(f"Importing HCMC traffic data from {csv_path}")

        df = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(csv_path)

        # Expected columns: timestamp, segment_id, speed, travel_time, etc.
        df_with_meta = df \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", "kaggle_hcmc_traffic") \
            .withColumn("_year", year(current_timestamp())) \
            .withColumn("_month", month(current_timestamp())) \
            .withColumn("_day", dayofmonth(current_timestamp()))

        df_with_meta.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", f"{warehouse_path}/bronze_traffic_hcmc_raw") \
            .partitionBy("_year", "_month", "_day") \
            .saveAsTable("bronze_traffic_hcmc_raw")

        logger.info(f"Imported {df.count()} HCMC traffic records")

    except Exception as e:
        logger.error(f"Error importing HCMC traffic: {e}", exc_info=True)
        raise


def import_pems_bay(spark: SparkSession, parquet_path: str, warehouse_path: str) -> None:
    """Import PEMS-BAY benchmark dataset."""
    try:
        logger.info(f"Importing PEMS-BAY from {parquet_path}")

        df = spark.read.parquet(parquet_path)

        df_with_meta = df \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", "pems_bay") \
            .withColumn("_year", year(current_timestamp())) \
            .withColumn("_month", month(current_timestamp())) \
            .withColumn("_day", dayofmonth(current_timestamp()))

        df_with_meta.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", f"{warehouse_path}/bronze_traffic_pems_bay_raw") \
            .partitionBy("_year", "_month", "_day") \
            .saveAsTable("bronze_traffic_pems_bay_raw")

        logger.info(f"Imported {df.count()} PEMS-BAY records")

    except Exception as e:
        logger.error(f"Error importing PEMS-BAY: {e}", exc_info=True)
        raise


def import_mets10(spark: SparkSession, data_path: str, warehouse_path: str) -> None:
    """Import MeTS-10 Bangkok training dataset."""
    try:
        logger.info(f"Importing MeTS-10 Bangkok from {data_path}")

        # MeTS-10 is typically in CSV or HDF5 format
        df = spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(f"{data_path}/*.csv")

        df_with_meta = df \
            .withColumn("_ingested_at", current_timestamp()) \
            .withColumn("_source", "mets10_bangkok") \
            .withColumn("_year", year(current_timestamp())) \
            .withColumn("_month", month(current_timestamp())) \
            .withColumn("_day", dayofmonth(current_timestamp()))

        df_with_meta.write \
            .format("iceberg") \
            .mode("append") \
            .option("path", f"{warehouse_path}/bronze_traffic_mets10_raw") \
            .partitionBy("_year", "_month", "_day") \
            .saveAsTable("bronze_traffic_mets10_raw")

        logger.info(f"Imported {df.count()} MeTS-10 records")

    except Exception as e:
        logger.error(f"Error importing MeTS-10: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    spark = get_spark_session("batch-to-bronze")
    warehouse_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    # Import all batch datasets
    # Adjust paths as needed based on your data location
    try:
        # import_hcmc_traffic(spark, "/data/hcmc_traffic.csv", warehouse_path)
        # import_pems_bay(spark, "/data/pems_bay.parquet", warehouse_path)
        # import_mets10(spark, "/data/mets10", warehouse_path)
        logger.info("Batch import completed")
    finally:
        spark.stop()
