from include.db import connection

LOG_DDL = """
CREATE TABLE IF NOT EXISTS raw.notification_log (
    activity_id BIGINT PRIMARY KEY,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now()
) 
"""

def _fmt_duration(seconds: int) -> str:
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} j {minutes} m" if hours else f"{minutes} m"

def build_run_summary() -> str | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT activity_name, run_date, distance_km, pace_label, moving_time_s, avg_heartrate
            FROM marts.fct_runs
            ORDER BY run_date DESC
            LIMIT 1
            """
        )
        run = cur.fetchone()
        if run is None:
            return None
        
        cur.execute(
            """
            SELECT total_km, run_count 
            FROM marts.weekly_summary
            WHERE week_start = date_trunc('week', now() AT TIME ZONE 'Asia/Bangkok')::date
            """
        )
        week = cur.fetchone()

        cur.execute(
            """
            SELECT event_name, event_date, weeks_until, readiness_status, est_finish_label, avg_weekly_km_month, target_weekly_mileage
            FROM marts.race_readiness
            ORDER BY event_date DESC
            LIMIT 1 
            """
        )
        race = cur.fetchone()

    name, run_date, km, pace, moving_time, avg_hr = run
    lines = [
        f"🏃 Run: {name} ({run_date.strftime('%d %b %Y')})",
        f"📊 Jarak: {km:.1f} km · Pace: {pace} · Durasi: {_fmt_duration(moving_time)}",
        f"❤️  Rata-rata HR: {avg_hr:.0f} bpm"
    ]

    week_km, week_runs = (float(week[0]), week[1]) if week else (0.0, 0)
    lines += ["", f"📃 Minggu ini: {week_km: .1f} KM dalam {week_runs} lari"]

    if race:
        ev_name, ev_date, weeks_until, readiness, est_finish, avg_weekly_km_month, target_weekly_mileage = race
        lines += [
            "",
            f"🎯 {ev_name} ({ev_date.strftime('%d %b %Y')}, {weeks_until} minggu lagi)",
            f"Status: {readiness} · Est. Finish: {est_finish}",
            f"Rata-rata mingguan bulan ini: {avg_weekly_km_month:.1f} km · Target mingguan: {target_weekly_mileage:.1f} km"
        ]

    return "\n".join(lines)


def notify_if_new_run(send) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(LOG_DDL)
        cur.execute(
            "SELECT activity_id FROM marts.fct_runs ORDER BY started_at_local DESC LIMIT 1"
        )
        row = cur.fetchone()

        if row is None:
            return False
        activity_id  = row[0]
        cur.execute(
            "SELECT 1 FROM raw.notification_log WHERE activity_id = %s", (activity_id,)
        )
        if cur.fetchone():
            return False

    send(build_run_summary())

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.notification_log (activity_id) VALUES (%s) ON CONFLICT DO NOTHING", (activity_id,)
        )
    return True