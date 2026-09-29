import argparse
import importlib
import time
from datetime import datetime, timezone

from common import db, scan_log
from common.http import polite_sleep
from common.config import CLOSE_RATIO_LIMIT, CLOSE_MIN_ABS

MODULES = {
    "zangia": "zangia",
    "worki": "worki",
    "lambda": "lambda_",
}

def run(name):
    source = importlib.import_module(f"sources.{MODULES[name]}")

    started_at = datetime.now(timezone.utc)
    now_iso = started_at.isoformat()

    # ══ 1. DB-ээс тухайн source-ийн мэдэгдэж буй зарууд ══
    db_codes = db.load_codes(name)
    active_in_db = {c for c, a in db_codes.items() if a}
    inactive_in_db = {c for c, a in db_codes.items() if not a}
    print(f"DB [{name}]: нийт {len(db_codes)} | идэвхтэй {len(active_in_db)} "
          f"| идэвхгүй {len(inactive_in_db)}")

    # ══ 2. Эх сурвалжаас жагсаалт ══
    seen_items, stats = source.list_items()

    # ══ 3. Set үйлдлээр 3 бүлэг ══
    today_codes = set(seen_items)
    new_codes = today_codes - db_codes.keys()
    newly_closed = active_in_db - today_codes
    reopened = today_codes & inactive_in_db

    print(f"Шинэ: {len(new_codes)} | Хаагдсан: {len(newly_closed)} "
          f"| Дахин нээгдсэн: {len(reopened)}")

    # ══ 4. ШИНЭ зар — detail татаж бичнэ ══
    inserted = 0
    detail_failed = []

    for idx, code in enumerate(sorted(new_codes), 1):
        item = seen_items[code]
        detail = source.fetch_detail(code)

        # detail татагдаагүй бол огт бичихгүй — маргааш дахин "шинэ" болж оролдоно
        if detail is None:
            detail_failed.append(code)
            print(f"\n[{code}] detail татагдсангүй — маргааш дахин оролдоно.")
            polite_sleep()
            continue

        db.upsert_job(name, code, item, detail, source.posted_at(item, detail))
        inserted += 1
        print(f"\r  Шинэ зар: [{idx}/{len(new_codes)}]", end="", flush=True)
        polite_sleep()

    if detail_failed:
        print(f"\n{len(detail_failed)} зарын detail татагдаагүй тул бичигдсэнгүй.")

    # ══ 5. ДАХИН НЭЭГДСЭН зар ══
    if reopened:
        db.mark_reopened(name, reopened)
        print(f"\n{len(reopened)} зар дахин нээгдлээ.")

    # ══ 6. ХААГДСАН зар — зөвхөн бүрэн scan + sanity check давбал ══
    closed_applied = 0
    if stats["scan_completed"]:
        ratio = len(newly_closed) / max(len(active_in_db), 1)
        if ratio > CLOSE_RATIO_LIMIT and len(newly_closed) > CLOSE_MIN_ABS:
            print(f"⚠ АНХААР: {len(newly_closed)} зар ({ratio:.1%}) хаагдсан гэж "
                  f"гарлаа — хэт их тул update хийсэнгүй.")
        else:
            closed_applied = db.mark_closed(name, newly_closed, now_iso)
            print(f"{closed_applied} зарыг идэвхгүй болголоо ({ratio:.1%}).")
    else:
        print("Scan дутуу — closure update алгасав.")

    # ══ 7. scan_runs ══
    stats.update({
        "new_count": inserted,
        "closed_count": closed_applied,
        "reopened_count": len(reopened),
    })
    scan_log.record(name, now_iso, datetime.now(timezone.utc).isoformat(), stats)

        # ══ 7. scan_runs ══
    stats.update({
        "new_count": inserted,
        "closed_count": closed_applied,
        "reopened_count": len(reopened),
    })
    scan_log.record(name, now_iso, datetime.now(timezone.utc).isoformat(), stats)

    # ══ 8. jobs_unified шинэчлэх ══
    db.refresh_jobs_unified()
    print("jobs_unified шинэчлэгдлээ.")

    print(f"[{name}] scan дууслаа.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=list(MODULES))
    run(parser.parse_args().source)

