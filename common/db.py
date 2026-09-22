from common.config import supabase, CHUNK


def load_codes(source):
    """Тухайн source-ийн бүх job_code → is_active.

    .order("id") заавал байх ёстой: эрэмбэгүй .range() хуудаслалт нь
    хуудас хооронд мөр давхардуулж / алгасч болдог тул зарим код
    уншигдахгүй өнгөрч, "шинэ зар" гэж буруу тооцогддог.
    """
    codes = {}
    offset = 0
    while True:
        rows = (supabase.table("raw_jobs")
                .select("job_code, is_active")
                .eq("source", source)
                .order("id")
                .range(offset, offset + 999)
                .execute().data)
        if not rows:
            break
        for r in rows:
            codes[r["job_code"]] = r["is_active"]
        offset += 1000

    # Хамгаалалт: уншсан тоо DB-ийн бодит тоотой таарах ёстой
    total = (supabase.table("raw_jobs")
             .select("id", count="exact")
             .eq("source", source)
             .limit(1)
             .execute().count)
    if len(codes) != total:
        raise RuntimeError(
            f"load_codes [{source}]: {len(codes)} код уншсан, DB-д {total} мөр байна")
    return codes


def upsert_job(source, code, list_payload, detail_payload, posted_at):
    supabase.table("raw_jobs").upsert({
        "source": source,
        "job_code": code,
        "list_payload": list_payload,
        "detail_payload": detail_payload,
        "posted_at": posted_at,
        "is_active": True,
    }, on_conflict="source,job_code").execute()


def mark_reopened(source, codes):
    codes = list(codes)
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        rows = (supabase.table("raw_jobs")
                .select("job_code, reopen_count")
                .eq("source", source)
                .in_("job_code", batch)
                .execute().data)
        for r in rows:
            supabase.table("raw_jobs").update({
                "is_active": True,
                "closed_at": None,
                "reopen_count": (r.get("reopen_count") or 0) + 1,
            }).eq("source", source).eq("job_code", r["job_code"]).execute()
    return len(codes)


def mark_closed(source, codes, closed_at):
    codes = list(codes)
    for i in range(0, len(codes), CHUNK):
        batch = codes[i:i + CHUNK]
        supabase.table("raw_jobs").update({
            "is_active": False,
            "closed_at": closed_at,
        }).eq("source", source).in_("job_code", batch).execute()
    return len(codes)


def refresh_jobs_unified():
    """raw_jobs-оос jobs_unified-ийг шинэчилнэ (Supabase дээрх SQL функц)."""
    supabase.rpc("refresh_jobs_unified").execute()