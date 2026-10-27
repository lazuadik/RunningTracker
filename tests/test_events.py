"""Tes untuk validasi data event (tanpa database). Jalankan dari root proyek: python -m pytest"""
from datetime import date

import pytest

from include.events import make_event_id, parse_events

HEADER = "name,event_date,city,distance,price_idr,registration_url,source\n"


def write_csv(tmp_path, body: str):
    path = tmp_path / "events.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_normalizes_distance_date_and_price(tmp_path):
    path = write_csv(tmp_path, "Lomba A,14/02/2027,  Jakarta  ,half marathon,Rp 400.000,https://x.id,web\n")
    valid, rejected = parse_events(path)
    assert rejected == []
    row = valid[0]
    assert row["event_date"] == date(2027, 2, 14)
    assert row["distance_label"] == "21K"
    assert row["distance_km"] == pytest.approx(21.0975)
    assert row["price_idr"] == 400000
    assert row["city"] == "Jakarta"


def test_rejects_bad_rows_with_reason(tmp_path):
    body = (
        "Tanggal ngawur,31-31-2027,Jakarta,10K,,,\n"
        "Jarak aneh,2027-01-01,Jakarta,7K,,,\n"
        ",2027-01-01,Jakarta,10K,,,\n"
        "URL salah,2027-01-01,Jakarta,10K,,ftp://x,\n"
        "Harga salah,2027-01-01,Jakarta,10K,2.5jt,,\n"
    )
    valid, rejected = parse_events(write_csv(tmp_path, body))
    assert valid == []
    assert len(rejected) == 5
    assert [r["line"] for r in rejected] == [2, 3, 4, 5, 6]
    assert all(r["reason"] for r in rejected)


def test_duplicate_rows_collapse_to_one(tmp_path):
    body = (
        "Lomba A,2027-02-14,Jakarta,10K,100000,,\n"
        "lomba   a,2027-02-14,Jakarta,10k,150000,,\n"  # nama sama (beda spasi/huruf), harga diperbarui
    )
    valid, rejected = parse_events(write_csv(tmp_path, body))
    assert rejected == []
    assert len(valid) == 1
    assert valid[0]["price_idr"] == 150000  # yang terakhir menang


def test_event_id_is_stable():
    assert make_event_id("Lomba A", date(2027, 1, 1), "10K") == make_event_id("lomba a", date(2027, 1, 1), "10K")
    assert make_event_id("Lomba A", date(2027, 1, 1), "10K") != make_event_id("Lomba A", date(2027, 1, 1), "21K")


def test_missing_required_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("name,city\nLomba,Jakarta\n", encoding="utf-8")
    with pytest.raises(ValueError, match="kolom wajib"):
        parse_events(path)