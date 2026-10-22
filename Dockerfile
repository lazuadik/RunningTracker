FROM apache/airflow:2.10.5-python3.11

USER airflow

# Library tambahan untuk DAG (client Strava, dll.)
RUN pip install --no-cache-dir requests

# dbt dipasang di virtualenv terpisah supaya tidak bentrok dengan dependency Airflow.
# Dipanggil dari DAG lewat: /home/airflow/dbt_venv/bin/dbt
RUN python -m venv /home/airflow/dbt_venv \
    && /home/airflow/dbt_venv/bin/pip install --no-cache-dir dbt-postgres==1.9.0
