# Running Tracker

Pipeline data end-to-end untuk menganalisis performa lari pribadi: aktivitas diambil dari **Strava API**, diorkestrasi dengan **Apache Airflow**, disimpan di **PostgreSQL**, ditransformasi dengan **dbt**, lalu ditampilkan di dashboard **Metabase**. Seluruh stack berjalan lokal lewat Docker Compose dan tidak membutuhkan biaya.

> Proyek belajar data engineering. Data yang dipakai adalah data aktivitas lari milik penulis sendiri.

docs/images/dashboard.png

## Status

| Tahap | Isi | Status |
|---|---|---|
| 1 | Infrastruktur Docker Compose (Airflow, Postgres, Metabase) | ✅ |
| 2 | Ingestion Strava: incremental dan idempotent | ✅ |
| 3 | Transformasi dbt (staging → marts) dengan test | ✅ |
| 4 | Dashboard performa lari di Metabase | ✅ |
| – | dbt dijalankan otomatis oleh Airflow setelah ingestion | ⬜ |
| – | Pipeline event race dan `race_readiness` | ⬜ |
| – | Alerting dan CI (GitHub Actions) | ⬜ |
| – | Deploy ke VPS | ⬜ |

## Arsitektur

```mermaid
flowchart LR
    A["Strava API"] -->|"OAuth2 + REST"| B["Airflow: DAG strava_ingest"]
    B --> C[("File JSON mentah<br/>data/raw/strava")]
    B --> D[("Postgres: schema raw")]
    D --> E["dbt: schema staging"]
    E --> F["dbt: schema marts"]
    F --> G["Metabase: dashboard"]
```

Data mengalir lewat tiga lapisan di satu warehouse PostgreSQL:

| Lapisan | Schema | Isi | Setara medallion |
|---|---|---|---|
| Mentah | `raw` | Payload JSON Strava apa adanya (`jsonb`) | Bronze |
| Bersih | `staging` | Kolom bertipe dan satuan dasar (meter, detik), semua jenis aktivitas | Silver |
| Siap pakai | `marts` | Hanya lari, sudah dihitung (km, pace), diringkas per minggu | Gold |

Dashboard hanya membaca schema `marts`.

## Tech stack

| Komponen | Pilihan | Peran |
|---|---|---|
| Orkestrasi | Apache Airflow 2.10 (LocalExecutor) | Menjadwalkan dan menjalankan DAG |
| Warehouse | PostgreSQL 16 | Penyimpanan raw, staging, marts |
| Transformasi | dbt (dbt-postgres) | Model SQL, test, dokumentasi kolom |
| Dashboard | Metabase | Visualisasi |
| Infrastruktur | Docker Compose | Menjalankan semua layanan secara lokal |
| Bahasa | Python 3.11 (`requests`, `psycopg2`) | Client Strava dan loader |

## Struktur repo

```
.
├── docker-compose.yml          # Airflow, dua Postgres, Metabase
├── Dockerfile                  # Image Airflow + dbt (virtualenv terpisah)
├── init-warehouse.sql          # Membuat schema raw, staging, marts
├── .env.example                # Template variabel lingkungan (tanpa secret)
├── dags/
│   └── strava_ingest.py        # DAG ingestion Strava
├── include/
│   ├── db.py                   # Koneksi dan DDL tabel raw
│   └── strava_client.py        # OAuth refresh token + pengambilan aktivitas
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml            # Membaca kredensial dari environment variable
│   ├── macros/                 # generate_schema_name
│   ├── models/staging/         # stg_strava_activities
│   ├── models/marts/           # fct_runs, weekly_summary, personal_records
│   └── tests/                  # test singular (pace masuk akal)
├── data/raw/                   # JSON mentah dari Strava (tidak di-commit)
└── docs/                       # Dokumentasi per tahap
```

## Cara menjalankan

Prasyarat: Docker Desktop (alokasikan RAM minimal 4 GB), Git, dan akun Strava.

