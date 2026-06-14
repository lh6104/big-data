"""Airflow DAG: Silver Layer Processing (Phase 2)."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 31),
    "email": ["admin@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "silver_processing",
    default_args=default_args,
    description="Silver Layer: Cleaning + Enrichment + Matching (Phase 2)",
    schedule_interval="0 * * * *",  # Every hour
    catchup=False,
    tags=["silver", "cleaning", "hourly"],
)

SPARK_SUBMIT = "spark-submit --master spark://spark-master:7077 --deploy-mode client --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0"
WAREHOUSE = "s3a://lakehouse"
RAW_DATA_DIR = "/opt/airflow/raw"

# Phase 2a: Clean traffic and weather in parallel
with TaskGroup("clean_data", tooltip="Validate and clean raw data", dag=dag) as tg_clean:
    clean_traffic = BashOperator(
        task_id="clean_traffic",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/processing/silver/clean_traffic.py \
            {WAREHOUSE}
        """,
    )

    clean_weather = BashOperator(
        task_id="clean_weather",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/processing/silver/clean_weather.py \
            {WAREHOUSE}
        """,
    )

    [clean_traffic, clean_weather]

# Phase 2b: Match traffic ↔ weather (depends on both clean jobs)
match_traffic_weather = BashOperator(
    task_id="match_traffic_weather",
    bash_command=f"""
    {SPARK_SUBMIT} \
        /opt/spark-apps/processing/silver/match_traffic_weather.py \
        {WAREHOUSE}
    """,
    dag=dag,
)

# Phase 2c: Clean events (news/alerts)
with TaskGroup("clean_events", tooltip="Process news events", dag=dag) as tg_events:
    clean_news = BashOperator(
        task_id="clean_news_events",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/processing/silver/clean_events.py \
            {WAREHOUSE}
        """,
    )

# Set dependencies
tg_clean >> match_traffic_weather >> tg_events
