import time
from datetime import datetime, timedelta, timezone

from common import pii
from common.config import MIN_COVERAGE
from common.http import make_session, post_json

NAME = "worki"

GQL = "https://graphql.worki.mn/graphql"
PAGE_SIZE = 100          
MAX_PAGES = 50
PAGE_DELAY = 1.5
MN_TZ = timezone(timedelta(hours=8))   

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) "
                  "Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://worki.mn",
    "Referer": "https://worki.mn/",
}

session = make_session(HEADERS)

LIST_QUERY = """query($page:Int,$size:Int,$searchType:String){
  jobFilter(page:$page,size:$size,searchType:$searchType){
    totalElements,totalPages,numberOfElements,last,
    content{
      id,name,addressNames,positionType,positionLevel,companyName,
      state,categoryId,expiryDate,disabled,createdAt,updatedAt,
      salary{min,max,option,negotiate},
      company{id,name,slug}
    }
  }
}"""

DETAIL_QUERY = """query($id:ID!){
  job(id:$id){
    id,name,positionType,positionLevel,expiryDate,
    responsibility,description,benefits,addressNames,
    disabled,isStudent,canWorkToCountry,
    salary{min,max,option,negotiate},
    requirement{
      educations{level,profession},
      experiences{position,yearOfAtLeast,category},
      languages{id,name,type,skillLevel},
      skills{id,name,type,skillLevel},
      qualifications{qualification},
      trainings{name}
    },
    company{id,name,slug}
  }
}"""


def _fetch_page(page):
    body = {"query": LIST_QUERY,
            "variables": {"page": page, "size": PAGE_SIZE, "searchType": "ALL"}}
    data = post_json(session, GQL, body, label=f"page {page}")
    if data is None:
        return None
    return data.get("jobFilter")


def _collect(block, seen):
    for item in block.get("content") or []:
        job_id = item.get("id")
        if job_id:
            seen[job_id] = pii.clean_list(item, NAME)


def list_items():
    seen = {}
    failed_pages = []

    first = _fetch_page(0)
    if first is None:
        print(f"\n{NAME}: эхний хуудас татагдсангүй — scan зогслоо.")
        return {}, {"pages_scanned": 1, "failed_pages": 1,
                    "seen_count": 0, "scan_completed": False}

    api_total = first.get("totalElements")
    total_pages = first.get("totalPages") or 1
    print(f"{NAME}: нийт {api_total} зар — {total_pages} хуудас")
    _collect(first, seen)

    page = 1
    while page < min(total_pages, MAX_PAGES):
        time.sleep(PAGE_DELAY)
        block = _fetch_page(page)
        if block is None:
            failed_pages.append(page)
            print(f"\n[page {page}] амжилтгүй — тэмдэглээд цааш явна.")
        else:
            _collect(block, seen)
        print(f"\rPage {page + 1}/{total_pages} — цугласан: {len(seen)}",
              end="", flush=True)
        page += 1

    pages_scanned = min(total_pages, MAX_PAGES)

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
    body = {"query": DETAIL_QUERY, "variables": {"id": str(code)}}
    data = post_json(session, GQL, body, label=str(code))
    if data is None:
        return None
    job = data.get("job")
    if job is None:
        return None
    return pii.clean_detail(job, NAME)


def posted_at(item, detail=None):
    raw = item.get("createdAt")
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=MN_TZ).astimezone(timezone.utc).isoformat()