"""
Spark Structured Streaming job: Kafka → Bronze Iceberg tables
Consumes from Kafka topics and writes raw data to Bronze Iceberg tables
Supports: events.news, traffic.realtime.tomtom, weather.current
"""

import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp, year, month, dayofmonth
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType, BooleanType

from processing.utils.spark_session import get_spark_session

logger = logging.getLogger(__name__)


def get_schema_for_topic(topic: str) -> StructType:
    """Get schema for a specific Kafka topic."""
    if topic == "events.news":
        return StructType([
            StructField("event_id", StringType(), False),
            StructField("source", StringType(), False),
            StructField("source_url", StringType(), True),
            StructField("crawled_at", TimestampType(), False),
            StructField("published_at", TimestampType(), True),
            StructField("title", StringType(), False),
            StructField("content", StringType(), True),
            StructField("event_type", StringType(), True),
            StructField("severity", IntegerType(), True),
            StructField("location_entity", StringType(), True),
            StructField("lat", DoubleType(), True),
            StructField("lon", DoubleType(), True),
            StructField("snapped_segment_id", StringType(), True),
            StructField("snap_distance_m", DoubleType(), True),
            StructField("event_confidence", DoubleType(), True),
            StructField("city", StringType(), True),
            StructField("mirrored_sources", StringType(), True),
            StructField("raw_html_path", StringType(), True),
        ])
    elif topic == "traffic.realtime.tomtom":
        return StructType([
            StructField("segment_id", StringType(), False),
            StructField("current_speed", DoubleType(), True),
            StructField("free_flow_speed", DoubleType(), True),
            StructField("jam_factor", DoubleType(), True),
            StructField("congestion_ratio", DoubleType(), True),
            StructField("confidence", DoubleType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("functional_road_class", StringType(), True),
            StructField("road_closure", BooleanType(), True),
            StructField("source", StringType(), False),
            StructField("timestamp", StringType(), False),
        ])
    elif topic == "weather.current":
        return StructType([
            StructField("city", StringType(), False),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("temperature", DoubleType(), True),
            StructField("feels_like", DoubleType(), True),
            StructField("humidity", IntegerType(), True),
            StructField("pressure", IntegerType(), True),
            StructField("visibility", IntegerType(), True),
            StructField("wind_speed", DoubleType(), True),
            StructField("wind_degree", IntegerType(), True),
            StructField("rain_1h", DoubleType(), True),
            StructField("rain_3h", DoubleType(), True),
            StructField("cloudiness", IntegerType(), True),
            StructField("description", StringType(), True),
            StructField("weather_main", StringType(), True),
            StructField("source", StringType(), False),
            StructField("timestamp", StringType(), False),
        ])
    else:
        raise ValueError(f"Unknown topic: {topic}")


def get_output_table_for_topic(topic: str) -> str:
    """Get output table name for a topic."""
    mapping = {
        "events.news": "bronze_events_raw",
        "traffic.realtime.tomtom": "bronze_traffic_raw",
        "weather.current": "bronze_weather_raw",
    }
    return mapping.get(topic, f"bronze_{topic.replace('.', '_')}_raw")


def run_kafka_to_bronze(kafka_brokers: str, kafka_topic: str, warehouse_path: str):
    """Consume Kafka topic and write to Bronze Iceberg table."""
    spark = get_spark_session()
    output_table = get_output_table_for_topic(kafka_topic)
    schema = get_schema_for_topic(kafka_topic)

    try:
        logger.info(f"Starting Kafka→Bronze streaming: {kafka_topic} → {output_table}")

        # Read from Kafka
        df_kafka = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_brokers) \
            .option("subscribe", kafka_topic) \
            .option("startingOffsets", "latest") \
            .option("maxOffsetsPerTrigger", 10000) \
            .load()

        # Parse JSON and apply schema
        df_parsed = df_kafka.select(
            from_json(col("value").cast("string"), schema).alias("data")
        ).select("data.*") \
         .withColumn("_ingested_at", current_timestamp()) \
         .withColumn("_source", col("source")) \
         .withColumn("_year", year(current_timestamp())) \
         .withColumn("_month", month(current_timestamp())) \
         .withColumn("_day", dayofmonth(current_timestamp()))

        # Write to Iceberg table
        query = df_parsed.writeStream \
            .format("iceberg") \
            .outputMode("append") \
            .option("path", f"{warehouse_path}/{output_table}") \
            .option("checkpointLocation", f"{warehouse_path}/checkpoints/{kafka_topic}") \
            .partitionBy("_year", "_month", "_day") \
            .start()

        logger.info(f"Streaming started for {kafka_topic}")
        query.awaitTermination()

    except Exception as e:
        logger.error(f"Error in kafka_to_bronze: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import sys

    kafka_brokers = sys.argv[1] if len(sys.argv) > 1 else "localhost:9092"
    kafka_topic = sys.argv[2] if len(sys.argv) > 2 else "events.news"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "/warehouse"

    run_kafka_to_bronze(kafka_brokers, kafka_topic, output_path)
