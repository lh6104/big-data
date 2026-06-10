"""Spark session factory with Iceberg configuration."""

from pyspark.sql import SparkSession
import logging

logger = logging.getLogger(__name__)


def get_spark_session(app_name: str = "traffic-analytics", enable_iceberg: bool = True) -> SparkSession:
    """Create and return a SparkSession with Iceberg configuration.

    Args:
        app_name: Application name for Spark
        enable_iceberg: Whether to enable Iceberg/Hive Metastore

    Returns:
        Configured SparkSession
    """
    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("spark://spark-master:7077")
    )

    if enable_iceberg:
        builder = (
            builder
            # Iceberg catalog configuration
            .config("spark.sql.defaultCatalog", "iceberg")
            .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.iceberg.type", "hive")
            .config("spark.sql.catalog.iceberg.warehouse", "s3a://lakehouse")
            .config("spark.sql.catalog.iceberg.uri", "thrift://hive-metastore:9083")
            # S3 / MinIO configuration
            .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
            .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
            .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            # Spark SQL extensions for Iceberg
            .config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
            )
        )

    # Add Kafka packages
    builder = builder.config(
        "spark.jars.packages",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0,"
        "org.apache.hadoop:hadoop-aws:3.3.4"
    )

    spark = builder.getOrCreate()

    # Set log level
    spark.sparkContext.setLogLevel("INFO")

    logger.info(f"SparkSession created: {app_name}")
    return spark


def stop_spark_session(spark: SparkSession) -> None:
    """Stop Spark session gracefully."""
    if spark:
        spark.stop()
        logger.info("SparkSession stopped")
