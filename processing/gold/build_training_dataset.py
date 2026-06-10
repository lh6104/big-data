"""Spark job: Build training dataset with all 8 feature groups → gold_training_dataset.

This is the main orchestration job that runs feature engineering end-to-end:
1. Temporal features
2. Traffic features (congestion, rolling averages)
3. Weather features (asof join)
4. Spatial features (road class, district)
5. Stats baseline features (p15, p50, p85)
6. Lag features (5, 10, 15 min history)
7. Event features (accidents, floods, roadwork)
8. Graph features (centrality)

Then creates targets: future_speed_{15m, 60m, 240m}
"""

import logging
import sys
from datetime import timedelta
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

# Import feature engineering modules
from feature_temporal import engineer_temporal_features
from feature_traffic import engineer_traffic_features
from feature_weather import engineer_weather_features
from feature_spatial import engineer_spatial_features
from feature_stats_baseline import engineer_stats_baseline_features
from feature_lag import engineer_lag_features
from feature_event import engineer_event_features
from feature_graph import engineer_graph_features

# Import utility functions
import sys
sys.path.insert(0, "/home/longha/Desktop/leue")
from processing.utils.spark_session import get_spark_session
from processing.utils.iceberg_utils import get_iceberg_session, write_iceberg_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_target_labels(df):
    """Create target variables: future_speed for 15, 60, 240 minutes ahead.

    Args:
        df: DataFrame with segment_id, timestamp, currentSpeed

    Returns:
        DataFrame with future_speed targets added
    """
    window_spec = Window.partitionBy("segment_id").orderBy("timestamp")

    # Lead: future speed (ahead in time)
    # Assuming 5-minute intervals, lag=3 means 15 minutes, lag=12 means 60 minutes, lag=48 means 240 minutes
    df = df.withColumn(
        "future_speed_15m",
        F.lead(F.col("currentSpeed"), 3).over(window_spec)
    )

    df = df.withColumn(
        "future_speed_60m",
        F.lead(F.col("currentSpeed"), 12).over(window_spec)
    )

    df = df.withColumn(
        "future_speed_240m",
        F.lead(F.col("currentSpeed"), 48).over(window_spec)
    )

    # Filter out rows without targets (last observations)
    df = df.filter(
        F.col("future_speed_15m").isNotNull() |
        F.col("future_speed_60m").isNotNull() |
        F.col("future_speed_240m").isNotNull()
    )

    logger.info("✅ Created target labels for 15/60/240 minute horizons")

    return df