1. **Clone repo** lalu masuk ke foldernya.
2. **Buat aplikasi Strava** di `https://www.strava.com/settings/api` dengan *Authorization Callback Domain* `localhost`. Catat Client ID dan Client Secret.
3. **Siapkan `.env`**: salin `.env.example` menjadi `.env` (`copy .env.example .env` di Windows, `cp .env.example .env` di Mac/Linux), lalu isi nilainya. File `.env` sudah ada di `.gitignore`, jangan pernah di-commit.
4. **Ambil refresh token Strava** (sekali saja). Langkahnya ada di [docs/02-ingestion-strava.md](docs/02-ingestion-strava.md#mendapatkan-refresh-token-pertama).
5. **Jalankan stack**:
   ```bash
   docker compose build
   docker compose up -d
   ```
   Tunggu 1-3 menit sampai `docker compose ps` menunjukkan `airflow-webserver` berstatus `healthy`.
6. **Buka layanan**: Airflow di `http://localhost:8080` (login dengan `AIRFLOW_ADMIN_USER` dan `AIRFLOW_ADMIN_PASSWORD`), Metabase di `http://localhost:3000`. Kalau port 8080 sudah dipakai aplikasi lain, ubah mapping port di `docker-compose.yml` (misalnya `8081:8080`).
7. **Jalankan ingestion**: aktifkan DAG `strava_ingest` di Airflow lalu klik *Trigger DAG*. Semua task harus hijau.
8. **Bangun model dbt**:
   ```bash
   docker compose exec airflow-scheduler /home/airflow/dbt_venv/bin/dbt run --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project
   docker compose exec airflow-scheduler /home/airflow/dbt_venv/bin/dbt test --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project
   ```
9. **Hubungkan Metabase** ke warehouse dan buat dashboard. Lihat [docs/04-dashboard-metabase.md](docs/04-dashboard-metabase.md).

## Keputusan desain

| Keputusan | Alasan |
|---|---|
| Payload Strava disimpan mentah sebagai `jsonb` di `raw` | Perubahan atau tambahan field dari Strava tidak merusak ingestion; kolom dipecah di dbt, jadi bisa dihitung ulang kapan saja |
| Upsert berdasarkan `activity_id` (`ON CONFLICT DO UPDATE`) | Idempotent: menjalankan DAG dua kali tidak membuat data ganda |
| Incremental load dengan `lookback` 3 hari | Hanya mengambil aktivitas baru, tetapi tetap menangkap aktivitas yang diedit setelah diunggah |
| Refresh token terbaru disimpan di database | Strava dapat mengganti refresh token pada setiap pembaruan; membaca dari `.env` terus-menerus akan gagal suatu saat |
| Hanya path file JSON yang dikirim antar task Airflow | Menghindari data besar di XCom |
| Dua database Postgres terpisah (metadata Airflow dan warehouse) | Metadata orkestrasi tidak bercampur dengan data analitik |
| dbt di virtualenv terpisah dalam image Airflow | Menghindari konflik dependency dengan Airflow |
| Secret hanya lewat environment variable | `profiles.yml` dan `docker-compose.yml` aman di-commit |
| Pace mingguan = total waktu ÷ total jarak | Lebih akurat daripada merata-ratakan pace tiap lari, yang membuat lari pendek terlalu berpengaruh |

## Kualitas data

- **Test dbt**: `unique` dan `not_null` pada kunci, `accepted_values` pada jenis aktivitas, dan satu test singular yang memperingatkan lari dengan pace tidak masuk akal (di bawah 2:30 atau di atas 15:00 per km).
- **Ingestion idempotent**, dibuktikan dengan menjalankan DAG berulang kali tanpa perubahan jumlah baris.

## Dokumentasi lanjutan

- [Tahap 1: Infrastruktur](docs/01-infrastruktur.md)
- [Tahap 2: Ingestion Strava](docs/02-ingestion-strava.md)
- [Tahap 3: Transformasi dbt](docs/03-transformasi-dbt.md)
- [Tahap 4: Dashboard Metabase](docs/04-dashboard-metabase.md)
- [Masalah yang ditemui dan solusinya](docs/troubleshooting.md)

## Roadmap

- dbt dijalankan otomatis di Airflow (`load → dbt_run → dbt_test`)
- Pipeline event race: CSV manual, validasi, `dim_events`, dan `race_readiness` yang menghubungkan data lari dengan jadwal event
- Alert saat DAG gagal, GitHub Actions (lint, pytest, `dbt parse`)
- Deploy ke VPS dan dashboard publik

## Catatan keamanan dan penggunaan data

- Jangan commit `.env`, token, atau Client Secret. Kalau secret pernah tampil di screenshot atau log, buat ulang di `strava.com/settings/api`.
- Proyek ini hanya memproses data akun penulis sendiri. Sebelum menampilkan data Strava ke pengguna lain, baca dahulu [Strava API Agreement](https://www.strava.com/legal/api).