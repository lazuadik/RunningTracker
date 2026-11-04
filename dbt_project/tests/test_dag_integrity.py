"""Pemeriksaan struktur DAG tanpa menjalankan task apa pun.

Butuh Airflow terpasang. Di mesin tanpa Airflow, file ini dilewati otomatis.
Jalankan di dalam container:
    docker compose exec airflow-scheduler python -m pytest tests/test_dag_integrity.py
"""
from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag  # noqa: E402

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(DAGS_DIR), include_examples=False)


def test_semua_dag_bisa_dimuat(dagbag):
    # Menangkap SyntaxError, salah ketik impor, dan jadwal tidak valid (penyebab "Broken DAG").
    assert dagbag.import_errors == {}


def test_dag_yang_diharapkan_ada(dagbag):
    assert {"strava_ingest", "events_ingest"} <= set(dagbag.dag_ids)


def test_strava_ingest_punya_task_dan_urutan_yang_benar(dagbag):
    dag = dagbag.dags["strava_ingest"]
    assert {t.task_id for t in dag.tasks} == {
        "create_tables", "extract", "load", "dbt_run", "dbt_test", "notify_run",
    }
    # dbt harus menunggu data selesai dimuat, dan ringkasan menunggu test lulus.
    assert dag.get_task("dbt_run").upstream_task_ids == {"load"}
    assert dag.get_task("dbt_test").upstream_task_ids == {"dbt_run"}
    assert dag.get_task("notify_run").upstream_task_ids == {"dbt_test"}


def test_events_ingest_urutan_task(dagbag):
    dag = dagbag.dags["events_ingest"]
    assert dag.get_task("dbt_run").upstream_task_ids == {"load_events"}
    assert dag.get_task("dbt_test").upstream_task_ids == {"dbt_run"}