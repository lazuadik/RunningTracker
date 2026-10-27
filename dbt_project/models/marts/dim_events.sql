with today as(
    select (now() at time zone 'Asia/Bangkok')::date as d
)

select
    e.event_id,
    e.event_name,
    e.event_date,
    e.distance_label,
    e.distance_km,
    e.price_idr,
    e.registration_url,
    e.source,
    (e.event_date - t.d) as days_until,
    (e.event_date >= t.d) as is_upcoming
from {{ ref('stg_event') }} e
cross join today t