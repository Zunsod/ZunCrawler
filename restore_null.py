import os
import time
from datetime import datetime, timezone
import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

DETAIL_API_BASE = "https://new-api.zangia.mn/api/jobs/_"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:153.0) Gecko/20100101 Firefox/153.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.zangia.mn",
    "Referer": "https://www.zangia.mn/"
}

session = requests.Session()
session.headers.update(HEADERS)

# detail_payload дутуу job_code-уудыг DB-ээс шууд татаж авна
missing = supabase.table("raw_jobs").select("job_code").filter("detail_payload", "is", "null").execute()
job_codes = [row["job_code"] for row in missing.data]
print(f"Нөхөх ёстой зарын тоо: {len(job_codes)}")

for job_code in job_codes:
    detail_payload = None
    for attempt in range(3):
        try:
            detail_res = session.get(f"{DETAIL_API_BASE}{job_code}", timeout=20)
            if detail_res.status_code == 200:
                detail_payload = detail_res.json()
                detail_payload.pop("similarJobs", None)
                break
            elif detail_res.status_code == 429:
                print(f"[{job_code}] Rate limit, 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                print(f"[{job_code}] HTTP {detail_res.status_code}, дахин оролдоно...")
                time.sleep(3)
        except Exception as e:
            print(f"[{job_code}] Оролдлого {attempt+1}/3 амжилтгүй: {e}")
            time.sleep(5)

    if detail_payload is None:
        print(f"[{job_code}] 3 оролдлогын дараа ч амжилтгүй — алгасав.")
        continue

    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("raw_jobs").update({
        "detail_payload": detail_payload,
        "last_seen_at": now_iso
    }).eq("job_code", job_code).execute()

    print(f"[{job_code}] Амжилттай шинэчлэгдлээ.")
    time.sleep(1.5)

print("Нөхөх ажил дууслаа.")