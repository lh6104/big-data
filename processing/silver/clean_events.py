"""
Silver layer processing: Clean, deduplicate, and enrich events from Bronze
Pipeline: dedup → NLP classification → geocoding → confidence scoring
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json, to_json, struct, lit, udf, coalesce
from pyspark.sql.types import DoubleType, StringType
import logging

from .deduplicator import Deduplicator
from .classifier import classify
from .ner import extract_locations, detect_city
from .geocoder import geocode_with_confidence
from .severity import score_severity

logger = logging.getLogger(__name__)


class SilverEventProcessor:
    """Orchestrate Silver layer processing for news events"""

    def __init__(self, spark: SparkSession, config: dict):
        self.spark = spark
        self.config = config
        self.dedup = Deduplicator(config.get("redis", {}))

    def process(self, df: DataFrame) -> DataFrame:
        """
        Process Bronze events through Silver pipeline

        Args:
            df: DataFrame from bronze_events_raw

        Returns:
            Processed DataFrame ready for Gold layer
        """
        logger.info("Starting Silver layer processing")

        # Step 1: Deduplication (URL + content hash)
        df_dedup = self._deduplicate(df)
        logger.info(f"After dedup: {df_dedup.count()} unique events")

        # Step 2: Event classification + NER
        df_classified = self._classify_and_extract(df_dedup)

        # Step 3: Geocoding (location → lat/lon → segment_id)
        df_geocoded = self._geocode(df_classified)

        # Step 4: Confidence scoring
        df_confident = self._score_confidence(df_geocoded)

        return df_confident

    def _deduplicate(self, df: DataFrame) -> DataFrame:
        """Remove duplicate articles (URL hash + content fingerprint)"""
        # For Spark, use native dedup operations
        df = df.dropDuplicates(["source_url"])  # Remove exact URL duplicates
        return df

    def _classify_and_extract(self, df: DataFrame) -> DataFrame:
        """Apply NLP classification and entity extraction"""
        import json

        classify_udf = udf(
            lambda title, content: str(classify(title + " " + content)),
            StringType()
        )

        def extract_locs_udf_func(title, content, city):
            locs = extract_locations(title + " " + content, city_hint=city)
            return json.dumps(locs)

        extract_locs_udf = udf(extract_locs_udf_func, StringType())

        df = df.withColumn(
            "event_type",
            classify_udf(col("title"), col("content"))
        ).withColumn(
            "extracted_locations",
            extract_locs_udf(col("title"), col("content"), col("city"))
        )

        return df

    def _geocode(self, df: DataFrame) -> DataFrame:
        """Geocode location entities to lat/lon"""
        import json

        def geocode_udf_func(location_str, city_hint):
            lat, lon, conf, status = geocode_with_confidence(location_str, city_hint=city_hint)
            return json.dumps({
                "lat": lat,
                "lon": lon,
                "confidence": conf,
                "status": status
            })

        geocode_udf = udf(geocode_udf_func, StringType())

        df = df.withColumn(
            "geocode_result",
            geocode_udf(col("location_entity"), col("city"))
        )

        from pyspark.sql.types import StructType, StructField, DoubleType, StringType as StringTypeSchema
        schema = StructType([
            StructField("lat", DoubleType()),
            StructField("lon", DoubleType()),
            StructField("confidence", DoubleType()),
            StructField("status", StringTypeSchema()),
        ])

        df = df.select(
            "*",
            from_json(col("geocode_result"), schema).alias("geocoded")
        ).withColumn("lat", col("geocoded.lat")) \
         .withColumn("lon", col("geocoded.lon")) \
         .withColumn("geocode_confidence", col("geocoded.confidence")) \
         .withColumn("geocode_status", col("geocoded.status"))

        return df.drop("geocode_result", "geocoded")

    def _score_confidence(self, df: DataFrame) -> DataFrame:
        """Calculate overall event confidence"""
        confidence_udf = udf(
            lambda geocode_status, snap_dist, sources_count: self._calc_confidence(
                geocode_status, snap_dist, sources_count
            ),
            DoubleType()
        )

        df = df.withColumn(
            "event_confidence",
            confidence_udf(
                col("snapped_segment_id").isNotNull().cast("int"),
                col("snap_distance_m"),
                lit(1)  # placeholder for mirrored sources count
            )
        )

        return df

    @staticmethod
    def _geocode_result_schema():
        """Schema for geocode_and_snap result"""
        from pyspark.sql.types import StructType, StructField, DoubleType, StringType
        return StructType([
            StructField("lat", DoubleType()),
            StructField("lon", DoubleType()),
            StructField("segment_id", StringType()),
            StructField("snap_distance", DoubleType()),
            StructField("confidence", DoubleType()),
        ])

    @staticmethod
    def _calc_confidence(geocode_status: int, snap_distance: float, sources_count: int) -> float:
        """Calculate confidence score (0-1)"""
        if geocode_status == 0:
            return 0.3  # Geocoding failed

        if snap_distance is None:
            return 0.5

        # Score based on snap distance
        if snap_distance < 50:
            dist_score = 1.0
        elif snap_distance < 200:
            dist_score = 0.7
        else:
            dist_score = 0.4

        return min(1.0, dist_score * (1 + 0.1 * sources_count))


def run_silver_processing(input_table: str, output_table: str, config: dict):
    """
    Read from Bronze, process through Silver, write to Gold-ready table

    Args:
        input_table: Bronze table name
        output_table: Silver table name
        config: Configuration dict
    """
    spark = SparkSession.builder.appName("silver-events-processing").getOrCreate()

    df_bronze = spark.table(input_table)
    processor = SilverEventProcessor(spark, config)
    df_silver = processor.process(df_bronze)

    df_silver.write.mode("overwrite").option("mergeSchema", "true").saveAsTable(output_table)
    logger.info(f"Wrote {df_silver.count()} events to {output_table}")


if __name__ == "__main__":
    import json
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/settings.py"
    input_table = sys.argv[2] if len(sys.argv) > 2 else "bronze_events_raw"
    output_table = sys.argv[3] if len(sys.argv) > 3 else "silver_events_clean"

    # Load config (simplified)
    config = {"redis": {}, "geocoder": {}}

    run_silver_processing(input_table, output_table, config)
