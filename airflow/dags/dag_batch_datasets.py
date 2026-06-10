"""Airflow DAG: Batch Dataset Imports (one-time or weekly)."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 31),
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

dag = DAG(
    "batch_dataset_imports",
    default_args=default_args,
    description="Import Batch Datasets (OSM, PEMS-BAY, MeTS-10, HCMC)",
    schedule_interval="@weekly",  # Weekly on Sundays
    catchup=False,
    tags=["batch", "import", "datasets"],
)

SPARK_SUBMIT = "spark-submit --master spark://spark-master:7077 --deploy-mode client"
WAREHOUSE = "s3a://lakehouse"

with TaskGroup("import_batch_datasets", tooltip="Import all batch data") as tg_batch:
    import_osm = BashOperator(
        task_id="import_osm",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/ingestion/batch/osm_importer.py \
            {WAREHOUSE}
        """,
        trigger_rule="all_done",  # Continue even if previous failed
    )

    import_pems = BashOperator(
        task_id="import_pems_bay",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/ingestion/batch/pems_bay_importer.py \
            {WAREHOUSE}
        """,
        trigger_rule="all_done",
    )

    import_mets10 = BashOperator(
        task_id="import_mets10",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/ingestion/batch/mets10_importer.py \
            {WAREHOUSE}
        """,
        trigger_rule="all_done",
    )

    import_hcmc = BashOperator(
        task_id="import_hcmc_traffic",
        bash_command=f"""
        {SPARK_SUBMIT} \
            /opt/spark-apps/ingestion/batch/hcmc_traffic_importer.py \
            {WAREHOUSE}
        """,
        trigger_rule="all_done",
    )

    [import_osm, import_pems, import_mets10, import_hcmc]

notify_completion = BashOperator(
    task_id="notify_completion",
    bash_command="echo 'Batch dataset imports completed'",
)

tg_batch >> notify_completion
