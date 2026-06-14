"""Airflow DAG: Hourly Data Quality Checks."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 31),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "data_quality_checks",
    default_args=default_args,
    description="Hourly Data Quality Monitoring",
    schedule_interval="30 * * * *",  # Every hour at :30
    catchup=False,
    tags=["monitoring", "quality", "hourly"],
)


def check_kafka_lag():
    """Check Kafka consumer lag."""
    import subprocess
    result = subprocess.run(
        [
            "docker", "exec", "kafka",
            "kafka-consumer-groups",
            "--bootstrap-server", "localhost:9092",
            "--describe", "--all-groups"
        ],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"Kafka lag check failed: {result.stderr}")


def check_bronze_tables():
    """Check Bronze table row counts."""
    from pyspark.sql import SparkSession
    
    spark = SparkSession.builder \
        .appName("dq-check-bronze") \
        .master("spark://spark-master:7077") \
        .getOrCreate()
    
    tables = ["bronze_events_raw", "bronze_traffic_raw", "bronze_weather_raw"]
    for table in tables:
        try:
            count = spark.table(table).count()
            print(f"{table}: {count} rows")
        except Exception as e:
            print(f"Warning: Could not count {table}: {e}")
    
    spark.stop()


kafka_lag_check = PythonOperator(
    task_id="check_kafka_lag",
    python_callable=check_kafka_lag,
    dag=dag,
)

bronze_count_check = PythonOperator(
    task_id="check_bronze_tables",
    python_callable=check_bronze_tables,
    dag=dag,
)

quality_report = BashOperator(
    task_id="generate_quality_report",
    bash_command="echo 'Data Quality Check Complete at' $(date)",
    dag=dag,
)

[kafka_lag_check, bronze_count_check] >> quality_report
