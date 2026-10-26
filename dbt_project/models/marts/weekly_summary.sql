select
    week_start,
    count(*) as run_count,
     round(sum(distance_km), 2)                                      as total_km,
    round(sum(moving_time_s) / 3600.0, 2)                           as total_hours,
    round(sum(moving_time_s) / 60.0 / nullif(sum(distance_km), 0), 2) as avg_pace_min_per_km,
    max(distance_km)                                            as longest_run_km,
    max(moving_time_s)                                         as longest_run_time_s,
    round(sum(elevation_gain_m), 2)                                      as total_elevation_gain_m
from 
    {{ ref('fct_runs') }}
group by week_start
order by week_start desc
