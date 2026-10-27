-- Kesiapan lari untuk tiap event yang akan datang. Ini yang menghubungkan data Strava dengan data event.
--
-- CATATAN: angka di sini adalah PERKIRAAN sederhana, bukan rencana latihan.
--   * Estimasi waktu finis memakai rumus Riegel: T2 = T1 * (D2 / D1) ^ 1.06,
--     dengan T1/D1 = lari tercepat (per pace) berjarak >= 5 km dalam 90 hari terakhir.
--     Rumus ini cenderung terlalu optimis untuk half dan full marathon kalau mileage mingguan rendah.
--   * Target mileage mingguan dan ambang status di bawah hanyalah patokan kasar; silakan disesuaikan.

with today as(
    select (now() at time zone 'Asia/Bangkok')::date as d
)

runner as (
    select 
        coalesce(sum(r.distance_km) filter (where r.run_date >= t.d - 28), 0) / 4.0 as avg_weekly_km_month,
        coalesce(max(r.distance_km) filter (where r.run_date >= t.d - 56), 0) as longest_run_2_months
    from today t
    cross join {{ ref('fct_runs') }} r on true
),

reference as (
    select
        r.distance_km as ref_km,
        r.moving_time_s as ref_time_s,
        r.run_date as ref_date
    from {{ ref('fct_runs') }} r
    cross join today t
    where r.run_date >= t.d - 90 and r.distance_km >= 5
    order by r.pace_sec_per_km
    limit 1
)

scored as (
    select 
        e.event_id,
        e.event_name,
        e.event_date,
        e.city,
        e.distance_label,
        e.distance_km,
        e.registraion_url,
        e.days_until,
        e.days_until/7 as weeks_until,
        rn.avg_weekly_km_month,
        rn.longest_run_2_months,
        case 
            e.distance_label
                when "5K" then 15
                when "10K" then 25
                when "21K" then 35
                when "42K" then 50
        end as target_weekly_mileage,
        ref.ref_km,
        ref.ref_date,
        case 
            when ref.ref_km is not null
                then round(ref.ref_time_s * power(e.distance_km / ref.ref_km, 1.06))::int
        end as est_finish_s
    from {{ ref{'dim_events'} }} e
    cross join runner rn
    left join reference ref on true
    where e.is_upcoming
),

ratio as (
    select 
        *, 
        avg_weekly_km_month / target_weekly_mileage as weekly_ratio,
        longest_run_2_months / distance_km as longest_ratio
    from scored
)

select 
    event_id,
    event_name,
    event_date,
    city,
    distance_label, 
    distance_km,
    registration_url,
    days_until,
    weeks_until,
    round(avg_weekly_km_month, 1) as avg_weekly_km_month,
    longest_run_2_months,
    target_weekly_mileage,
    round(weekly_ratio, 2) as weekly_mileage_ratio,
    round(longest_ratio, 2) as longest_run_ratio,
    ref_km,
    ref_date,
    est_finish_s,
    case 
        when est_finish_s is not null 
            then (est_finish_s / 3600)::text
                || ':' || lpad(((est_finish_s % 3600) / 60)::text, 2, '0')
                || ':' || lpad((est_finish_s % 60)::text, 2, '0')
    end as est_finish_label,
    case 
        when weekly_mileage_ratio >= 1.0 and longest_run_ratio >= 0.75 then 'Ready'
        when weekly_mileage_ratio >= 0.6 and longest_run_ratio >= 0.5 then 'On Track'
        else "Try Hard Bro"
    end as readiness_status
from ratio
order by event_date, distance_km

