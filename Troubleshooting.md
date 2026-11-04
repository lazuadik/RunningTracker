# Masalah yang ditemui dan solusinya

Jurnal masalah nyata selama membangun Tahap 1-4, beserta penyebab dan cara menemukannya.

## Infrastruktur dan Docker

| Gejala | Penyebab | Solusi |
|---|---|---|
| `airflow-webserver` restart terus; log: `No response from gunicorn master within 120 seconds` | Start pertama di Docker Desktop (WSL2) lebih lama dari batas bawaan 120 detik | Tambahkan `AIRFLOW__WEBSERVER__WEB_SERVER_MASTER_TIMEOUT: "300"` dan `AIRFLOW__WEBSERVER__WORKERS: "2"`, lalu `docker compose up -d` |
| `localhost:8080` tidak terbuka padahal container `healthy`; `curl` menjawab `Empty reply from server` | Dua proses memegang port 8080: Docker di `0.0.0.0` dan aplikasi lain di `127.0.0.1`; `localhost` mengarah ke aplikasi lain | Cek dengan `netstat -ano \| findstr :8080`, lalu ubah mapping port menjadi `8081:8080` |
| `airflow-init` berstatus `Exited` | Memang container sekali jalan (migrasi database dan membuat admin) | Normal selama `Exited (0)` |
| Metabase: *couldn't connect* / *Check your password* | Username di form Metabase tidak sama dengan `WAREHOUSE_USER` di `.env`; Postgres memberi pesan yang sama untuk user dan password salah | Cocokkan dengan `docker compose exec warehouse-db printenv POSTGRES_USER POSTGRES_DB`. Host `warehouse-db`, port `5432` |
| Metabase hanya menampilkan tabel `raw`, tidak ada `marts` | Metabase menyimpan struktur database saat pertama dihubungkan | **Admin settings → Databases → Sync database schema now** |
| Mengubah password warehouse di `.env` tidak berpengaruh | Kredensial hanya dibaca saat volume Postgres pertama kali dibuat | Ubah lewat `ALTER USER` di dalam container, atau `docker compose down -v` kalau datanya masih kosong |

## Airflow dan DAG

| Gejala | Penyebab | Solusi |
|---|---|---|
| *Broken DAG* dengan `SyntaxError: invalid syntax` | Koma terlewat di dictionary; Python melaporkan error di baris **sesudahnya** | Periksa baris sebelum baris yang ditunjuk |
| *Broken DAG*: `ImportError` pada nama fungsi | Salah ketik di baris `import` | Samakan nama dengan definisi di modul |
| `AirflowTimetableInvalid: Exactly 5, 6 or 7 columns` | Nilai `schedule=` bukan ekspresi cron yang valid | Pakai `"@daily"` atau cron 5 kolom |
| DAG tampil hijau tapi grafik kosong, `airflow tasks list` kosong | Baris pemanggilan task di dalam fungsi DAG menjorok terlalu dalam, sehingga masuk ke fungsi `load` setelah `return` | Pemanggilan task harus menjorok sejajar dengan `@task` di dalam fungsi DAG |
| Task merah, log UI kosong | Log tidak tampil di UI | Jalankan fungsinya langsung: `docker compose exec airflow-scheduler python -c "from include.db import init_tables; init_tables()"` |
| `TypeError: '_Environ' object is not callable` | `os.environ(...)` dipanggil seperti fungsi | `os.environ["NAMA"]` (wajib ada) atau `os.getenv("NAMA", "default")` |
| `syntax error at or near "TEXT"` pada DDL | Nama kolom `refresh token` (spasi) bukan `refresh_token` | Nama kolom tidak boleh mengandung spasi |
| `relation "strava_tokens" does not exist` | Nama tabel di kode berbeda dari tabel yang dibuat (`raw.strava_auth`) | Samakan nama tabel dan kolom di tiga tempat: DDL, fungsi baca, fungsi simpan |
| `_save_refresh_token() takes 0 positional arguments but 1 was given` | Parameter `token` lupa ditulis di definisi fungsi | `def _save_refresh_token(token: str)` |

## Strava

| Gejala | Penyebab | Solusi |
|---|---|---|
| `401 Unauthorized` pada daftar aktivitas, padahal refresh token berhasil | Token tidak punya scope `activity:read_all` | Ulangi otorisasi dengan scope penuh dan pastikan semua kotak izin tercentang |
| Token baru di `.env` tidak dipakai | Kode membaca token dari `raw.strava_auth` lebih dulu daripada `.env` | `DELETE FROM raw.strava_auth;`, lalu recreate container agar `.env` terbaca |
| Halaman `localhost refused to connect` setelah *Authorize* | Callback diarahkan ke `http://localhost` yang tidak punya server | Normal; ambil `code` dari address bar |

## dbt

