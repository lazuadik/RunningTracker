import csv
import hashlib
import re
from datetime import date, datetime
from pathlib import Path

from psycopg2.extras import execute_values
from include.db import connection

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.events (
    event_id            TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    event_date          DATE NOT NULL,
    city                TEXT,
    distance_label      TEXT NOT NULL,
    distance_km         NUMERIC(6, 3) NOT NULL,
    price_idr           INTEGER,
    registration_url    TEXT,
    source              TEXT NOT NULL,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Label untuk jarak yang diterima
DISTANCES = {"5K": 5.0, "10K": 10.0, "21K": 21.0975, "42K": 42.195}

_DISTANCE_WORDS = {
    "hm": "21K", "half": "21K", "half marathon": "21K", "half-marathon": "21K",
    "fm": "42K", "full": "42K", "marathon": "42K", "full marathon": "42K", "full-marathon": "42K",
    "10 k": "10K", "10k": "10K", "5 k": "5K", "5k": "5K",
}

_DISTANCE_RANGE = [
    (4.9, 5.1, "5K"), (9.9, 10.1, "10K"), (20.9, 21.2, "21K"), (41.9, 42.4, "42K")
]

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y")

REQUIRED_COLUMNS = {"name", "event_date", "distance"}

def make_event_id(name:str, event_date:date, distance_label:str) -> str:
    """ID stabil dari isi event: file sama dibaca dua kali menghasilkan ID yang sama (idempotent)"""

    key = f"{name.lower()}|{event_date.isoformat()}|{distance_label}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def _parse_date(value) -> date:
    s = (value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"tanggal tidak valid: {value!r} (pakai YYYY-MM-DD atau DD/MM/YYYY)")

def _parse_distance(value) -> str:
    s = " ".join((value or "").lower().split()).replace(",", ".")
    if not s:
        raise ValueError("jarak kosong")
    if s in _DISTANCE_WORDS:
        return _DISTANCE_WORDS[s]
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:k|km)?", s)
    if match:
        number = float(match.group(1))
        for low, high, label in _DISTANCE_RANGE:
            if low <= number <= high:
                return label
    raise ValueError(f"jarak tidak dikenali: {value!r} (didukung: 5K, 10K, 21K/HM, 42K/FM)")

def _parse_price(value):
    s = (value or "").strip().lower()
    if not s:
        return None
    if s in ("gratis", "free"):
        return 0
    cleaned = re.sub(r"^rp\.?\s*", "", s).replace(".", "").replace(",", "").replace(" ", "")
    if not cleaned.isdigit():
        raise ValueError(f"harga tidak valid: {value!r}")
    return int(cleaned)

def _clean_row(raw: dict) -> dict:
    name = " ".join((raw.get("name") or "").split())
    if not name:
        raise ValueError("nama kosong")
    event_date = _parse_date(raw.get("event_date"))
    label = _parse_distance(raw.get("distance"))
    city = " ".join((raw.get("city") or "").split()) or None
    url = (raw.get("registration_url") or "").strip() or None
    if url and not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL harus diawali dengan http atau https")
    return {
        "event_id": make_event_id(name, event_date, label),
        "name": name,
        "event_date": event_date,
        "city": city,
        "distance_label": label,
        "distance_km": DISTANCES[label],
        "price_idr": _parse_price(raw.get("price_idr")),
        "registration_url": url,
        "source": (raw.get("source") or "").strip() or "manual",
    }

def parse_events(path) -> tuple[list[dict], list[dict]]:
    """Baca csv, mengembalikan baris valid, baris ditolak, dan alasan. Duplikat digabung: yang terakhir menang"""
    valid_by_id: dict[str, str] = {}
    rejected: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as f:

        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"kolom wajib tidak ada di csv: {sorted(missing)}")
        for line_no, raw in enumerate(reader, start = 2):
            try:
                row = _clean_row(raw)
            except ValueError as exc:
                rejected.append({**raw, "line": line_no, "reason": str(exc)})
                continue
            valid_by_id[row["event_id"]] = row
    return list(valid_by_id.values()), rejected 

def write_rejected(rejected: list[dict], directory: Path):
    """Simpan baris yang ditolak ke file supaya bisa diperbaiki. Mengembalikan path-nya (atau None)."""
    if not rejected:
        return None
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"rejected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fields = ["line", "reason", "name", "event_date", "city", "distance",
              "price_idr", "registration_url", "source"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rejected)
    return path

def init_events_table() -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(DDL)


def upsert_events(rows: list[dict]) -> int:
    """Upsert berdasarkan event_id: dijalankan dua kali hasilnya sama"""
    values = [
        (r["event_id"], r["name"], r["event_date"], r["city"], r["distance_label"],
         r["distance_km"], r["price_idr"], r["registration_url"], r["source"])
        for r in rows
    ]
    with connection() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO raw.events
                (event_id, name, event_date, city, distance_label, distance_km,
                 price_idr, registration_url, source)
            VALUES %s
            ON CONFLICT (event_id) DO UPDATE
            SET name = EXCLUDED.name,
                event_date = EXCLUDED.event_date,
                city = EXCLUDED.city,
                distance_label = EXCLUDED.distance_label,
                distance_km = EXCLUDED.distance_km,
                price_idr = EXCLUDED.price_idr,
                registration_url = EXCLUDED.registration_url,
                source = EXCLUDED.source,
                ingested_at = now()
            """,
            values,
        )
    return len(values)

def load_events(csv_path, rejected_dir) -> dict:
    """Alur lengkap: baca -> validasi -> simpan baris ditolak -> upsert yang valid."""
    valid, rejected = parse_events(csv_path)
    rejected_file = write_rejected(rejected, Path(rejected_dir))
    if not valid:
        raise ValueError(f"Tidak ada baris event yang valid di {csv_path} ({len(rejected)} ditolak)")
    loaded = upsert_events(valid)
    return {
        "valid": len(valid),
        "rejected": len(rejected),
        "loaded": loaded,
        "rejected_file": str(rejected_file) if rejected_file else None,
    }