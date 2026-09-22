import json
import re
import time

from common import pii
from common.http import make_session, get_text

NAME = "lambda"

JOBS_URL = "https://lambda.global/jobs"
LIST_URL = "https://lambda.global/jobs?sortBy=newest"      # шинэ гэсэн эрэмбээр тогтвортой pagination хийнэ
MAX_PAGES = 60          
PAGE_DELAY = 1.5
EMPTY_STREAK_LIMIT = 2  # дараалан шинэ slug гарахгүй бол зогсоно

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) "
                  "Gecko/20100101 Firefox/153.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "mn,en;q=0.9",
}

session = make_session(HEADERS)

SLUG = re.compile(r"/jobs/([a-z0-9][a-z0-9\-]*-\d{6,})")
FLIGHT = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')
DECODER = json.JSONDecoder()


def _flight_text(html):
    """Next.js-ийн бүх script блокийг нийлүүлж unescape хийнэ

    JSON нэг объект хоёр push-д тасарч болдог тул заавал нийлүүлж байж parse хийнэ
    """
    parts = []
    for chunk in FLIGHT.findall(html):
        try:
            parts.append(json.loads('"' + chunk + '"'))
        except ValueError:
            continue
    return "".join(parts)


def _extract_job(text):
    """jobCategoryId агуулсан JSON объектыг бүтнээр нь сугалж авна"""
    i = text.find('"jobCategoryId"')
    if i == -1:
        return None
    j = i
    while True:
        j = text.rfind("{", 0, j)
        if j == -1:
            return None
        try:
            obj, end = DECODER.raw_decode(text, j)
        except ValueError:
            continue
        if isinstance(obj, dict) and end > i and "jobCategoryId" in obj:
            return obj


def list_items():
    """{slug: list_payload}. Lambda-д жагсаалтаас зөвхөн slug гарна."""
    seen = {}
    failed_pages = []
    empty_streak = 0
    page = 1
    ended_naturally = False

    while page <= MAX_PAGES:
        html = get_text(session, f"{LIST_URL}&page={page}", label=f"page {page}")

        if html is None:
            failed_pages.append(page)
            print(f"\n[page {page}] амжилтгүй — тэмдэглээд цааш явна.")
        else:
            slugs = SLUG.findall(html)
            fresh = [s for s in slugs if s not in seen]
            for slug in slugs:
                seen.setdefault(slug, {"slug": slug, "list_page": page})

            if fresh:
                empty_streak = 0
            else:
                empty_streak += 1
                if empty_streak >= EMPTY_STREAK_LIMIT:
                    ended_naturally = True

        print(f"\rPage {page} — цугласан: {len(seen)}", end="", flush=True)

        if ended_naturally:
            break

        page += 1
        time.sleep(PAGE_DELAY)

    pages_scanned = page
    scan_completed = ended_naturally and not failed_pages
    print(f"\nScan {'БҮРЭН' if scan_completed else 'ДУТУУ'} — {len(seen)} зар "
          f"({pages_scanned} хуудас)")

    stats = {
        "pages_scanned": pages_scanned,
        "failed_pages": len(failed_pages),
        "seen_count": len(seen),
        "scan_completed": scan_completed,
    }
    return seen, stats


def fetch_detail(code):
    html = get_text(session, f"{JOBS_URL}/{code}", label=str(code))
    if html is None:
        return None
    job = _extract_job(_flight_text(html))
    if job is None:
        print(f"\n[{code}] HTML-ээс JSON салгаж чадсангүй.")
        return None
    return pii.clean_detail(job, NAME)


def posted_at(item, detail=None):
    if not detail:
        return None
    return detail.get("createdAt")   