def main(s3_path="s3a://lakehouse"):
    """Main pipeline orchestration.

    Args:
        s3_path: S3/MinIO path to lakehouse (default: s3a://lakehouse)
    """
    logger.info("=" * 80)
    logger.info("🚀 PHASE 3: Building training dataset with feature engineering")
    logger.info("=" * 80)

    # Initialize Spark
    spark = get_spark_session("build_training_dataset", s3_path)

    try:
        # Read Silver tables (output from Phase 2)
        logger.info("\n📖 Reading Silver tables...")
        df_traffic = spark.read.format("iceberg").load(f"{s3_path}.db.silver_traffic_cleaned")
        df_weather = spark.read.format("iceberg").load(f"{s3_path}.db.silver_weather_cleaned")
        df_events = spark.read.format("iceberg").load(f"{s3_path}.db.silver_events_cleaned")
        df_osm = spark.read.format("iceberg").load(f"{s3_path}.db.silver_traffic_osm_mapped")
        df_stats = spark.read.format("iceberg").load(f"{s3_path}.db.silver_tomtom_stats_lookup")

        logger.info(f"  ✓ silver_traffic_cleaned: {df_traffic.count():,} records")
        logger.info(f"  ✓ silver_weather_cleaned: {df_weather.count():,} records")
        logger.info(f"  ✓ silver_events_cleaned: {df_events.count():,} records")

        # Feature engineering: 8 groups
        logger.info("\n🔧 Engineering features (8 groups)...")

        # 1. Temporal
        logger.info("  1️⃣ Temporal features...")
        df_features = engineer_temporal_features(df_traffic)

        # 2. Traffic
        logger.info("  2️⃣ Traffic features...")
        df_features = engineer_traffic_features(df_features)

        # 3. Weather (asof join)
        logger.info("  3️⃣ Weather features (asof join)...")
        df_features = engineer_weather_features(df_features, df_weather)

        # 4. Spatial (road class, district)
        logger.info("  4️⃣ Spatial features...")
        df_features = engineer_spatial_features(df_features, df_osm)

        # 5. Stats baseline (p15, p50, p85)
        logger.info("  5️⃣ Stats baseline features...")
        df_features = engineer_stats_baseline_features(df_features, df_stats)

        # 6. Lag (historical)
        logger.info("  6️⃣ Lag features...")
        df_features = engineer_lag_features(df_features)

        # 7. Event (accidents, floods, roadwork)
        logger.info("  7️⃣ Event features...")
        df_features = engineer_event_features(df_features, df_events)

        # 8. Graph (centrality) — placeholder if centrality table not available
        logger.info("  8️⃣ Graph features...")
        try:
            df_centrality = spark.read.format("iceberg").load(f"{s3_path}.db.silver_segment_centrality")
            df_features = engineer_graph_features(df_features, df_centrality)
        except Exception as e:
            logger.warning(f"  ⚠️  Graph features skipped (centrality table not found): {e}")
            # Add dummy centrality columns
            df_features = df_features \
                .withColumn("degree_centrality", F.lit(0.5)) \
                .withColumn("betweenness_centrality", F.lit(0.5)) \
                .withColumn("closeness_centrality", F.lit(0.5)) \
                .withColumn("degree_centrality_encoded", F.lit(1)) \
                .withColumn("betweenness_centrality_encoded", F.lit(1)) \
                .withColumn("network_importance_score", F.lit(0.5))

        # Create targets (future speeds)
        logger.info("\n🎯 Creating target labels...")
        df_features = create_target_labels(df_features)

        # Feature summary
        logger.info(f"\n📊 Features created: {len(df_features.columns)} total")
        logger.info(f"  Total records: {df_features.count():,}")
        logger.info(f"  Memory usage: ~{df_features.count() * 0.001} MB (estimated)")

        # Write to gold_training_dataset
        logger.info("\n💾 Writing gold_training_dataset...")
        write_iceberg_table(
            df_features,
            table_name="gold_training_dataset",
            s3_path=s3_path,
            mode="overwrite",
            partition_cols=["city", "date"]
        )

        logger.info("✅ gold_training_dataset written successfully!")

        # Also write gold_traffic_features (same as training dataset but with explicit schema)
        logger.info("\n💾 Writing gold_traffic_features...")
        write_iceberg_table(
            df_features.select([
                "segment_id", "city", "timestamp", "currentSpeed", "freeFlowSpeed",
                "jamFactor", "lat", "lon", "date",
                # Temporal
                "hour_of_day", "day_of_week", "day_of_month", "month_of_year",
                "is_weekend", "is_peak_hour", "is_holiday_vn",
                # Traffic
                "congestion_ratio", "speed_rolling_avg_5m", "speed_rolling_avg_15m",
                "speed_rolling_avg_30m", "congestion_rolling_avg_5m",
                # Weather
                "weather_temperature", "weather_humidity", "weather_rain_1h",
                "weather_visibility", "weather_wind_speed", "weather_severity",
                # Spatial
                "road_class", "district", "road_class_encoded", "district_segment_count",
                # Stats
                "p15", "p50", "p85", "baseline_congestion_ratio",
                "speed_vs_p15", "speed_vs_p50", "speed_vs_p85",
                # Lag
                "speed_lag_1", "speed_lag_2", "speed_lag_3",
                "congestion_lag_1", "congestion_lag_2",
                # Event
                "has_accident", "has_flood", "has_roadwork", "has_event",
                # Graph
                "degree_centrality", "betweenness_centrality", "network_importance_score"
            ]),
            table_name="gold_traffic_features",
            s3_path=s3_path,
            mode="overwrite",
            partition_cols=["city", "date"]
        )

        logger.info("✅ gold_traffic_features written successfully!")

        logger.info("\n" + "=" * 80)
        logger.info("✅ Phase 3 - Feature Engineering Complete!")
        logger.info("=" * 80)
        logger.info("\n📊 Gold tables ready:")
        logger.info("  ✓ gold_traffic_features: Full feature vectors")
        logger.info("  ✓ gold_training_dataset: Features + targets (future_speed_15/60/240m)")
        logger.info("\n🚀 Next: Run LightGBM training (ml/training/train_lightgbm.py)")

    except Exception as e:
        logger.error(f"❌ Error in feature engineering: {e}", exc_info=True)
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    s3_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"
    main(s3_path)