| Gejala | Penyebab | Solusi |
|---|---|---|
| `'database' is a required property` | Kunci database di `profiles.yml` tidak terbaca | Pakai kunci `database:` dan pastikan indentasi sejajar |
| `No filter named 'as_int'` | Filter Jinja yang benar di dbt adalah `as_number` | `port: "{{ env_var('WAREHOUSE_PORT', '5432') \| as_number }}"` |
| `function round(double precision, integer) does not exist` | Postgres hanya punya `round(x, n)` untuk `numeric` | Cast ke `::numeric` di staging |
| Semua model menjadi *view* di schema yang salah; peringatan *unused configuration paths* | Kunci di `models:` (`running-tracker`) tidak sama dengan nama proyek (`running_tracker`) | Samakan persis, termasuk garis bawah |
| Model `marts` tetap *view* walaupun dikonfigurasi `table` | Salah ketik `+materalized` (kurang huruf `i`); dbt mengabaikan kunci yang tidak dikenalnya tanpa error | `+materialized: table`. Cek dengan `dbt ls --output json --output-keys "name config"` |
| `dbt debug` menampilkan `git [ERROR]` | Git hanya dibutuhkan untuk `dbt deps` | Abaikan; yang penting `Connection test: OK` |

## Event race, notifikasi, dan CI

| Gejala | Penyebab | Solusi |
|---|---|---|
| `Tidak ada baris event yang valid ... (1 ditolak)` | Satu-satunya baris di CSV gagal validasi (misalnya tanggal `2026/11/22`) | Buka `data/events/rejected/`; kolom `reason` menjelaskan alasannya. Pakai `YYYY-MM-DD` |
| `FileNotFoundError: 'opt/airflow/data/...'` | Path di DAG tanpa `/` di depan sehingga dianggap relatif | `/opt/airflow/data/events/events_seed.csv` |
| `dbt: No such command 'run--select'` | Spasi hilang di perintah `BashOperator` | `dbt run --select ...`. Cek juga `dbt test` |
| `ImportError: cannot import name ...` dari modul `include/` | Fungsi belum ditulis, belum disimpan, atau namanya salah ketik | `docker compose exec airflow-scheduler grep -n "def " /opt/airflow/include/<file>.py` |
| Tabel `marts` tidak berubah setelah ingestion | `marts` berupa table: isinya salinan dari `dbt run` terakhir. View `staging` langsung ikut `raw`, `marts` tidak | Pastikan `dbt_run` ada dan tersambung **setelah** `load` di DAG (`tests/test_dag_integrity.py` memeriksanya) |
| Perintah `docker compose exec ... "...<>..."` gagal di CMD: `> was unexpected at this time` | CMD Windows membaca `<>` sebagai redirect dan tidak mengenal `\"` | Masuk ke psql interaktif: `docker compose exec warehouse-db sh -c "psql -U $POSTGRES_USER -d $POSTGRES_DB"`, lalu ketik SQL di dalamnya |
| Metabase: `Select statement did not produce a ResultSet` | Metabase hanya menjalankan query pembaca; `DELETE`/`UPDATE` tidak mengembalikan hasil | Ubah data lewat psql atau DBeaver; Metabase hanya untuk membaca |
| Data event contoh masih muncul | Upsert hanya menambah dan memperbarui, tidak menghapus | `delete from raw.events where ...` lalu jalankan `events_ingest` lagi |
| Telegram: `KeyError: 'TELEGRAM_BOT_TOKEN'` | Variabel belum ada di `.env` atau container belum dimuat ulang | Isi `.env`, lalu `docker compose up -d --force-recreate airflow-webserver airflow-scheduler` |
| Telegram `401` / `chat not found` | Token salah / `chat_id` salah atau belum pernah mengirim pesan ke bot | Cek token; kirim pesan ke bot dulu, lalu ambil `chat_id` dari `getUpdates` |
| CI gagal di `ruff`: `I001 Import block is un-sorted` | Urutan impor tidak sesuai aturan isort | `ruff check --fix .` lalu commit |

## Pelajaran umum

- Baca **baris terakhir** traceback dan nomor baris file milik sendiri.
- Uji potongan kecil di luar Airflow (`python -c`, `airflow tasks test`) sebelum menunggu retry penjadwal.
- Pengaturan yang salah eja sering diabaikan tanpa error. Bandingkan hasilnya dengan yang diharapkan (jumlah view/table, nama schema), jangan hanya melihat "sukses".
- Hijau di UI belum berarti pekerjaannya terjadi. Selalu verifikasi dengan query ke database.
- Urutan task di DAG adalah bagian dari logika. Task yang tidak punya `>>` ke pendahulunya berjalan bersamaan dengannya, bukan sesudahnya.
- Token, secret, dan password tidak pernah ditempel di chat atau screenshot. Kalau terlanjur, cabut dan buat baru.