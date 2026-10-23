import os
import requests

from include.db import connection

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

def _get_refresh_token() -> str:
    """Pakai token terbaru di database; kalau belum ada, ambil dari .env (token pertama)."""

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT refresh_token FROM raw.strava_auth WHERE id = 1")
        row = cur.fetchone()
    return row[0] if row else os.environ["STRAVA_REFRESH_TOKEN"]

def _save_refresh_token(token: str) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.strava_auth (id, refresh_token, updated_at)
            VALUES (1, %s, now())
            ON CONFLICT (id) DO UPDATE
            SET refresh_token = EXCLUDED.refresh_token, updated_at = now()
            """,
            (token,),
        )

def refresh_access_token() -> str:
    """Tukar Refresh Token jadi access token baru""" 
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": _get_refresh_token()
        },
        timeout = 30,
    )
    resp.raise_for_status()
    data = resp.json()
    _save_refresh_token(data["refresh_token"])
    return data["access_token"]

def fetch_activities(access_token: str, after: int = 0, per_page: int = 200) -> list[dict]:
    """Ambil semua aktivitas sejak timestamp after"""

    headers = {"Authorization": f"Bearer {access_token}"}
    activities: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            ACTIVITIES_URL,
            headers = headers,
            params = {"after": after, "per_page": per_page, "page": page},
            timeout = 30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        activities.extend(batch)
        page += 1
    return activities