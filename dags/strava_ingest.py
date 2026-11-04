"""DAG: ambil aktivitas dari Strava secara incremental, simpan JSON mentah, upsert ke raw.strava_activities"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from psycopg2.extras import execute_values

from include.db import connection, init_tables
from include.run_summary import notify_if_new_run
from include.strava_client import fetch_activities, refresh_access_token
from include.telegram import notify_failure, send_telegram_message

RAW_DIR = Path("/opt/airflow/data/raw/strava")
LOOKBACK_DAYS = 3 #kenapa 3, karena untuk mengantisipasi aktivitas yang mungkin diedit oleh user

DBT_CMD = (
    "/home/airflow/dbt_venv/bin/dbt {cmd}"
    " --select stg_strava_activities+ source:raw_strava_activities"
    " --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project"
)

@dag(
    dag_id = "strava_ingest",
    schedule = "@daily",
    start_date = datetime(2026,1,1),
    catchup = False,
    default_args = {"retries": 3, "retry_delay": timedelta(minutes=5), "on_failure_callback": notify_failure},
    tags = ["strava", "ingest"],
)

def strava_ingest():
    @task
    def create_tables():
        init_tables()

    #Test ini adalah komentar, tidak akan dijalankan
    #Init_tables()
    @task
    def extract() -> str:

        #Incremental: mulai dari aktivitas terakhir di database (dikurangi lookback).
        #Kalau table kosong, ambil semua aktivitas (after=0)

        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT MAX(start_date) FROM raw.strava_activities")
            last = cur.fetchone()[0]
        after = int((last - timedelta(days=LOOKBACK_DAYS)).timestamp()) if last else 0

        activities = fetch_activities(refresh_access_token(), after=after)

        now = datetime.now(timezone.utc)
        outdir = RAW_DIR / now.strftime("%Y/%m/%d")
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / f"activities_{now.strftime('%H%M%S')}.json"
        path.write_text(json.dumps(activities, indent=2))
        return str(path)

    @task
    def load(path: str):
        activities = json.loads(Path(path).read_text())
        if not activities:
            return 0
        rows = [
            (a["id"], a["start_date"], a.get("sport_type") or a.get("type"), json.dumps(a))
            for a in activities
        ]
        with connection() as conn, conn.cursor() as cur:

            execute_values(
                cur,
                """
                INSERT INTO raw.strava_activities (activity_id, start_date, sport_type, payload)
                VALUES %s
                ON CONFLICT (activity_id) DO UPDATE
                SET start_date = EXCLUDED.start_date,
                    sport_type = EXCLUDED.sport_type,
                    payload = EXCLUDED.payload,
                    ingested_at = now()
            """,
            rows,
            )
        return len(rows)

    @task
    def notify_run():
        return notify_if_new_run(send_telegram_message)


    tables = create_tables()
    path = extract()
    loaded = load(path)
    notify = notify_run()

    dbt_run = BashOperator(task_id="dbt_run", bash_command=DBT_CMD.format(cmd="run"))
    dbt_test = BashOperator(task_id="dbt_test", bash_command=DBT_CMD.format(cmd="test"))
    tables >> path >> loaded >> dbt_run >> dbt_test >> notify

strava_ingest()
