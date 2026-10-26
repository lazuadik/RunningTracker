-- Rekor pribadi per kelompok jarak, diambil dari pace tercepat di tiap kelompok.
-- Catatan: ini perkiraan berdasarkan jarak total aktivitas (mis. lari 5,2 km masuk "5K").
-- Untuk PR yang tepat (best effort 5K di tengah lari panjang), nanti perlu data detail
-- per aktivitas dari Strava (best_efforts/splits).

with bucketed as(
    select
        *,
        case
            when distance_km between 4.8 and 5.5 then '5K'
            when distance_km between 9.5 and 11.0 then '10K'
            when distance_km between 19.0 and 22.0 then 'Half Marathon'
            when distance_km between 41.0 and 44.0 then 'Marathon'
        end as distance_bucket
    from {{ ref('fct_runs') }}
),

ranked as (

    select 
        *,
        row_number() over(partition by distance_bucket order by pace_sec_per_km asc) as pace_rank
    from bucketed
    where distance_bucket is not null
)

select
    distance_bucket,
    activity_id,
    run_date,
    distance_km,
    moving_time_s,
    pace_min_per_km,
    pace_label
from  ranked
where pace_rank = 1