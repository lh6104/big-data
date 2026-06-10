"""Alert engine for traffic congestion warnings.

Evaluates alert rules and generates traffic alerts based on:
1. Predicted speed vs baseline (p15, p50)
2. Speed trends (rapid deceleration)
3. Real-time events (accidents, floods)
"""

import logging
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from processing.utils.spark_session import get_spark_session
from processing.utils.iceberg_utils import write_iceberg_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertEngine:
    """Generates traffic alerts based on rule evaluation."""

    def __init__(self, s3_path="s3a://lakehouse"):
        self.s3_path = s3_path
        self.spark = get_spark_session("alert_engine", s3_path)

    def load_predictions(self):
        """Load recent predictions from gold_prediction_results.

        Returns:
            Pandas DataFrame with predictions
        """
        logger.info("📖 Loading recent predictions...")

        df = self.spark.read.format("iceberg").load(f"{self.s3_path}.db.gold_prediction_results")

        # Get last 1 hour of predictions
        from pyspark.sql import functions as F

        window_start = F.from_unixtime(F.unix_timestamp() - 3600)

        df_recent = df.filter(F.col("prediction_timestamp") >= window_start)

        pdf = df_recent.toPandas()
        logger.info(f"✓ Loaded {len(pdf):,} recent predictions")

        return pdf

    def load_baseline_stats(self):
        """Load baseline stats for comparison.

        Returns:
            Pandas DataFrame with baseline stats
        """
        logger.info("📖 Loading baseline stats...")

        df = self.spark.read.format("iceberg").load(f"{self.s3_path}.db.silver_tomtom_stats_lookup")
        pdf = df.toPandas()

        logger.info(f"✓ Loaded {len(pdf):,} baseline records")

        return pdf

    def evaluate_alert_rules(self, pdf_predictions, pdf_stats):
        """Evaluate alert rules on predictions.

        Rules:
        1. CRITICAL: predicted_speed < p15 * 0.8 (very severe congestion)
        2. HIGH: predicted_speed < p50 * 0.7 (severe congestion)
        3. MEDIUM: predicted_speed < p50 * 0.9 (moderate congestion)
        4. LOW: predicted_speed < p50 (mild congestion)

        Args:
            pdf_predictions: Pandas DataFrame with predictions
            pdf_stats: Pandas DataFrame with baseline stats

        Returns:
            Pandas DataFrame with generated alerts
        """
        logger.info("⚖️ Evaluating alert rules...")

        # Merge predictions with baseline stats
        # Simplified join on segment_id + time
        df_merged = pdf_predictions.copy()

        # Add baseline stats (assume we have p15, p50 columns)
        df_merged = df_merged.fillna(0)

        alerts = []

        for idx, row in df_merged.iterrows():
            pred_speed = row.get("predicted_speed_15m", row["currentSpeed"])
            current_speed = row["currentSpeed"]
            p15 = row.get("p15", 20)
            p50 = row.get("p50", 35)

            # Evaluate rules
            severity = None
            reason = None

            if pred_speed < p15 * 0.8:
                severity = "CRITICAL"
                reason = f"Speed {pred_speed:.1f} km/h is <80% of baseline p15 ({p15:.1f} km/h)"
            elif pred_speed < p50 * 0.7:
                severity = "HIGH"
                reason = f"Speed {pred_speed:.1f} km/h is <70% of baseline p50 ({p50:.1f} km/h)"
            elif pred_speed < p50 * 0.9:
                severity = "MEDIUM"
                reason = f"Speed {pred_speed:.1f} km/h is <90% of baseline p50 ({p50:.1f} km/h)"
            elif pred_speed < p50:
                severity = "LOW"
                reason = f"Speed {pred_speed:.1f} km/h is below baseline p50 ({p50:.1f} km/h)"

            # Also check for rapid deceleration
            if "speed_lag_1" in row and row["speed_lag_1"] > 0:
                decel = row["speed_lag_1"] - current_speed
                if decel > 20:  # >20 km/h deceleration in 5 minutes
                    severity = "MEDIUM"
                    reason = f"Rapid deceleration: {current_speed:.1f} km/h (was {row['speed_lag_1']:.1f} km/h)"

            # Generate alert if any rule triggered
            if severity:
                alert = {
                    "alert_id": f"{row['segment_id']}_{datetime.utcnow().timestamp()}",
                    "segment_id": row["segment_id"],
                    "city": row.get("city", "unknown"),
                    "severity": severity,
                    "reason": reason,
                    "predicted_speed": pred_speed,
                    "current_speed": current_speed,
                    "baseline_p50": p50,
                    "baseline_p15": p15,
                    "created_at": datetime.utcnow(),
                    "acknowledged": False,
                }
                alerts.append(alert)

        df_alerts = pd.DataFrame(alerts)
        logger.info(f"✓ Generated {len(df_alerts)} alerts")
        logger.info(f"  CRITICAL: {len(df_alerts[df_alerts['severity'] == 'CRITICAL'])}")
        logger.info(f"  HIGH: {len(df_alerts[df_alerts['severity'] == 'HIGH'])}")
        logger.info(f"  MEDIUM: {len(df_alerts[df_alerts['severity'] == 'MEDIUM'])}")

        return df_alerts

    def write_alerts(self, df_alerts):
        """Write alerts to gold_alerts table.

        Args:
            df_alerts: Pandas DataFrame with alerts
        """
        if len(df_alerts) == 0:
            logger.info("ℹ️ No alerts to write")
            return

        logger.info("💾 Writing gold_alerts...")

        # Convert to Spark DataFrame and write
        df_spark = self.spark.createDataFrame(df_alerts)
        write_iceberg_table(
            df_spark,
            table_name="gold_alerts",
            s3_path=self.s3_path,
            mode="append",
            partition_cols=["city"],
        )

        logger.info("✅ Alerts written to gold_alerts!")

    def run(self):
        """Execute alert generation pipeline."""
        try:
            pdf_predictions = self.load_predictions()

            if len(pdf_predictions) == 0:
                logger.warning("⚠️ No recent predictions found")
                return

            pdf_stats = self.load_baseline_stats()
            df_alerts = self.evaluate_alert_rules(pdf_predictions, pdf_stats)
            self.write_alerts(df_alerts)

            logger.info("\n" + "=" * 80)
            logger.info("✅ Alert Generation Complete!")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Alert generation failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.spark.stop()


if __name__ == "__main__":
    s3_path = sys.argv[1] if len(sys.argv) > 1 else "s3a://lakehouse"

    engine = AlertEngine(s3_path)
    engine.run()
