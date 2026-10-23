import os
from contextlib import contextmanager 
import psycopg2

@contextmanager
def connection():
    """Buka koneksi ke database warehouse (Postgres)"""
    conn = psycopg2.connect(
        host=os.getenv("WAREHOUSE_HOST", "warehouse-db"),
        port=os.getenv("WAREHOUSE_PORT", "5432"),
        dbname=os.environ["WAREHOUSE_DB"],
        user=os.environ["WAREHOUSE_USER"],
        password=os.environ["WAREHOUSE_PASSWORD"],
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

-- Payload mentah dari Strava disimpan apa adanya (jsonb); dipecah di kolom dbt.
CREATE TABLE IF NOT EXISTS raw.strava_activities (
    activity_id BIGINT PRIMARY KEY,
    start_date TIMESTAMP NOT NULL,
    sport_type TEXT,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Strava bisa mengganti refresh token tiap refresh, jadi token terbaru disimpan di sini.
CREATE TABLE IF NOT EXISTS raw.strava_auth (
    id      INT PRIMARY KEY DEFAULT 1,
    refresh_token   TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    CHECK (id = 1)
);
"""

def init_tables():
    with connection() as conn, conn.cursor() as cur:
        cur.execute(DDL)