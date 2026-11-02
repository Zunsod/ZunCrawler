import time

import psycopg
from psycopg.types.json import Jsonb

from common.config import DATABASE_URL

ATTEMPTS = 3
RETRY_DELAY = 5

_conn = None


def _connection():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=15)
    return _conn


def execute(sql, params=None):
    """SQL ажиллуулж мөрүүдийг буцаана. Холболт тасарвал дахин холбогдож оролдоно.

    Дахин оролдох тул бичилт бүр давтан ажиллахад аюулгүй байх ёстой.
    """
    for i in range(ATTEMPTS):
        try:
            with _connection().cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall() if cur.description else []
        except psycopg.OperationalError as e:
            if _conn is not None:
                _conn.close()
            if i == ATTEMPTS - 1:
                raise
            print(f"\n[DB] Оролдлого {i+1}/{ATTEMPTS} амжилтгүй: {e}")
            time.sleep(RETRY_DELAY)


def load_codes(source):
    rows = execute("SELECT job_code, is_active FROM raw_jobs WHERE source = %s", (source,))
    return dict(rows)


def upsert_job(source, code, list_payload, detail_payload, posted_at):
    execute("""
        INSERT INTO raw_jobs (source, job_code, list_payload, detail_payload, posted_at, is_active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (source, job_code) DO UPDATE SET
            list_payload = EXCLUDED.list_payload,
            detail_payload = EXCLUDED.detail_payload,
            posted_at = EXCLUDED.posted_at,
            is_active = TRUE
    """, (source, code, Jsonb(list_payload), Jsonb(detail_payload), posted_at))


def mark_reopened(source, codes):
    codes = list(codes)
    # is_active шалгалт нь дахин оролдоход reopen_count давхар нэмэгдэхээс хамгаална
    execute("""
        UPDATE raw_jobs
        SET is_active = TRUE, closed_at = NULL, reopen_count = COALESCE(reopen_count, 0) + 1
        WHERE source = %s AND job_code = ANY(%s::text[]) AND is_active IS NOT TRUE
    """, (source, codes))
    return len(codes)


def mark_closed(source, codes, closed_at):
    codes = list(codes)
    execute("""
        UPDATE raw_jobs
        SET is_active = FALSE, closed_at = %s
        WHERE source = %s AND job_code = ANY(%s::text[])
    """, (closed_at, source, codes))
    return len(codes)


def refresh_jobs_unified():
    """raw_jobs -> jobs_unified-г шинэчилнэ (DB дээрх SQL функц)."""
    execute("SELECT refresh_jobs_unified()")


def refresh_jobs_clean():
    """jobs_unified -> jobs_clean-г шинэчлэнэ (normalize + dedup)."""
    execute("SELECT refresh_jobs_clean()")
