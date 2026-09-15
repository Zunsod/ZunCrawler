import json
import random
import time
from pathlib import Path
import requests

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)
output_file = RAW_DIR / "zangia_jobs_selected.json"

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

# Duplicate fetching сэргийлэх
if output_file.exists():
    with open(output_file, "r", encoding="utf-8") as f:
        try:
            final_jobs_dataset = json.load(f)
            print(f"Өмнө нь татсан {len(final_jobs_dataset)} зар олдлоо. Түүн дээр нэмж хадгална.")
        except Exception:
            final_jobs_dataset = []
else:
    final_jobs_dataset = []

# Нийт 1000 датагаа 11 batch болгон таслав
total_batches = 11

for batch_num in range(1, total_batches + 1):
    print(f"▶ BATCH {batch_num}/{total_batches} ЭХЭЛЛЭЭ (Хуудас: {batch_num})")
    params = {
        "limit": 90,
        "page": batch_num,
        "isSortByJobs": "true",
        "time": 1
    }

    try:
        res = session.get(SEARCH_API, params=params, timeout=15)
        if res.status_code != 200:
            print(f"[Алдаа] Batch {batch_num} жагсаалт амжилтгүй: HTTP {res.status_code}")
            break

        items = res.json().get("items", [])
        if not items:
            print("Бүх ажлын зарын жагсаалт дууслаа.")
            break

        print(f"Энэ batch-д нийт {len(items)} зар байна. Fetch хийж байна...")

        # Тухайн batch-н заруудыг нэг нэгээр нь гүйх
        for idx, item in enumerate(items, 1):
            job_code = item.get("code")
            if not job_code:
                continue

            job_record = {
                "job_id": item.get("id"),
                "job_code": job_code,
                "company_id": item.get("company_id"),
                "company_name": item.get("company_name"),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "salary_phrase": item.get("salary_phrase"),
                "address": item.get("address"),
                "job_title": None,
                "profession": None,
                "branch": None,
                "branch_id": None,
                "job_level": None,
                "timetype": None,
                "timetype_id": None
            }

            # APIруу хандах
            try:
                detail_url = f"{DETAIL_API_BASE}{job_code}"
                detail_res = session.get(detail_url, timeout=10)

                if detail_res.status_code == 200:
                    d = detail_res.json()
                    job_record["job_title"] = d.get("title")
                    job_record["profession"] = d.get("profession")
                    job_record["branch"] = d.get("branch")
                    job_record["branch_id"] = d.get("branch_id")
                    job_record["job_level"] = d.get("job_level")
                    job_record["timetype"] = d.get("timetype")
                    job_record["timetype_id"] = d.get("timetype_id")

                elif detail_res.status_code == 429:
                    print("\n[Rate Limit] Сервер түр хязгаарлалаа. 30 завсарлах...")
                    time.sleep(30)

            except Exception as e:
                print(f"\n[{job_code}] Алдаа: {e}")

            final_jobs_dataset.append(job_record)
            
            print(f"\r  Явц: [{idx}/{len(items)}] | Нийт цугласан: {len(final_jobs_dataset)} зар", end="", flush=True)

            # fetch завсарлах
            time.sleep(random.uniform(1.0, 1.6))

        # Batch бүрийн дараа файлыг шууд шинэчлэн хадгалах (Checkpoint)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_jobs_dataset, f, ensure_ascii=False, indent=2)

        print(f"\n✔ Batch {batch_num} амжилттай дуусаж, файлд хадгалагдлаа.")
        time.sleep(3)

    except Exception as e:
        print(f"\nСүлжээний алдаа гарлаа: {e}")
        break

print(f"Ажил бүрэн дууслаа. Нийт хадгалагдсан зар: {len(final_jobs_dataset)}")
