import os
import math
import time
import random
from datetime import datetime, timezone
import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

SEARCH_API = "https://new-api.zangia.mn/api/jobs/search"
DETAIL_API_BASE = "https://new-api.zangia.mn/api/jobs/_"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.zangia.mn",
    "Referer": "https://www.zangia.mn/"
}

session = requests.Session()
session.headers.update(HEADERS)

CHUNK = 200
CLOSE_RATIO_LIMIT = 0.20

started_at = datetime.now(timezone.utc)
now_iso = started_at.isoformat()

# ══ 1. DB-ээс мэдэгдэж буй бүх зарын job_code + is_active уншина ══
db_codes = {}
offset = 0
while True:
    rows = supabase.table("raw_jobs").select("job_code, is_active") \
        .range(offset, offset + 999).execute().data
    if not rows:
        break
    for r in rows:
        db_codes[r["job_code"]] = r["is_active"]
    offset += 1000

active_in_db = {c for c, a in db_codes.items() if a}
inactive_in_db = {c for c, a in db_codes.items() if not a}
print(f"DB: нийт {len(db_codes)} | идэвхтэй {len(active_in_db)} | идэвхгүй {len(inactive_in_db)}")

# ══ 2. zangia-ийн БҮХ хуудсыг уншина (detail дуудахгүй) ══
seen_items = {}
failed_pages = []
expected_pages = None
page = 1

while True:
    if expected_pages and page > expected_pages:
        break

    params = {"limit": 90, "page": page, "isSortByJobs": "true", "time": 1}
    page_ok = False

    for attempt in range(3):
        try:
            res = session.get(SEARCH_API, params=params, timeout=20)
            if res.status_code == 200:
                data = res.json()

                if expected_pages is None:
                    total = data.get("meta", {}).get("total")
                    if total:
                        expected_pages = math.ceil(total / 90)
                        print(f"zangia: нийт {total} зар — {expected_pages} хуудас")

                items = data.get("items", [])
                if not items:
                    expected_pages = page - 1
                    page_ok = True
                    break

                for item in items:
                    code = item.get("code")
                    if code:
                        seen_items[code] = item
                page_ok = True
                break

            elif res.status_code == 429:
                print(f"\n[Rate Limit] page {page} — 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                print(f"\n[page {page}] HTTP {res.status_code}, оролдлого {attempt+1}/3")
                time.sleep(5)

        except Exception as e:
            print(f"\n[page {page}] Оролдлого {attempt+1}/3 амжилтгүй: {e}")
            time.sleep(8)

    if not page_ok:
        failed_pages.append(page)
        print(f"\n[page {page}] амжилтгүй — тэмдэглээд цааш явна.")

    print(f"\rPage {page}/{expected_pages or '?'} — цугласан: {len(seen_items)}", end="", flush=True)
    page += 1
    time.sleep(1.2)

pages_scanned = page - 1

# ══ 3. Амжилтгүй хуудсуудыг дахин оролдоно ══
if failed_pages:
    print(f"\n{len(failed_pages)} хуудсыг дахин оролдож байна: {failed_pages}")
    still_failed = []
    for p in failed_pages:
        time.sleep(10)
        try:
            res = session.get(SEARCH_API, params={"limit": 90, "page": p, "isSortByJobs": "true", "time": 1}, timeout=25)
            if res.status_code == 200:
                for item in res.json().get("items", []):
                    code = item.get("code")
                    if code:
                        seen_items[code] = item
                print(f"  page {p} сэргээлээ.")
            else:
                still_failed.append(p)
        except Exception as e:
            print(f"  page {p} дахин амжилтгүй: {e}")
            still_failed.append(p)
    failed_pages = still_failed

scan_completed = (len(failed_pages) == 0)
print(f"\nScan {'БҮРЭН' if scan_completed else 'ДУТУУ'} — zangia дээр {len(seen_items)} зар")

# ══ 4. Set үйлдлээр 3 бүлэг ялгана ══
today_codes = set(seen_items.keys())
new_codes = today_codes - db_codes.keys()
newly_closed = active_in_db - today_codes
reopened = today_codes & inactive_in_db

print(f"Шинэ: {len(new_codes)} | Хаагдсан: {len(newly_closed)} | Дахин нээгдсэн: {len(reopened)}")

# ══ 5. ШИНЭ зар — detail татаж бүрэн insert ══
for idx, code in enumerate(new_codes, 1):
    item = seen_items[code]
    detail_payload = None

    for attempt in range(3):
        try:
            detail_res = session.get(f"{DETAIL_API_BASE}{code}", timeout=20)
            if detail_res.status_code == 200:
                detail_payload = detail_res.json()
                detail_payload.pop("similarJobs", None)
                break
            elif detail_res.status_code == 429:
                print(f"\n[Rate Limit] 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                time.sleep(3)
        except Exception as e:
            print(f"\n[{code}] Оролдлого {attempt+1}/3: {e}")
            time.sleep(5)

    posted_at = None
    if item.get("time"):
        posted_at = datetime.fromtimestamp(item["time"], tz=timezone.utc).isoformat()

    supabase.table("raw_jobs").upsert({
        "job_code": code,
        "list_payload": item,
        "detail_payload": detail_payload,
        "posted_at": posted_at,
        "is_active": True
    }, on_conflict="job_code").execute()

    print(f"\r  Шинэ зар: [{idx}/{len(new_codes)}]", end="", flush=True)
    time.sleep(random.uniform(1.0, 1.6))

# ══ 6. ДАХИН НЭЭГДСЭН зар ══
if reopened:
    rows = supabase.table("raw_jobs").select("job_code, reopen_count") \
        .in_("job_code", list(reopened)).execute().data
    for r in rows:
        supabase.table("raw_jobs").update({
            "is_active": True,
            "closed_at": None,
            "reopen_count": (r.get("reopen_count") or 0) + 1
        }).eq("job_code", r["job_code"]).execute()
    print(f"\n{len(reopened)} зар дахин нээгдлээ.")

# ══ 7. ХААГДСАН зар — зөвхөн бүрэн scan + sanity check давбал ══
closed_applied = 0
if scan_completed:
    ratio = len(newly_closed) / max(len(active_in_db), 1)
    if ratio > CLOSE_RATIO_LIMIT:
        print(f"⚠ АНХААР: {len(newly_closed)} зар ({ratio:.1%}) хаагдсан гэж гарлаа — хэт их тул update хийсэнгүй.")
    else:
        closed_list = list(newly_closed)
        for i in range(0, len(closed_list), CHUNK):
            batch = closed_list[i:i+CHUNK]
            supabase.table("raw_jobs").update({
                "is_active": False,
                "closed_at": now_iso
            }).in_("job_code", batch).execute()
        closed_applied = len(closed_list)
        print(f"{closed_applied} зарыг идэвхгүй болголоо ({ratio:.1%}).")
else:
    print(f"Scan дутуу ({len(failed_pages)} хуудас) — closure update алгасав.")

# ══ 8. scan_runs-д нэг мөр бичнэ ══
supabase.table("scan_runs").insert({
    "started_at": now_iso,
    "finished_at": datetime.now(timezone.utc).isoformat(),
    "pages_scanned": pages_scanned,
    "failed_pages": len(failed_pages),
    "seen_count": len(seen_items),
    "new_count": len(new_codes),
    "closed_count": closed_applied,
    "reopened_count": len(reopened),
    "scan_completed": scan_completed
}).execute()

print("Өдрийн scan дууслаа.")