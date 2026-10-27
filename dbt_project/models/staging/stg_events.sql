-- Staging: ganti nama kolom saja. Pembersihan utama (tanggal, jarak, harga) sudah dilakukan di Python.
 
select
    event_id,
    name as event_name,
    event_date,
    city,
    distance_label,
    distance_km,
    price_idr,
    registration_url,
    source,
    ingested_at
from {{ source('raw_events', 'events') }}