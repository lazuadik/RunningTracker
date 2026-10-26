-- Peringatan (bukan error) kalau ada lari dengan pace yang tidak masuk akal:
-- lebih cepat dari 2:30 /km atau lebih lambat dari 15:00 /km (biasanya salah kategori / data GPS rusak).

{{config(severity='warn')}}

select
    activity_id,
    run_date,
    distance_km, 
    pace_min_per_km
from
    {{ ref('fct_runs') }}
where pace_min_per_km < 2.5