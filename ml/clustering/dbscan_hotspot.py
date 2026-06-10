"""DBSCAN clustering for congestion hotspot detection.

Identifies spatial clusters of congested traffic segments using DBSCAN algorithm
on (lat, lon, congestion_ratio) features. Runs every 15 minutes to detect current hotspots.
"""

import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from processing.utils.spark_session import get_spark_session
from processing.utils.iceberg_utils import write_iceberg_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DBSCANHotspotDetector:
    """Detects congestion hotspots using DBSCAN clustering."""

    def __init__(self, s3_path="s3a://lakehouse", city="hanoi"):
        self.s3_path = s3_path
        self.city = city
        self.spark = get_spark_session("dbscan_hotspot", s3_path)

        # Tuned parameters per city
        self.params = {
            "hanoi": {"eps": 0.01, "min_samples": 5},  # ~1km radius
            "hcmc": {"eps": 0.015, "min_samples": 4},  # ~1.5km radius
        }

    def load_current_traffic(self):
        """Load latest traffic data for the city.

        Returns:
            Pandas DataFrame with segment data
        """
        logger.info(f"📖 Loading current traffic for {self.city}...")

        df = self.spark.read.format("iceberg").load(f"{self.s3_path}.db.silver_traffic_cleaned")

        # Get latest data (last 30 minutes)
        from pyspark.sql import functions as F

        window_start = F.from_unixtime(
            F.unix_timestamp() - 1800  # 30 minutes ago
        )

        df_recent = df.filter(
            (F.col("city") == self.city) &
            (F.col("timestamp") >= window_start)
        )

        pdf = df_recent.toPandas()
        logger.info(f"✓ Loaded {len(pdf):,} recent records")

        return pdf

    def detect_hotspots(self, pdf):
        """Detect hotspots using DBSCAN.

        Args:
            pdf: Pandas DataFrame with traffic data

        Returns:
            DataFrame with cluster assignments and hotspot labels
        """
        logger.info("🔎 Detecting hotspots with DBSCAN...")

        # Features for clustering
        features = ["lat", "lon"]
        X = pdf[features].values

        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Get DBSCAN parameters for this city
        params = self.params.get(self.city, {"eps": 0.01, "min_samples": 5})

        # Apply DBSCAN
        clustering = DBSCAN(eps=params["eps"], min_samples=params["min_samples"]).fit(X_scaled)

        pdf["cluster"] = clustering.labels_
        pdf["is_core_point"] = clustering.core_sample_indices_

        # Filter out noise points (cluster = -1)
        pdf_clusters = pdf[pdf["cluster"] != -1].copy()

        logger.info(f"✓ Detected {pdf['cluster'].max() + 1} hotspot clusters")

        # Compute cluster statistics
        cluster_stats = pdf_clusters.groupby("cluster").agg({
            "lat": "mean",
            "lon": "mean",
            "segment_id": "count",
            "currentSpeed": ["mean", "min", "max"],
            "congestion_ratio": "mean",
            "jamFactor": "mean",
        }).reset_index()

        cluster_stats.columns = ["cluster", "center_lat", "center_lon", "num_segments",
                                "avg_speed", "min_speed", "max_speed", "avg_congestion",
                                "avg_jam_factor"]

        # Hotspot severity (based on congestion ratio)
        cluster_stats["severity"] = pd.cut(
            cluster_stats["avg_congestion"],
            bins=[0, 0.3, 0.6, 1.0],
            labels=["low", "medium", "high"],
            include_lowest=True
        )

        # Hotspot radius (distance from center to furthest point)
        for idx, row in cluster_stats.iterrows():
            cluster_id = row["cluster"]
            cluster_points = pdf_clusters[pdf_clusters["cluster"] == cluster_id]
            if len(cluster_points) > 0:
                distances = np.sqrt(
                    (cluster_points["lat"] - row["center_lat"]) ** 2 +
                    (cluster_points["lon"] - row["center_lon"]) ** 2
                ) * 111  # Approximate: 1 degree ~ 111 km
                cluster_stats.loc[idx, "radius_km"] = distances.max()

        logger.info(f"📊 Hotspot statistics:")
        logger.info(f"  Total clusters: {len(cluster_stats)}")
        logger.info(f"  High severity: {len(cluster_stats[cluster_stats['severity'] == 'high'])}")
        logger.info(f"  Medium severity: {len(cluster_stats[cluster_stats['severity'] == 'medium'])}")

        return pdf, cluster_stats

    def write_hotspots(self, cluster_stats):
        """Write hotspots to gold_congestion_hotspots table.

        Args:
            cluster_stats: Pandas DataFrame with cluster statistics
        """
        logger.info("💾 Writing gold_congestion_hotspots...")

        # Add metadata columns
        cluster_stats["city"] = self.city
        cluster_stats["detected_at"] = datetime.utcnow()
        cluster_stats["hotspot_id"] = (
            self.city + "_" + cluster_stats["cluster"].astype(str) + "_" +
            datetime.utcnow().strftime("%Y%m%d%H%M%S")
        )

        # Convert to Spark DataFrame and write
        df_hotspots = self.spark.createDataFrame(cluster_stats)
        write_iceberg_table(
            df_hotspots,
            table_name="gold_congestion_hotspots",
            s3_path=self.s3_path,
            mode="append",
            partition_cols=["city"],
        )

        logger.info("✅ gold_congestion_hotspots written!")

    def run(self):
        """Execute hotspot detection pipeline."""
        try:
            pdf = self.load_current_traffic()

            if len(pdf) == 0:
                logger.warning("⚠️ No recent traffic data found")
                return

            pdf, cluster_stats = self.detect_hotspots(pdf)
            self.write_hotspots(cluster_stats)

            logger.info("\n" + "=" * 80)
            logger.info(f"✅ DBSCAN Hotspot Detection Complete for {self.city}!")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Hotspot detection failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.spark.stop()


if __name__ == "__main__":
    city = sys.argv[1] if len(sys.argv) > 1 else "hanoi"
    s3_path = sys.argv[2] if len(sys.argv) > 2 else "s3a://lakehouse"

    detector = DBSCANHotspotDetector(s3_path, city)
    detector.run()
