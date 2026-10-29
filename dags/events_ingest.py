"""DAG baca csv event race -> validasi -> upsert ke raw.events, lalu bangun model dbt event"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from include.events import init_events_table, load_events as load_events_csv

EVENTS_CSV = Path("/opt/airflow/data/events/events_seed.csv")
REJECTED_DIR = Path("/opt/airflow/data/events/rejected")

#hanya model event saja yang dirun di DAG ini

DBT_CMD = (
    "/home/airflow/dbt_venv/bin/dbt {cmd}"
    " --select stg_events dim_events race_readiness source:raw_events "
    " --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project"
)

@dag(
    dag_id="events_ingest",
    schedule="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["events", "ingestion"],
)

def event_ingest():
    @task
    def create_event_tables():
        init_events_table()

    @task 
    def load_events() -> dict:
        result = load_events_csv(EVENTS_CSV, REJECTED_DIR)
        if result['rejected']:
             print(f"PERINGATAN: {result['rejected']} baris ditolak, lihat {result['rejected_file']}")
        print(f"Event dimuat: {result['loaded']} (valid={result['valid']}, ditolak={result['rejected']})")
        return result

    dbt_run = BashOperator(task_id="dbt_run", bash_command=DBT_CMD.format(cmd="run"))
    dbt_test = BashOperator(task_id="dbt_test", bash_command=DBT_CMD.format(cmd="test"))

    tables = create_event_tables()
    loaded = load_events()
    tables >> loaded
    loaded >> dbt_run >> dbt_test 

event_ingest()