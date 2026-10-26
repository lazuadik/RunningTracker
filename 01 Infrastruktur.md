# Tahap 1: Infrastruktur

## Tujuan

Menyediakan seluruh komponen pipeline di laptop dengan satu perintah (`docker compose up -d`), sehingga lingkungan yang sama bisa dipindahkan ke server nanti.

## Layanan

| Service | Image | Port (host) | Fungsi |
|---|---|---|---|
| `airflow-db` | `postgres:16` | – | Database metadata Airflow |
| `warehouse-db` | `postgres:16` | `5433` | Warehouse: schema `raw`, `staging`, `marts` |
| `airflow-init` | image Airflow | – | Sekali jalan: migrasi database Airflow dan membuat user admin |
| `airflow-webserver` | image Airflow | `8080` | UI Airflow |
| `airflow-scheduler` | image Airflow | – | Menjadwalkan dan menjalankan task |
| `metabase` | `metabase/metabase` | `3000` | Dashboard |

`airflow-init` berstatus `Exited (0)` setelah selesai. Itu normal, bukan error.

## Dua database Postgres

Metadata Airflow (riwayat run, status task) dipisahkan dari warehouse. Alasannya: data orkestrasi dan data analitik punya siklus hidup dan hak akses yang berbeda, dan warehouse bisa dipindahkan atau di-backup tanpa membawa metadata Airflow.

Warehouse bisa diakses dari dua tempat dengan alamat berbeda:

| Dari mana | Host | Port |
|---|---|---|
| Container lain (Airflow, Metabase, dbt) | `warehouse-db` | `5432` |
| Laptop (DBeaver, VS Code) | `localhost` | `5433` |

## Konfigurasi penting

- **`.env`** berisi kredensial Strava, kredensial warehouse, dan akun admin Airflow. Template-nya ada di `.env.example`.
- **Volume yang di-mount**: `dags/`, `include/`, `data/`, `dbt_project/`, dan `logs/`. Perubahan kode langsung terbaca container tanpa build ulang.
- **`init-warehouse.sql`** membuat schema `raw`, `staging`, dan `marts`. File ini hanya dijalankan **saat volume warehouse pertama kali dibuat**. Mengubah user atau password di `.env` setelahnya tidak mengubah database yang sudah ada.
- **Executor** `LocalExecutor`: cukup untuk satu mesin dan lebih ringan daripada Celery.
- **Timeout webserver**: `AIRFLOW__WEBSERVER__WEB_SERVER_MASTER_TIMEOUT=300` dan `AIRFLOW__WEBSERVER__WORKERS=2`. Ditambahkan karena start pertama di Docker Desktop (WSL2) melewati batas bawaan 120 detik, sehingga webserver mati dan restart berulang.
- **`restart: unless-stopped`** dan *healthcheck* pada layanan utama, supaya stack naik sendiri setelah laptop dinyalakan ulang.
- **Dockerfile** memasang `requests` ke environment Airflow dan memasang dbt di virtualenv terpisah (`/home/airflow/dbt_venv`) agar dependency-nya tidak bentrok dengan Airflow.

## Verifikasi

```bash
docker compose ps
```

- `warehouse-db` dan `airflow-db`: `healthy`
- `airflow-webserver`: `healthy` (butuh 1-3 menit setelah start)
- `airflow-init`: `Exited (0)`

Lalu buka `http://localhost:8080` dan `http://localhost:3000`. Cek schema di warehouse:

```bash
docker compose exec warehouse-db sh -c "psql -U $POSTGRES_USER -d $POSTGRES_DB -c '\dn'"
```

Harus muncul `raw`, `staging`, dan `marts`.

## Masalah yang pernah muncul

Webserver mati karena timeout, port 8080 bentrok, dan Metabase gagal terhubung: lihat [troubleshooting](troubleshooting.md).