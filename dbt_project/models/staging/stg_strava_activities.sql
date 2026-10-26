-- Staging: pecah payload JSON jadi kolom bertipe, rapikan nama dan satuan.
-- Semua jenis aktivitas dipertahankan di sini; filter lari dilakukan di fct_runs.
 
 with source as (
    select * from {{ source('raw', 'strava_activities')}}

 ),

 parsed as (
    select
        activity_id,
        payload ->> 'name' as activity_name,
        coalesce(payload ->> 'sport_type', payload ->> 'type') as sport_type,

        (payload ->> 'start_date')::timestamptz as started_at_utc,
        (payload ->> 'start_date_local')::timestamptz as started_at_local,

        (payload ->> 'distance')::numeric as distance_m,
        (payload ->> 'moving_time')::int as moving_time_s,
        (payload ->> 'elapsed_time')::int as elapsed_time_s,
        (payload ->> 'total_elevation_gain')::numeric as elevation_gain_m,
        (payload ->> 'average_speed')::numeric as avg_speed_mps,
        (payload ->> 'average_heartrate')::numeric as avg_heartrate,
        (payload ->> 'max_heartrate')::numeric as max_heartrate,

        ingested_at
    from source 

 )

 select 
    *
 from parsed 