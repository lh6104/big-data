"""Airflow DAG: Load raw historical data → Bronze (Phase 2 initial setup)."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 31),
    "email": ["admin@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "load_raw_data",
    default_args=default_args,
    description="Load raw historical data to Bronze (Phase 2 bootstrap)",
    schedule_interval=None,  # Manual trigger or weekly
    catchup=False,
    tags=["bronze", "batch", "raw-data"],
)

SPARK_SUBMIT = "spark-submit --master spark://spark-master:7077 --deploy-mode client --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0"
WAREHOUSE = "s3a://lakehouse"
RAW_DATA_DIR = "/opt/airflow/raw"

load_raw_data = BashOperator(
    task_id="load_raw_data",
    bash_command=f"""
    {SPARK_SUBMIT} \
        /opt/spark-apps/processing/batch_load/load_raw_data.py \
        {RAW_DATA_DIR} \
        {WAREHOUSE}
    """,
)

load_raw_data
