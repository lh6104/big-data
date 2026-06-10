"""Spark job: Engineer graph features (centrality, neighbors) from road network."""

import logging
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def engineer_graph_features(df_traffic, df_centrality):
    """Add graph features: degree_centrality, betweenness_centrality, etc.

    Args:
        df_traffic: DataFrame with traffic data (segment_id, city, ...)
        df_centrality: DataFrame with precomputed centrality metrics (segment_id, degree_centrality, betweenness_centrality, ...)

    Returns:
        DataFrame with graph features added
    """
    # Join traffic with centrality metrics
    df_joined = df_traffic.join(
        df_centrality.select("segment_id", "degree_centrality", "betweenness_centrality", "closeness_centrality"),
        on="segment_id",
        how="left"
    )

    # Fill missing centrality values with global mean (0.5 for normalized metrics)
    centrality_features = ["degree_centrality", "betweenness_centrality", "closeness_centrality"]
    for feat in centrality_features:
        df_joined = df_joined.withColumn(
            feat,
            F.coalesce(F.col(feat), F.lit(0.5))
        )

    # Categorize centrality (high/medium/low)
    df_joined = df_joined.withColumn(
        "degree_centrality_category",
        F.when(F.col("degree_centrality") > 0.7, "high")
        .when(F.col("degree_centrality") > 0.3, "medium")
        .otherwise("low")
    )

    df_joined = df_joined.withColumn(
        "betweenness_centrality_category",
        F.when(F.col("betweenness_centrality") > 0.7, "high")
        .when(F.col("betweenness_centrality") > 0.3, "medium")
        .otherwise("low")
    )

    # Encode categories to numeric
    def category_to_numeric(category):
        mapping = {"high": 2, "medium": 1, "low": 0}
        return mapping.get(category, 0)

    from pyspark.sql.types import IntegerType

    category_udf = F.udf(category_to_numeric, IntegerType())

    df_joined = df_joined.withColumn(
        "degree_centrality_encoded",
        category_udf(F.col("degree_centrality_category"))
    )

    df_joined = df_joined.withColumn(
        "betweenness_centrality_encoded",
        category_udf(F.col("betweenness_centrality_category"))
    )

    # Network importance score (weighted combination)
    df_joined = df_joined.withColumn(
        "network_importance_score",
        0.4 * F.col("degree_centrality") +
        0.4 * F.col("betweenness_centrality") +
        0.2 * F.col("closeness_centrality")
    )

    # Drop string category columns (keep only encoded numeric)
    df_joined = df_joined.drop("degree_centrality_category", "betweenness_centrality_category")

    logger.info("✅ Engineered graph features")

    return df_joined
