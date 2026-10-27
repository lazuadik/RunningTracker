-- Peringatan (bukan error): event yang akan datang tapi belum punya link pendaftaran.
{{ config(severity='warn') }}

select
    event_id,
    event_name,
    event_date
from {{ ref('dim_events') }}
where is_upcoming
  and registration_url is null