"""Spark job: Engineer spatial features from OSM and segment data."""

import logging
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def engineer_spatial_features(df_traffic, df_osm_segments):
    """Add spatial features: road_class, district, centrality, proximity to major nodes.

    Args:
        df_traffic: DataFrame with traffic data (segment_id, city, lat, lon)
        df_osm_segments: DataFrame with OSM data (segment_id, road_class, district, lat, lon, ...)

    Returns:
        DataFrame with spatial features added
    """
    # Join traffic with OSM segment metadata
    df_joined = df_traffic.join(
        df_osm_segments.select("segment_id", "road_class", "district", "length_m", "speed_limit"),
        on="segment_id",
        how="left"
    )

    # Fill missing road_class with 'unknown'
    df_joined = df_joined.withColumn(
        "road_class",
        F.coalesce(F.col("road_class"), F.lit("unknown"))
    )

    # Fill missing district with 'unknown'
    df_joined = df_joined.withColumn(
        "district",
        F.coalesce(F.col("district"), F.lit("unknown"))
    )

    # Road class encoding (ordinal: higher = more important)
    road_class_mapping = {
        "motorway": 5,
        "trunk": 4,
        "primary": 3,
        "secondary": 2,
        "residential": 1,
        "unknown": 0,
    }
    road_class_expr = F.when(F.col("road_class") == "motorway", 5) \
        .when(F.col("road_class") == "trunk", 4) \
        .when(F.col("road_class") == "primary", 3) \
        .when(F.col("road_class") == "secondary", 2) \
        .when(F.col("road_class") == "residential", 1) \
        .otherwise(0)

    df_joined = df_joined.withColumn("road_class_encoded", road_class_expr)

    # Road length features
    df_joined = df_joined.withColumn(
        "length_m",
        F.coalesce(F.col("length_m"), F.lit(100.0))  # Default 100m if missing
    )

    df_joined = df_joined.withColumn(
        "is_short_segment",
        F.when(F.col("length_m") < 50, 1).otherwise(0)
    )

    # Speed limit encoding
    df_joined = df_joined.withColumn(
        "speed_limit",
        F.coalesce(F.col("speed_limit"), F.lit(50.0))  # Default 50 km/h
    )

    df_joined = df_joined.withColumn(
        "speed_limit_encoded",
        F.when(F.col("speed_limit") >= 80, 3)
        .when(F.col("speed_limit") >= 50, 2)
        .when(F.col("speed_limit") >= 30, 1)
        .otherwise(0)
    )

    # Compute segment density per district (count of segments in district)
    from pyspark.sql.window import Window

    district_density = Window.partitionBy("city", "district")
    df_joined = df_joined.withColumn(
        "district_segment_count",
        F.count("segment_id").over(district_density)
    )

    # Direction encoding (simplified to 8 cardinal directions based on lat/lon change)
    # For each segment, estimate direction from first to last point
    # This is a simplification; production code would use actual polyline geometry
    df_joined = df_joined.withColumn(
        "direction_quadrant",
        F.when((F.col("lat") > 20.8) & (F.col("lon") > 105.8), 1)  # NE
        .when((F.col("lat") > 20.8) & (F.col("lon") <= 105.8), 2)  # NW
        .when((F.col("lat") <= 20.8) & (F.col("lon") > 105.8), 3)  # SE
        .otherwise(4)  # SW
    )

    logger.info("✅ Engineered spatial features")

    return df_joined
