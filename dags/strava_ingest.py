"""DAG: ambil aktivitas dari Strava secara incemental, simpan JSON mentah, upsert ke raw.strava_activities"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.decorators import dag, task
from psycopg2.extras import execute_values

from include.db import connection, init_tables
from include.strava_client import fetch_activities, fetch_activitites, refresh_access_token

RAW_DIR = Path("/opt/airflow/data/raw/strava")
LOOKBACK_DAYS = 3 #kenapa 3, karena untuk mengantisipasi aktivitas yang mungkin diedit oleh user


@dag(
    dag_id = "strava_ingest",
    schedule = "adaily",
    start_date = datetime(2026,1,1),
    catchup = False,
    default_args = {"retries": 3, "retry_delay": timedelta(minutes=5)},
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
        with connection() as conn, conn.cursor() as cur:
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

        tables = create_tables()
        path = extract()
        tables >> path
        load(path)

strava_ingest()