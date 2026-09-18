from common.config import supabase


def record(source, started_at, finished_at, stats):
    supabase.table("scan_runs").insert({
        "source": source,
        "started_at": started_at,
        "finished_at": finished_at,
        "pages_scanned": stats.get("pages_scanned", 0),
        "failed_pages": stats.get("failed_pages", 0),
        "seen_count": stats.get("seen_count", 0),
        "new_count": stats.get("new_count", 0),
        "closed_count": stats.get("closed_count", 0),
        "reopened_count": stats.get("reopened_count", 0),
        "scan_completed": stats.get("scan_completed", False),
    }).execute()