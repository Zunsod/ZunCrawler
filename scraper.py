import os
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

BATCHES_PER_RUN = 2   

# ── 1. Явцаа DB-ээс уншина ──
progress = supabase.table("scrape_progress").select("*").eq("id", 1).execute().data[0]

if progress["status"] == "done":
    print("Backfill аль хэдийн бүрэн дууссан. Зогсож байна.")
    exit()

start_page = progress["last_completed_page"] + 1
end_page = start_page + BATCHES_PER_RUN - 1
print(f"Энэ ажиллагаа {start_page}-с {end_page} хуудас хүртэл үргэлжилнэ.")

scrape_started_at = datetime.now(timezone.utc)
reached_end = False

for batch_num in range(start_page, end_page + 1):
    print(f"▶ BATCH {batch_num}")
    params = {"limit": 90, "page": batch_num, "isSortByJobs": "true", "time": 1}

    try:
        res = session.get(SEARCH_API, params=params, timeout=15)
        if res.status_code != 200:
            print(f"[Алдаа] HTTP {res.status_code}")
            break

        items = res.json().get("items", [])
        if not items:
            print("Бүх хуудас дууслаа — жагсаалт хоосон ирлээ.")
            reached_end = True
            break

        for idx, item in enumerate(items, 1):
            job_code = item.get("code")
            if not job_code:
                continue

            detail_payload = None
            for attempt in range(3):
                try:
                    detail_res = session.get(f"{DETAIL_API_BASE}{job_code}", timeout=20)
                    if detail_res.status_code == 200:
                        detail_payload = detail_res.json()
                        detail_payload.pop("similarJobs", None)
                        break
                    elif detail_res.status_code == 429:
                        print("\n[Rate Limit] 30 сек хүлээж байна...")
                        time.sleep(30)
                    else:
                        print(f"\n[{job_code}] HTTP {detail_res.status_code}, дахин оролдоно...")
                        time.sleep(3)
                except Exception as e:
                    print(f"\n[{job_code}] Оролдлого {attempt+1}/3 амжилтгүй: {e}")
                    time.sleep(5)

            posted_at = None
            if item.get("time"):
                posted_at = datetime.fromtimestamp(item["time"], tz=timezone.utc).isoformat()

            now_iso = datetime.now(timezone.utc).isoformat()

            supabase.table("raw_jobs").upsert({
                "job_code": job_code,
                "list_payload": item,
                "detail_payload": detail_payload,
                "posted_at": posted_at,
                "last_seen_at": now_iso,
                "is_active": True
            }, on_conflict="job_code").execute()

            print(f"\r  Явц: [{idx}/{len(items)}] batch {batch_num}", end="", flush=True)
            time.sleep(random.uniform(1.0, 1.6))

        # ── 2. Batch бүр амжилттай дуусах болгонд cursor-оо шууд DB-рүү бичнэ ──
        supabase.table("scrape_progress").update({
            "last_completed_page": batch_num,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", 1).execute()

        print(f"\n✔ Batch {batch_num} дууслаа, cursor хадгалагдлаа.")
        time.sleep(3)

    except Exception as e:
        print(f"\nСүлжээний алдаа: {e}")
        break

# ── 3. Зөвхөн бүх дата дуусахад хүрсэн үед л idle-tagging хийнэ ──
if reached_end:
    supabase.table("scrape_progress").update({"status": "done"}).eq("id", 1).execute()

    supabase.table("raw_jobs") \
        .update({"is_active": False}) \
        .lt("last_seen_at", scrape_started_at.isoformat()) \
        .execute()

    print("Backfill бүрэн дууслаа, идэвхгүй зарыг тэмдэглэлээ.")
else:
    print("Энэ ажиллагаа дуусгалаа — дараагийн ажиллагаанд үргэлжилнэ.")