import time
from datetime import datetime, timezone

from common import pii
from common.config import MIN_COVERAGE
from common.http import make_session, get_json

NAME = "zangia"

SEARCH_API = "https://new-api.zangia.mn/api/jobs/search"
DETAIL_API_BASE = "https://new-api.zangia.mn/api/jobs/_"

MAX_PAGES = 400
PAGE_LIMIT = 90
PAGE_DELAY = 1.2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) "
                  "Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.zangia.mn",
    "Referer": "https://www.zangia.mn/",
}

session = make_session(HEADERS)


def _params(page):
    return {"limit": PAGE_LIMIT, "page": page, "isSortByJobs": "true", "time": 1}


def _collect(data, seen):
    """Нэг хуудасны items-ийг seen рүү цэвэрлээд хийнэ. Сүүлийн хуудас эсэхийг буцаана."""
    meta = data.get("meta", {})
    items = data.get("items", [])
    for item in items:
        code = item.get("code")
        if code:
            seen[code] = pii.clean_list(item, NAME)
    return (not items) or (not meta.get("hasNextPage"))


def list_items():
    """{job_code: list_payload}, stats буцаана."""
    seen = {}
    failed_pages = []
    expected_pages = None
    api_total = None
    page = 1

    while page <= MAX_PAGES:
        data = get_json(session, SEARCH_API, params=_params(page), label=f"page {page}")
        last_page_reached = False

        if data is None:
            failed_pages.append(page)
            print(f"\n[page {page}] амжилтгүй — тэмдэглээд цааш явна.")
        else:
            if expected_pages is None:
                meta = data.get("meta", {})
                api_total = meta.get("total")
                expected_pages = meta.get("totalPages")
                if not api_total:
                    raise RuntimeError(
                        f"zangia API хоосон хариу өглөө: {str(data)[:300]}")
                print(f"{NAME}: нийт {api_total} зар — {expected_pages} хуудас")
            last_page_reached = _collect(data, seen)

        print(f"\rPage {page}/{expected_pages or '?'} — цугласан: {len(seen)}",
              end="", flush=True)

        if last_page_reached:
            break

        page += 1
        time.sleep(PAGE_DELAY)

    pages_scanned = page

    # Амжилтгүй хуудсуудыг дахин оролдоно
    if failed_pages:
        print(f"\n{len(failed_pages)} хуудсыг дахин оролдож байна: {failed_pages}")
        still_failed = []
        for p in failed_pages:
            time.sleep(10)
            data = get_json(session, SEARCH_API, params=_params(p),
                            attempts=1, timeout=25, label=f"page {p} retry")
            if data is None:
                still_failed.append(p)
            else:
                _collect(data, seen)
                print(f"  page {p} сэргээлээ.")
        failed_pages = still_failed

    coverage = len(seen) / api_total if api_total else 0
    scan_completed = (len(failed_pages) == 0) and (coverage >= MIN_COVERAGE)
    print(f"\nScan {'БҮРЭН' if scan_completed else 'ДУТУУ'} — "
          f"{len(seen)}/{api_total} ({coverage:.0%})")

    stats = {
        "pages_scanned": pages_scanned,
        "failed_pages": len(failed_pages),
        "seen_count": len(seen),
        "scan_completed": scan_completed,
    }
    return seen, stats


def fetch_detail(code):
    data = get_json(session, f"{DETAIL_API_BASE}{code}", label=code)
    if data is None:
        return None
    return pii.clean_detail(data, NAME)


def posted_at(item, detail=None):
    ts = item.get("time")
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()