"""Airflow DAG: Weekly TomTom Traffic Stats Fetch."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 31),
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

dag = DAG(
    "tomtom_stats_async",
    default_args=default_args,
    description="Weekly TomTom Traffic Stats Baseline Fetch",
    schedule_interval="0 0 * * 0",  # Weekly on Sundays at midnight
    catchup=False,
    tags=["tomtom", "stats", "baseline"],
)


def fetch_tomtom_stats():
    """Fetch TomTom Traffic Stats via async API."""
    import os
    from datetime import datetime, timedelta
    
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        raise ValueError("TOMTOM_API_KEY not set")
    
    print(f"Fetching TomTom Stats for week of {datetime.now()}")
    print(f"Using API key: {api_key[:10]}...")
    
    # TODO: Implement actual TomTom Stats API call
    # This would submit an async job and poll for results
    print("TomTom Stats fetch simulation (requires actual implementation)")


def parse_and_load_stats():
    """Parse stats response and load into silver_tomtom_stats_lookup."""
    from pyspark.sql import SparkSession
    
    spark = SparkSession.builder \
        .appName("tomtom-stats-loader") \
        .master("spark://spark-master:7077") \
        .getOrCreate()
    
    # TODO: Parse stats JSON and load into silver_tomtom_stats_lookup
    print("Stats loading simulation (requires actual implementation)")
    spark.stop()


fetch_stats = PythonOperator(
    task_id="fetch_tomtom_stats",
    python_callable=fetch_tomtom_stats,
)

load_stats = PythonOperator(
    task_id="load_stats_to_silver",
    python_callable=parse_and_load_stats,
)

notify = BashOperator(
    task_id="notify_stats_loaded",
    bash_command="echo 'TomTom Stats loaded for week of {{ ds }}'",
)

fetch_stats >> load_stats >> notify
