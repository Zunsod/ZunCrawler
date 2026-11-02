from common.db import execute


def record(source, started_at, finished_at, stats):
    execute("""
        INSERT INTO scan_runs (source, started_at, finished_at, pages_scanned, failed_pages,
                               seen_count, new_count, closed_count, reopened_count, scan_completed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        source,
        started_at,
        finished_at,
        stats.get("pages_scanned", 0),
        stats.get("failed_pages", 0),
        stats.get("seen_count", 0),
        stats.get("new_count", 0),
        stats.get("closed_count", 0),
        stats.get("reopened_count", 0),
        stats.get("scan_completed", False),
    ))
