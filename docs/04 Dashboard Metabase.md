# Tahap 4: Dashboard Metabase

## Tujuan

Menampilkan performa lari dari schema `marts` dalam satu dashboard yang bisa dibuka di browser.

## Menghubungkan Metabase ke warehouse

Saat pertama kali membuka `http://localhost:3000`, Metabase meminta pembuatan akun admin lokal. Lalu tambahkan database lewat **Admin settings → Databases → Add database**:

| Kolom | Isi |
|---|---|
| Database type | PostgreSQL |
| Host | `warehouse-db` |
| Port | `5432` |
| Database name | nilai `WAREHOUSE_DB` di `.env` |
| Username / Password | nilai `WAREHOUSE_USER` / `WAREHOUSE_PASSWORD` di `.env` |

Host `warehouse-db` dan port `5432` dipakai karena Metabase berjalan di jaringan Docker yang sama dengan warehouse. `localhost:5433` hanya berlaku untuk aplikasi di laptop.

Metabase menyimpan salinan struktur database saat pertama dihubungkan. Setelah dbt membuat schema atau tabel baru, buka **Admin settings → Databases → pilih database → Sync database schema now** supaya schema `marts` muncul.

## Kartu pada dashboard `Running Performance`

Setiap kartu dibuat dari **New → SQL query**, lalu disimpan ke dashboard yang sama. Sesuaikan nama kolom kalau model di repo berbeda.

**Angka (visualisasi *Number*)**

```sql
-- Total km 30 hari terakhir
select coalesce(sum(distance_km), 0) as total_km_30_hari
from marts.fct_runs
where run_date >= current_date - 30;
```
```sql
-- Jumlah lari
select count(*) as jumlah_lari from marts.fct_runs;
```
```sql
-- Lari terpanjang (km)
select max(distance_km) as lari_terpanjang_km from marts.fct_runs;
```
```sql
-- Total jam berlari
select round(sum(moving_time_s) / 3600.0, 1) as total_jam from marts.fct_runs;
```

**Grafik**

```sql
-- Mileage mingguan (Bar)
select week_start, total_km from marts.weekly_summary order by week_start;
```
```sql
-- Tren pace mingguan (Line)
select week_start, avg_pace_min_per_km from marts.weekly_summary order by week_start;
```

Pada grafik pace, angka yang lebih kecil berarti lebih cepat, jadi garis yang turun menandakan peningkatan.

**Tabel**

```sql
-- Rekor pribadi
select distance_bucket as jarak, pace_label as pace,
       round(moving_time_s / 60.0, 1) as menit, run_date as tanggal
from marts.personal_records
order by distance_km;
```
```sql
-- 10 lari terakhir
select run_date, activity_name, distance_km, pace_label, moving_time_min
from marts.fct_runs
order by run_date desc
limit 10;
```

## Menyusun dashboard

Buka dashboard, klik ikon pensil, lalu atur tata letak: angka di baris atas, dua grafik di tengah, dua tabel di bawah. Simpan.

## Screenshot untuk README

Simpan screenshot dashboard sebagai `docs/images/dashboard.png`, lalu aktifkan baris gambar yang dikomentari di bagian atas `README.md`.

## Catatan

- Metabase menyimpan akun dan dashboard di volume Docker `metabase-data`. Perintah `docker compose down -v` **menghapus** volume itu, jadi dashboard ikut hilang.
- Semua kartu membaca schema `marts`; perubahan struktur di `raw` atau `staging` tidak memengaruhinya selama model `marts` tetap menghasilkan kolom yang sama.