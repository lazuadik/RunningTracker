with run as(
  select * from {{ ref('stg_strava_activities') }}
  where sport_type in ('Run', 'TrailRun', 'Walk') 
    and distance_m > 0 
    and moving_time_s > 0
),

calc as (
  select
    activity_id,
    activity_name,
    sport_type,
    started_at_utc,
    started_at_local,
    started_at_local::date as run_date,
    date_trunc('week', started_at_local)::date as week_start,
    round(distance_m / 1000.0, 2) as distance_km,
    moving_time_s,
    round(moving_time_s / 60.0, 1) as moving_time_min,
    elevation_gain_m,
    moving_time_s / (distance_m / 1000.0) as pace_sec_per_km,
    avg_heartrate,
    max_heartrate
  from run 
)

select
  *,
  round(pace_sec_per_km / 60.0, 2) as pace_min_per_km,
    floor(pace_sec_per_km / 60)::int
        || ':' || lpad(floor(mod(pace_sec_per_km, 60))::int::text, 2, '0') as pace_label
from calc

