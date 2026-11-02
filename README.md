# ZunCrawler

Монголын ажлын зарын гурван сайтаас (Zangia, Worki, Lambda) зар өдөр бүр татаж, Supabase Postgres-д хадгалдаг. Одоогоор GitHub Actions cron дээр ажиллаж байгаа.

Энд байгаа тоо бүгд **2026-11-02** өдрийн DB болон GitHub Actions түүхээс авсан утга.

## Анхаарах зүйл

1. **Transform логик энэ repo-д байхгүй.** `refresh_jobs_unified` ба `refresh_jobs_clean` нь зөвхөн Supabase дээр амьдардаг SQL функц. Table-ийн DDL ч мөн адил. Хувилбарын хяналтгүй, эдгээрийг нөөцлөх механизм repo-д алга. [Эхлээд экспортлох хэрэгтэй](#шилжүүлэх-алхам).

## Архитектур

```
 zangia.mn (REST)  ─┐
 worki.mn (GraphQL) ─┼─> sources/*.py ─> common/pii.py ─> raw_jobs
 lambda.global (HTML)┘                                      │
                                                            │ rpc refresh_jobs_unified()
                                                            ▼
                     scan_runs (run бүрийн лог)         jobs_unified
                                                            │ rpc refresh_jobs_clean()
                                                            ▼
                                                        jobs_clean
```

```
run.py                 Orchestration: diff, бичилт, sanity check, refresh
sources/
  zangia.py            REST JSON
  worki.py             GraphQL
  lambda_.py           Next.js flight payload-оос JSON сугалдаг (HTML parse)
common/
  config.py            Supabase client
  db.py                raw_jobs бичилт
  http.py              retry-тэй GET/POST
  pii.py               Source бүрийн drop / mask дүрэм
  scan_log.py          scan_runs бичилт
archive/               Хуучирсан script-үүд. Ашиглахгүй.
.github/workflows/     Одоогийн scheduler
```

Source бүр гурван функцтэй модуль байна:

| Функц                     | Буцаах утга                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `list_items()`            | `({job_code: list_payload}, stats)`. `stats`-д `pages_scanned`, `failed_pages`, `seen_count`, `scan_completed` орно |
| `fetch_detail(code)`      | PII цэвэрлэсэн `dict`, амжилтгүй бол `None`                                                                         |
| `posted_at(item, detail)` | ISO-8601 UTC string эсвэл `None`                                                                                    |

Шинэ source нэмэхэд: `sources/`-д модуль бичээд, `run.py`-ийн `MODULES` болон `common/pii.py`-ийн `RULES`-д нэмж, workflow-д бүртгэнэ. SQL функцэд нь нэмэх mapping хэрэгтэй байх магадлалтай.

Supabase-тай холбоотой код зөвхөн `common/config.py`, `common/db.py`, `common/scan_log.py`-д байгаа. Өөр Postgres руу шилжвэл Python талд эдгээрийг л солино.

## Нэг run-ий урсгал

`python run.py --source <zangia|worki|lambda>`

1. `raw_jobs`-ээс тухайн source-ийн бүх `job_code`, `is_active`-г уншина. Уншсан тоо DB-ийн `count`-той таарахгүй бол `RuntimeError`.
2. `list_items()`-р сайтын одоогийн жагсаалтыг бүтнээр нь авна.
3. Set үйлдлээр гурван бүлэг гаргана:
   - шинэ: `today - db`
   - хаагдсан: `active_in_db - today`
   - дахин нээгдсэн: `today ∩ inactive_in_db`
4. **Шинэ** зар бүрийн detail татаж upsert хийнэ (`on_conflict = source,job_code`). Detail татагдаагүй бол бичихгүй, дараагийн run-д дахин "шинэ" болно.
5. **Дахин нээгдсэн**: `is_active = true`, `closed_at = null`, `reopen_count + 1`.
6. **Хаагдсан**: дараах хоёр хамгаалалтыг давбал `is_active = false`, `closed_at = run-ий эхэлсэн цаг`.
7. `scan_runs`-д мөр нэмнэ.
8. `refresh_jobs_unified()`, дараа нь `refresh_jobs_clean()` дуудна. Хоёулаа бүрэн refresh, тухайн source-оор хязгаарлагдахгүй.

### Closure хамгаалалт

Scan тасалдсанаас болж идэвхтэй зарууд олноор нь хаагдахаас сэргийлдэг.

| Хамгаалалт   | Нөхцөл                                                                      | Утга     |
| ------------ | --------------------------------------------------------------------------- | -------- |
| Бүрэн scan   | Амжилтгүй хуудас 0, мөн хамралт ≥ `MIN_COVERAGE`                            | 0.90     |
| Sanity check | Хаагдах хувь > `CLOSE_RATIO_LIMIT` **ба** тоо > `CLOSE_MIN_ABS` бол алгасна | 0.20, 25 |

Lambda-д нийт зарын тоо API-аас ирдэггүй тул хамралт шалгахгүй. Дараалсан 2 хуудсанд шинэ slug гарахгүй бол scan бүрэн гэж үзнэ.

## Эх сурвалжууд

|                       | Zangia                              | Worki                      | Lambda                 |
| --------------------- | ----------------------------------- | -------------------------- | ---------------------- |
| Endpoint              | `new-api.zangia.mn/api/jobs/search` | `graphql.worki.mn/graphql` | `lambda.global/jobs`   |
| Төрөл                 | REST                                | GraphQL                    | HTML (Next.js flight)  |
| `job_code`            | `code`                              | `id`                       | URL slug               |
| `posted_at`           | `time` (unix)                       | `createdAt` (УБ цаг → UTC) | detail-ийн `createdAt` |
| Хуудасны дээд хязгаар | 400 × 90                            | 50 × 100                   | 60                     |
| Нийт мөр              | 26,256                              | 226                        | 1,630                  |
| Идэвхтэй              | 6,695                               | 128                        | 567                    |
| Scan-ий хугацаа\*     | 5–16 мин                            | 5–23 сек                   | 1–2.5 мин              |

\* Сүүлийн 4 өдрийн `scan_runs` (`refresh` ороогүй). Zangia-д өдөрт 50–410 шинэ зар гардаг бөгөөд хугацаа үндсэндээ үүнээс хамаарна.

## Өгөгдлийн давхарга

| Table          | Зорилго                                           | Мөр    |
| -------------- | ------------------------------------------------- | ------ |
| `raw_jobs`     | Эх payload (JSONB), lifecycle төлөв               | 28,112 |
| `jobs_unified` | Source-уудыг нэг бүтэцтэй болгосон                | 28,112 |
| `jobs_clean`   | Normalize + dedup. Хэрэглэгчид зориулсан давхарга | 28,112 |
| `scan_runs`    | Run бүрийн статистик                              | 190    |

### Өгөгдөл ашиглахдаа анхаарах

- **Payload нь анх харагдсан үеийн snapshot.** Upsert зөвхөн шинэ зар дээр ажилладаг, дахин нээгдсэн зарыг ч дахин татдаггүй. Иймээс цалин, тайлбар зэрэг нь хожмын өөрчлөлтийг тусгахгүй, `view_count`, `apply_count` нь анхны scan-ий утга хэвээр.
- **Dedup зөвхөн идэвхтэй Zangia зар дээр ажиллаж байгаа.**

## Scheduler (одоогийн)

| Workflow             | Cron (UTC)   | Төлөвлөсөн УБ цаг |
| -------------------- | ------------ | ----------------- |
| `daily-zangia`       | `17 2 * * *` | 10:17             |
| `daily-worki-lambda` | `0 7 * * *`  | 15:00             |

Workflow-ууд `_scan.yml`-ийг дууддаг: Python 3.12, `timeout-minutes: 350`, source тус бүрд `concurrency` group. Worki ба Lambda нь matrix-аар зэрэг ажилладаг тул refresh функцүүд зэрэг дуудагдана.

## Тохиргоо ба локал ажиллуулах

| Хувьсагч       | Тайлбар              |
| -------------- | -------------------- |
| `SUPABASE_URL` | Project URL          |
| `SUPABASE_KEY` | Одоо `service_role`. |

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env файлд дээрх хоёр хувьсагчийг бичнэ
python run.py --source worki    # Хамгийн хурдан. Анхаар: заасан DB руу шууд бичнэ
```

## ETL орчинд тавигдах шаардлага

Scheduler-ээс үл хамаарах гэрээ:

| Зүйл        | Шаардлага                                                                                                                   |
| ----------- | --------------------------------------------------------------------------------------------------------------------------- |
| Команд      | `python run.py --source <name>`, source тус бүр тусдаа task                                                                 |
| Runtime     | Python 3.12, `requirements.txt`                                                                                             |
| Сүлжээ      | Гарах HTTPS: `new-api.zangia.mn`, `graphql.worki.mn`, `lambda.global`, Supabase                                             |
| Давтамж     | Source тус бүр өдөрт 1 удаа. Цагийн хувьд доорх Zangia тэмдэглэлийг харна                                                   |
| Timeout     | Өдөр тутам 60 мин (ажиглагдсан хамгийн урт CI run нь 22 мин орчим). Хоосон DB эсвэл шинэ зар их бол цагаар хэмжигдэнэ       |
| Concurrency | **Нэг source зэрэг хоёр удаа ажиллаж болохгүй.** Хамгаалалт DB эсвэл кодод байхгүй, зөвхөн workflow-ийн `concurrency`-д бий |
| Retry       | Аюулгүй. Шинэ зар нь upsert, `reopen_count` дахин нэмэгдэхгүй. Давтан бүрд `scan_runs`-д мөр нэмэгдэнэ                      |
| Тасралт     | Run бүр atomic биш. Тасарвал бичигдсэн мөр үлдэж, дараагийн run үргэлжлүүлнэ                                                |

## Шилжүүлэх алхам

1. **Schema ба SQL функцийг экспортлож repo-д нэмэх.** Supabase-ийн database connection string хэрэгтэй:
   ```bash
   mkdir -p db
   pg_dump "$SUPABASE_DB_URL" --schema-only --schema=public --no-owner > db/schema.sql
   ```
2. ETL-д зориулж `raw_jobs`, `scan_runs` бичих, хоёр RPC дуудах эрхтэй тусдаа түлхүүр эсвэл role гаргах.
