# Database

Supabase Postgres 17-ийн бүтцийн тайлбар. Мөрийн тоо нь 2026-11-02-ны утга.

Файлууд нь DB-ийн snapshot. Эх үнэн нь Supabase, migration байхгүй.

| Файл                 | Агуулга                                          |
| -------------------- | ------------------------------------------------ |
| `schema.sql`         | Table, view, SQL функц (`public`, `marts`)       |
| `reference_data.sql` | `map_*`, `dim_date`, `dim_location`-ийн өгөгдөл  |

## Өгөгдлийн урсгал

```
run.py ──> raw_jobs            scan_runs <── run.py
              │
              │ refresh_jobs_unified()
              ▼
          jobs_unified
              │
              │ refresh_jobs_clean()  <── map_*, dim_location
              ▼
          jobs_clean
              │
              │ view (WHERE is_original)
              ▼
    fact_jobs, bridge_job_skill, dim_*, dash_*
              │
              │ refresh_export()  (гараар)
              ▼
          export.*
```

## Үндсэн table

| Table          | Мөр    | Үүрэг                                                                       | Хэн бичдэг                         | Түлхүүр                              |
| -------------- | ------ | --------------------------------------------------------------------------- | ---------------------------------- | ------------------------------------ |
| `raw_jobs`     | 28,112 | Эх payload (JSONB) ба зарын төлөв: `is_active`, `closed_at`, `reopen_count` | `run.py`                           | PK `id`, UNIQUE `(source, job_code)` |
| `jobs_unified` | 28,112 | Гурван source-ийн JSON-ийг нэг баганат бүтэцтэй болгосон                    | `refresh_jobs_unified()`, upsert   | PK `id`                              |
| `jobs_clean`   | 28,112 | Стандарт ангилал, байршил, цалингийн төлөв, dedup нэмсэн                    | `refresh_jobs_clean()`, `TRUNCATE` + insert | PK `id`                     |
| `scan_runs`    | 190    | Run бүрийн статистик: хуудас, шинэ, хаагдсан, `scan_completed`              | `run.py`                           | PK `id`                              |

`raw_jobs`, `jobs_unified`, `jobs_clean`-ийн `id` нь ижил утга боловч хооронд нь FK байхгүй.

### Source-уудын ялгаа (`jobs_unified`)

| Багана                     | Zangia  | Worki          | Lambda                           |
| -------------------------- | ------- | -------------- | -------------------------------- |
| `company_name`             | бий     | бий            | `recruiter`-ээс авна             |
| `experience_years`         | `NULL`  | бий            | бий                              |
| `deadline`                 | `NULL`  | `expiryDate`   | `deadline`                       |
| `view_count`, `apply_count` | бий    | `NULL`         | бий                              |
| `category_name`            | бий     | `NULL`         | `NULL`                           |
| `requirements_html`        | бий     | бий            | `NULL`                           |

### `jobs_clean`-д нэмэгддэг утгууд

- **`salary_status`**: `no_salary` (цалингүй), `non_monthly` (цагийн ажил эсвэл дундаж < 500,000₮), `monthly_outlier` (> 15,000,000₮), `monthly` (бусад).
- **`salary_min`, `salary_max`**: `0` нь `NULL` болно. `salary_avg` нь хоёрын дундаж, нэг нь л байвал тэр утга.
- **`is_original`, `dup_count`**: зөвхөн идэвхтэй Zangia зарт бодогдоно, бусад нь `NULL`. Компани, нормчилсон гарчиг, байршил, нормчилсон тайлбар нь ижил бол давхардал гэж үзэж, хамгийн эрт нийтлэгдсэнийг `true` болгоно.
- **`active_days`**: `posted_at`-аас `closed_at` (хаагдаагүй бол refresh хийсэн өдөр) хүртэлх календарийн өдөр, УБ цагаар.

## Шинжилгээний view

`fact_jobs`, `bridge_job_skill`, `dim_salary_band`, бүх `dash_*` нь **зөвхөн идэвхтэй, давхардаагүй Zangia зарыг** хамарна (6,577 зар). Бусад `dim_*` нь лавлах утгууд тул энэ шүүлтүүрт орохгүй.

| View                     | Үүрэг                                                                      |
| ------------------------ | -------------------------------------------------------------------------- |
| `fact_jobs`              | Гол fact. `salary_monthly`, `is_entry_level`, `is_new_7d` нэмдэг           |
| `bridge_job_skill`       | Зар ↔ ур чадварын холбоос                                                  |
| `dim_category`           | Ангилал ба бүлэг                                                           |
| `dim_job_level`          | Түвшин, эрэмбэ                                                             |
| `dim_employment_type`    | Ажлын төрөл                                                                |
| `dim_location_flat`      | `dim_location`-ийг хавтгайлсан: бүс, дүүрэг, `is_ub`                       |
| `dim_salary_band`        | `salary_avg` → цалингийн завсар (сая ₮)                                    |
| `dim_skill`              | Ур чадварын нэг нэр, төрөл. `jobs_clean`-ийн бүх мөрөөс бүтнэ              |
| `dash_sector_overview`   | Салбарын бүлгээр зарын тоо, цалингийн завсар, медиан                       |
| `dash_profession_salary` | Мэргэжлээр цалин. Хамгийн олон зартай 10 (≥ 30 зар)                        |
| `dash_level_share`       | Салбарын бүлэг доторх түвшний эзлэх хувь                                   |
| `dash_sector_skills`     | Салбар бүрийн топ 10 hard skill                                            |
| `dash_top_skills`        | Hard skill-үүдийн нийт тоо, хувь                                           |

`dash_*`-ийн `*_label` баганууд дахь `chr(8203)` (zero-width space) нь эрэмбэлэх зорилготой.

## Функц

| Функц                                       | Үүрэг                                                                     |
| ------------------------------------------- | ------------------------------------------------------------------------- |
| `refresh_jobs_unified()`                    | `raw_jobs` → `jobs_unified`. `run.py` дууддаг                             |
| `refresh_jobs_clean()`                      | `jobs_unified` → `jobs_clean`. `run.py` дууддаг                           |
| `refresh_export()`                          | `export` schema-г устгаад view-үүдээс table болгож дахин үүсгэнэ. Гараар  |
| `norm_title()`, `norm_desc()`               | Dedup-ийн гарчиг, тайлбарын нормчлол                                      |
| `norm_company()`                            | Компанийн нэрийн нормчлол. `stg_jobs` ашигладаг                           |
| `jarr()`                                    | JSONB массив биш бол `[]` буцаана                                         |
| `company_key()`                             | Өөр объект дууддаггүй                                                     |

## Бусад schema ба объект

| Объект                         | Төлөв                                                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `export.*`                     | `fact_jobs`, `bridge_job_skill`, `dim_*`, `dash_level_share`-ийн table хуулбар. Сүүлд 2026-10-11-нд шинэчлэгдсэн |
| `stg_jobs`, `mart_active_jobs` | Refresh функц, `fact_jobs`-д ашиглагддаггүй. `jobs_clean`-ээс өмнөх зам байж магадгүй                 |
| `marts`                        | Хоосон schema                                                                                         |
| `raw_jobs.last_seen_at`        | Шинэчлэгддэггүй, найдаж болохгүй                                                                      |
