--
-- PostgreSQL database dump
--

\restrict R2U8giTWRytbHjFCLTkpBmprhBI3WAjvWaWNDvFVam8vp8lbnGVGU7gDOb7BD0b

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: marts; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA marts;


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: company_key(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.company_key(name text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $_$
  SELECT nullif(
    regexp_replace(
      regexp_replace(
        -- & → энд, латин ижил хэлбэртэй үсэг → кирилл, э/ё → е
        translate(lower(replace(name, '&', 'энд')),
                  'aceopxykmthbэё', 'асеорхукмтнвее'),
        '[^а-яөү0-9a-z]', '', 'g'),     -- үсэг/тооноос бусдыг хасах
      '(ххк|хк|ббсб|төхк)+$', ''),      -- хуулийн хэлбэрийн дагавар
    '')
$_$;


--
-- Name: jarr(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.jarr(j jsonb) RETURNS jsonb
    LANGUAGE sql IMMUTABLE
    AS $$
  select case when jsonb_typeof(j) = 'array' then j else '[]'::jsonb end
$$;


--
-- Name: norm_company(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.norm_company(t text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  select nullif(trim(regexp_replace(
    regexp_replace(
      ' ' || regexp_replace(
               lower(case when t ~ '[А-Яа-яӨөҮүЁё]'
                          then translate(t, 'ABCEHKMOPTXYaceopxy', 'АВСЕНКМОРТХУасеорху')
                          else t end),
               '[[:punct:]«»“”„"]', ' ', 'g') || ' ',
      '\s(хувьцаат компани|ххк|хк|ббсб|xxk|llc|ltd|inc|co)(?=\s)', ' ', 'g'),
    '\s+', ' ', 'g')), '')
$$;


--
-- Name: norm_desc(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.norm_desc(t text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  select nullif(trim(regexp_replace(
    regexp_replace(lower(t), '<[^>]+>|&[a-z]+;|&#\d+;', ' ', 'g'),
    '[^0-9a-zа-яёөү]+', ' ', 'g')), '')
$$;


--
-- Name: norm_title(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.norm_title(t text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  select nullif(trim(regexp_replace(
    regexp_replace(
      lower(case when t ~ '[А-Яа-яӨөҮүЁё]'
                 then translate(t, 'ABCEHKMOPTXYaceopxy', 'АВСЕНКМОРТХУасеорху')
                 else t end),
      '[[:punct:]«»“”„"]', ' ', 'g'),
    '\s+', ' ', 'g')), '')
$$;


--
-- Name: refresh_export(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_export() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  DROP SCHEMA IF EXISTS export CASCADE;
  CREATE SCHEMA export;

  CREATE TABLE export.fact_jobs           AS SELECT * FROM public.fact_jobs;
  CREATE TABLE export.bridge_job_skill    AS SELECT * FROM public.bridge_job_skill;
  CREATE TABLE export.dim_date            AS SELECT * FROM public.dim_date;
  CREATE TABLE export.dim_location        AS SELECT * FROM public.dim_location;
  CREATE TABLE export.dim_location_flat   AS SELECT * FROM public.dim_location_flat;
  CREATE TABLE export.dim_category        AS SELECT * FROM public.dim_category;
  CREATE TABLE export.dim_employment_type AS SELECT * FROM public.dim_employment_type;
  CREATE TABLE export.dim_job_level       AS SELECT * FROM public.dim_job_level;
  CREATE TABLE export.dim_salary_band     AS SELECT * FROM public.dim_salary_band;
  CREATE TABLE export.dim_skill           AS SELECT * FROM public.dim_skill;
  CREATE TABLE export.dash_level_share    AS SELECT * FROM public.dash_level_share;
END $$;


--
-- Name: refresh_jobs_clean(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_jobs_clean() RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  truncate public.jobs_clean;

  insert into public.jobs_clean (
    id, source, job_code, source_job_id, title, company_name,
    location_id, region_mn, district_mn, location_level,
    category, job_level, job_level_rank, employment_type,
    salary_min, salary_max, salary_avg, salary_status,
    experience_years, skills, benefits,
    posted_at, deadline, first_seen_at, closed_at,
    is_active, active_days, view_count, apply_count,
    dup_count, is_original, loaded_at
  )
  with base as (
    select
      j.id,
      j.source,
      j.job_code,
      j.source_job_id,
      j.title,
      j.company_name,
      -- Байршил
      d.location_id,
      coalesce(p.name_mn, d.name_mn)                      as region_mn,
      case when d.level = 'district' then d.name_mn end   as district_mn,
      d.level                                             as location_level,
      -- Стандартчилсан ангилал (map-д байхгүй бол 'Бусад')
      coalesce(mc.category, 'Бусад')                      as category,
      coalesce(jl.job_level, 'Бусад')                     as job_level,
      jl.level_rank                                       as job_level_rank,
      coalesce(e.employment_type, 'Бусад')                as employment_type,
      -- Цалин (0 → NULL)
      nullif(j.salary_min, 0)                             as salary_min,
      nullif(j.salary_max, 0)                             as salary_max,
      j.experience_years,
      j.skills,
      j.benefits,
      j.posted_at,
      j.deadline,
      j.first_seen_at,
      j.closed_at,
      j.is_active,
      j.active_days,
      j.view_count,
      j.apply_count,
      -- Dedup-ийн хүрээ: Zangia-ийн active зарууд
      (j.source = 'zangia' and j.is_active)               as in_scope,
      case when j.source = 'zangia' and j.is_active
           then norm_title(j.title) end                   as title_norm,
      case when j.source = 'zangia' and j.is_active
           then norm_desc(j.duties_html) end              as desc_norm
    from public.jobs_unified j
    left join public.map_location m         on m.source = j.source and m.location_raw = j.location_raw
    left join public.dim_location d         on d.location_id = m.location_id
    left join public.dim_location p         on p.location_id = d.parent_id
    left join public.map_category mc        on mc.source = j.source and mc.source_category_id = j.category_id
    left join public.map_employment_type e  on e.source = j.source and e.raw_value = j.employment_type_raw
    left join public.map_job_level jl       on jl.source = j.source and jl.raw_value = j.job_level_raw
  ),
  calc as (
    select b.*,
           case when b.salary_min is not null and b.salary_max is not null
                then round((b.salary_min + b.salary_max) / 2::numeric)
                else coalesce(b.salary_min, b.salary_max)
           end as salary_avg
    from base b
  ),
  ranked as (
    select c.*,
           count(*) over w as grp_count,
           row_number() over (w order by c.posted_at asc nulls last,
                                         c.first_seen_at asc,
                                         c.id asc) as grp_rn
    from calc c
    window w as (partition by c.in_scope, c.company_name, c.title_norm,
                              c.location_id, c.desc_norm)
  )
  select
    id, source, job_code, source_job_id, title, company_name,
    location_id, region_mn, district_mn, location_level,
    category, job_level, job_level_rank, employment_type,
    salary_min, salary_max, salary_avg,
    case
      when salary_avg is null                                       then 'no_salary'
      when employment_type = 'Цагийн ажил' or salary_avg < 500000   then 'non_monthly'
      when salary_avg > 15000000                                    then 'monthly_outlier'
      else 'monthly'
    end,
    experience_years, skills, benefits,
    posted_at, deadline, first_seen_at, closed_at,
    is_active, active_days, view_count, apply_count,
    case when in_scope then grp_count end,          -- хүрээнээс гадуур NULL
    case when in_scope then grp_rn = 1 end,         -- хүрээнээс гадуур NULL
    now()
  from ranked;
end;
$$;


--
-- Name: refresh_jobs_unified(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_jobs_unified() RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  -- raw_jobs-оос устгагдсан мөр байвал л jobs_unified-аас хасна (ердийн үед 0 мөр)
  delete from public.jobs_unified u
  where not exists (select 1 from public.raw_jobs r where r.id = u.id);

  -- Шинэ мөрийг нэмнэ, байгаа мөрийг шинэчилнэ (table хэзээ ч хоосрохгүй)
  insert into public.jobs_unified (
    id, source, job_code, source_job_id,
    title, company_name, salary_min, salary_max,
    employment_type_raw, job_level_raw, location_raw,
    category_id, category_name, skills, benefits,
    experience_years, deadline, view_count, apply_count,
    duties_html, requirements_html,
    posted_at, first_seen_at, is_active, closed_at,
    active_days
  )
  select
    r.id,
    r.source,
    r.job_code,
    d->>'id',

    -- Ажлын нэр
    case r.source
      when 'worki'  then d->>'name'
      when 'lambda' then d->>'title'
      when 'zangia' then d->>'title'
    end,

    -- Компани
    --   lambda: дээд түвшний "company" хоосон ирдэг тул recruiter-ээс авна.
    --   recruiter.company / companyMn-ийг recruiter бүр өөрөөр бөглөдөг
    --   ("Mn" талбарт латин, энгийн талбарт кирилл байх нь бий) тул
    --   аль нэгэнд нь кирилл байвал түүнийг, үгүй бол англи нэрийг авна.
    case r.source
      when 'worki'  then d->'company'->>'name'
      when 'lambda' then
        case
          when d->'recruiter'->>'companyMn' ~ '[А-Яа-яӨөҮүЁё]' then trim(d->'recruiter'->>'companyMn')
          when d->'recruiter'->>'company'   ~ '[А-Яа-яӨөҮүЁё]' then trim(d->'recruiter'->>'company')
          else coalesce(nullif(trim(d->'recruiter'->>'companyMn'), ''),
                        trim(d->'recruiter'->>'company'))
        end
      when 'zangia' then d->>'company_name'
    end,

    -- Цалин (₮)
    nullif(case r.source when 'zangia' then d->>'salary_min'
                         else d->'salary'->>'min' end, '')::numeric,
    nullif(case r.source when 'zangia' then d->>'salary_max'
                         else d->'salary'->>'max' end, '')::numeric,

    -- Ажлын төрөл (raw: FULL_TIME / "Бүтэн цагийн" ...)
    case r.source
      when 'worki'  then d->>'positionType'
      when 'lambda' then d->>'engagmentType'
      when 'zangia' then d->>'timetype'
    end,

    -- Түвшин (raw: MIDDLE / MID-LEVEL / "Мэргэжилтэн" ...)
    case r.source
      when 'worki'  then d->>'positionLevel'
      when 'lambda' then d->>'positionType'
      when 'zangia' then d->>'job_level'
    end,

    -- Байршил (raw)
    case r.source
      when 'worki'  then (select string_agg(v, ' / ')
                          from jsonb_array_elements_text(public.jarr(d->'addressNames')) x(v))
      when 'lambda' then d->>'location'
      when 'zangia' then d->>'address'
    end,

    -- Салбар: ID нь 3-уланд, нэр нь зөвхөн zangia-д
    case r.source
      when 'worki'  then r.list_payload->>'categoryId'
      when 'lambda' then d->>'jobCategoryId'
      when 'zangia' then d->>'branch_id'
    end,
    case r.source
      when 'zangia' then d->>'branch'
    end,

    -- Ур чадвар
    case r.source
      when 'worki' then array(select s->>'name'
                              from jsonb_array_elements(public.jarr(d->'requirement'->'skills')) x(s))
      else              array(select v
                              from jsonb_array_elements_text(public.jarr(d->'skills')) x(v))
    end,

    -- Хангамж, урамшуулал (lambda: tags дотор issuer = LAMBDA)
    case r.source
      when 'lambda' then array(select t->>'nameMn'
                               from jsonb_array_elements(public.jarr(d->'tags')) x(t)
                               where t->>'issuer' = 'LAMBDA')
      else               array(select v
                               from jsonb_array_elements_text(public.jarr(d->'benefits')) x(v))
    end,

    -- Туршлага (жил) — zangia-д байхгүй
    case r.source
      when 'worki'  then (select max(nullif(e->>'yearOfAtLeast', '')::int)
                          from jsonb_array_elements(public.jarr(d->'requirement'->'experiences')) x(e))
      when 'lambda' then nullif(d->>'experience', '')::int
    end,

    -- Зар хаагдах огноо — zangia-д байхгүй
    case r.source
      when 'worki'  then nullif(d->>'expiryDate', '')::timestamp at time zone 'Asia/Ulaanbaatar'
      when 'lambda' then nullif(d->>'deadline', '')::timestamptz
    end,

    -- Үзэлт / өргөдөл — worki-д байхгүй
    case r.source
      when 'lambda' then nullif(d->>'viewCount', '')::int
      when 'zangia' then nullif(d->>'hits', '')::int
    end,
    case r.source
      when 'lambda' then nullif(d->>'applyCount', '')::int
      when 'zangia' then nullif(d->>'applies', '')::int
    end,

    -- Тайлбар (HTML хэвээр)
    case r.source
      when 'worki'  then d->>'responsibility'   -- worki: responsibility = үүрэг
      when 'lambda' then d->>'description'
      when 'zangia' then d->>'description'
    end,
    case r.source
      when 'worki'  then d->>'description'      -- worki: description = шаардлага
      when 'zangia' then d->>'requirements'
    end,

    r.posted_at,
    r.first_seen_at,
    r.is_active,
    r.closed_at,

    -- Идэвхтэй байсан хоног (UB цагаар, календарийн өдрөөр):
    --   эхлэл = posted_at (байхгүй бол first_seen_at)
    --   төгсгөл = closed_at (хаагдаагүй бол refresh хийсэн өдөр)
    greatest(
      (coalesce(r.closed_at, now()) at time zone 'Asia/Ulaanbaatar')::date
      - (coalesce(r.posted_at, r.first_seen_at) at time zone 'Asia/Ulaanbaatar')::date,
      0
    )

  from public.raw_jobs r
  cross join lateral (select r.detail_payload as d) p

  on conflict (id) do update set
    source              = excluded.source,
    job_code            = excluded.job_code,
    source_job_id       = excluded.source_job_id,
    title               = excluded.title,
    company_name        = excluded.company_name,
    salary_min          = excluded.salary_min,
    salary_max          = excluded.salary_max,
    employment_type_raw = excluded.employment_type_raw,
    job_level_raw       = excluded.job_level_raw,
    location_raw        = excluded.location_raw,
    category_id         = excluded.category_id,
    category_name       = excluded.category_name,
    skills              = excluded.skills,
    benefits            = excluded.benefits,
    experience_years    = excluded.experience_years,
    deadline            = excluded.deadline,
    view_count          = excluded.view_count,
    apply_count         = excluded.apply_count,
    duties_html         = excluded.duties_html,
    requirements_html   = excluded.requirements_html,
    posted_at           = excluded.posted_at,
    first_seen_at       = excluded.first_seen_at,
    is_active           = excluded.is_active,
    closed_at           = excluded.closed_at,
    active_days         = excluded.active_days,
    refreshed_at        = now();
end;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: jobs_clean; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs_clean (
    id bigint NOT NULL,
    source text,
    job_code text,
    source_job_id text,
    title text,
    company_name text,
    location_id integer,
    region_mn text,
    district_mn text,
    location_level text,
    category text,
    job_level text,
    job_level_rank integer,
    employment_type text,
    salary_min numeric,
    salary_max numeric,
    salary_avg numeric,
    salary_status text,
    experience_years integer,
    skills text[],
    benefits text[],
    posted_at timestamp with time zone,
    deadline timestamp with time zone,
    first_seen_at timestamp with time zone,
    closed_at timestamp with time zone,
    is_active boolean,
    active_days integer,
    view_count integer,
    apply_count integer,
    dup_count integer,
    is_original boolean,
    loaded_at timestamp with time zone
);


--
-- Name: bridge_job_skill; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.bridge_job_skill WITH (security_invoker='on') AS
 SELECT DISTINCT j.id AS job_id,
    lower(btrim(s.s)) AS skill_key
   FROM (public.jobs_clean j
     CROSS JOIN LATERAL unnest(j.skills) s(s))
  WHERE (j.is_original AND (NULLIF(btrim(s.s), ''::text) IS NOT NULL));


--
-- Name: map_category; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_category (
    source text NOT NULL,
    source_category_id text NOT NULL,
    source_category_label text,
    category text NOT NULL
);


--
-- Name: map_category_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_category_group (
    category_name text NOT NULL,
    category_group text NOT NULL,
    group_sort integer NOT NULL
);


--
-- Name: dim_category; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_category WITH (security_invoker='on') AS
 WITH names AS (
         SELECT map_category.category AS category_name
           FROM public.map_category
        UNION
         SELECT 'Бусад'::text
        )
 SELECT n.category_name,
    COALESCE(g.category_group, 'Бусад'::text) AS category_group,
    COALESCE(g.group_sort, 99) AS group_sort
   FROM (names n
     LEFT JOIN public.map_category_group g USING (category_name));


--
-- Name: map_job_level; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_job_level (
    source text NOT NULL,
    raw_value text NOT NULL,
    job_level text NOT NULL,
    level_rank integer
);


--
-- Name: dim_job_level; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_job_level WITH (security_invoker='on') AS
 WITH lv AS (
         SELECT map_job_level.job_level,
            min(map_job_level.level_rank) AS level_rank
           FROM public.map_job_level
          GROUP BY map_job_level.job_level
        UNION
         SELECT 'Бусад'::text,
            NULL::integer AS int4
        )
 SELECT job_level,
    level_rank,
    (repeat(chr(8203), COALESCE(level_rank, 9)) || replace(job_level, '/Оюутан'::text, ''::text)) AS level_label
   FROM lv;


--
-- Name: fact_jobs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.fact_jobs WITH (security_invoker='on') AS
 SELECT id AS job_id,
    job_code,
    title,
    company_name,
    location_id,
    category AS category_name,
    job_level,
    employment_type,
    ((posted_at AT TIME ZONE 'Asia/Ulaanbaatar'::text))::date AS posted_date,
    (round(salary_min))::integer AS salary_min,
    (round(salary_max))::integer AS salary_max,
    (round(salary_avg))::integer AS salary_avg,
    salary_status,
    active_days,
    view_count,
    apply_count,
    loaded_at,
    job_level_rank,
        CASE
            WHEN (salary_status = 'monthly'::text) THEN (round(salary_avg))::integer
            ELSE NULL::integer
        END AS salary_monthly,
        CASE
            WHEN (job_level_rank <= 2) THEN 1
            ELSE 0
        END AS is_entry_level,
        CASE
            WHEN (((first_seen_at AT TIME ZONE 'Asia/Ulaanbaatar'::text))::date > (((now() AT TIME ZONE 'Asia/Ulaanbaatar'::text))::date - 7)) THEN 1
            ELSE 0
        END AS is_new_7d
   FROM public.jobs_clean
  WHERE is_original;


--
-- Name: dash_level_share; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dash_level_share WITH (security_invoker='on') AS
 WITH base AS (
         SELECT c.category_group,
            COALESCE(l.level_rank, 99) AS level_rank,
            f.job_level,
            count(*) AS jobs
           FROM ((public.fact_jobs f
             JOIN public.dim_category c USING (category_name))
             LEFT JOIN public.dim_job_level l USING (job_level))
          GROUP BY c.category_group, COALESCE(l.level_rank, 99), f.job_level
        ), tot AS (
         SELECT base.category_group,
            sum(base.jobs) AS total,
            COALESCE(sum(base.jobs) FILTER (WHERE (base.level_rank <= 2)), (0)::numeric) AS entry
           FROM base
          GROUP BY base.category_group
        ), ranked AS (
         SELECT t.category_group,
            t.total,
            t.entry,
            (round(((100.0 * t.entry) / t.total)))::integer AS pct,
            row_number() OVER (ORDER BY ((1.0 * t.entry) / t.total) DESC, t.category_group) AS rn
           FROM tot t
        )
 SELECT b.category_group,
    (((((r.rn || '. '::text) || b.category_group) || ' · '::text) || r.pct) || '%'::text) AS category_label,
    b.job_level,
    b.level_rank,
    (b.jobs)::integer AS jobs,
    (round(((100.0 * (b.jobs)::numeric) / r.total), 1))::double precision AS share,
    r.pct AS entry_pct,
    ((b.level_rank || '. '::text) || b.job_level) AS level_label
   FROM (base b
     JOIN ranked r USING (category_group));


--
-- Name: raw_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_jobs (
    id bigint NOT NULL,
    job_code text NOT NULL,
    list_payload jsonb,
    detail_payload jsonb,
    posted_at timestamp with time zone,
    first_seen_at timestamp with time zone DEFAULT now(),
    last_seen_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true,
    closed_at timestamp with time zone,
    reopen_count integer DEFAULT 0,
    source text DEFAULT 'zangia'::text NOT NULL
);


--
-- Name: dash_profession_salary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dash_profession_salary WITH (security_invoker='on') AS
 WITH base AS (
         SELECT (r.detail_payload ->> 'profession'::text) AS profession,
            f.salary_min,
            COALESCE(f.salary_max, f.salary_min) AS salary_max,
            f.salary_monthly
           FROM (public.fact_jobs f
             JOIN public.raw_jobs r ON (((r.source = 'zangia'::text) AND (r.job_code = f.job_code))))
          WHERE ((f.salary_status = 'monthly'::text) AND (COALESCE((r.detail_payload ->> 'profession'::text), ''::text) <> ALL (ARRAY[''::text, 'Бусад'::text])))
        ), agg AS (
         SELECT base.profession,
            count(*) AS jobs,
            percentile_disc((0.25)::double precision) WITHIN GROUP (ORDER BY base.salary_min) AS lo,
            percentile_disc((0.75)::double precision) WITHIN GROUP (ORDER BY base.salary_max) AS hi,
            percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((base.salary_monthly)::double precision)) AS med
           FROM base
          GROUP BY base.profession
         HAVING (count(*) >= 30)
        ), top10 AS (
         SELECT agg.profession,
            agg.jobs,
            agg.lo,
            agg.hi,
            agg.med
           FROM agg
          ORDER BY agg.jobs DESC
         LIMIT 10
        ), ranked AS (
         SELECT top10.profession,
            top10.jobs,
            top10.lo,
            top10.hi,
            top10.med,
            row_number() OVER (ORDER BY top10.med, top10.lo, top10.profession) AS med_rank
           FROM top10
        )
 SELECT profession,
    ((((((repeat(chr(8203), (med_rank)::integer) || profession) || ' · '::text) || to_char(((lo)::numeric / '1000000'::numeric), 'FM990.0'::text)) || '–'::text) || to_char(((hi)::numeric / '1000000'::numeric), 'FM990.0'::text)) || ' сая'::text) AS profession_label,
    (jobs)::integer AS jobs,
    (round(((lo)::numeric / '1000000'::numeric), 1))::double precision AS range_low,
    (round((((hi - lo))::numeric / '1000000'::numeric), 1))::double precision AS range_width,
    (round(((med / ('1000000'::numeric)::double precision))::numeric, 1))::double precision AS median_mln,
    (med_rank)::integer AS med_rank
   FROM ranked;


--
-- Name: dash_sector_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dash_sector_overview WITH (security_invoker='on') AS
 WITH base AS (
         SELECT c.category_group,
            c.group_sort,
            f.salary_status,
            f.salary_min,
            COALESCE(f.salary_max, f.salary_min) AS salary_max,
            f.salary_monthly
           FROM (public.fact_jobs f
             JOIN public.dim_category c USING (category_name))
        ), agg AS (
         SELECT base.category_group,
            max(base.group_sort) AS group_sort,
            count(*) AS jobs,
            count(*) FILTER (WHERE (base.salary_status = 'monthly'::text)) AS n_salary,
            percentile_disc((0.25)::double precision) WITHIN GROUP (ORDER BY base.salary_min) FILTER (WHERE (base.salary_status = 'monthly'::text)) AS lo,
            percentile_disc((0.75)::double precision) WITHIN GROUP (ORDER BY base.salary_max) FILTER (WHERE (base.salary_status = 'monthly'::text)) AS hi,
            percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((base.salary_monthly)::double precision)) AS med
           FROM base
          GROUP BY base.category_group
        ), ranked AS (
         SELECT agg.category_group,
            agg.group_sort,
            agg.jobs,
            agg.n_salary,
            agg.lo,
            agg.hi,
            agg.med,
            row_number() OVER (ORDER BY (agg.group_sort = 99) DESC, agg.jobs) AS sort_rank
           FROM agg
        )
 SELECT (repeat(chr(8203), (sort_rank)::integer) || category_group) AS sector_label,
    category_group,
    (jobs)::integer AS jobs,
    (n_salary)::integer AS n_salary,
    (round(((lo)::numeric / '1000000'::numeric), 1))::double precision AS range_low,
    (round((((hi - lo))::numeric / '1000000'::numeric), 1))::double precision AS range_width,
    (round(((med / ('1000000'::numeric)::double precision))::numeric, 1))::double precision AS median_mln,
    (sort_rank)::integer AS sort_rank
   FROM ranked;


--
-- Name: map_skill_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_skill_type (
    skill_name text NOT NULL,
    skill_type text NOT NULL,
    CONSTRAINT map_skill_type_skill_type_check CHECK ((skill_type = ANY (ARRAY['hard'::text, 'soft'::text])))
);


--
-- Name: dim_skill; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_skill WITH (security_invoker='on') AS
 WITH variants AS (
         SELECT lower(btrim(s.s)) AS skill_key,
            btrim(s.s) AS skill_name,
            count(*) AS n
           FROM (public.jobs_clean j
             CROSS JOIN LATERAL unnest(j.skills) s(s))
          WHERE (NULLIF(btrim(s.s), ''::text) IS NOT NULL)
          GROUP BY (lower(btrim(s.s))), (btrim(s.s))
        )
 SELECT DISTINCT ON (v.skill_key) v.skill_key,
    v.skill_name,
    COALESCE(t.skill_type, 'hard'::text) AS skill_type
   FROM (variants v
     LEFT JOIN public.map_skill_type t ON ((t.skill_name = v.skill_key)))
  ORDER BY v.skill_key, v.n DESC;


--
-- Name: dash_sector_skills; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dash_sector_skills WITH (security_invoker='on') AS
 WITH sector_total AS (
         SELECT fact_jobs.category_name,
            count(*) AS total
           FROM public.fact_jobs
          GROUP BY fact_jobs.category_name
        ), skill_counts AS (
         SELECT f.category_name,
            s.skill_name,
            count(DISTINCT f.job_id) AS jobs
           FROM ((public.fact_jobs f
             JOIN public.bridge_job_skill b ON ((b.job_id = f.job_id)))
             JOIN public.dim_skill s ON ((s.skill_key = b.skill_key)))
          WHERE (s.skill_type = 'hard'::text)
          GROUP BY f.category_name, s.skill_name
        ), ranked AS (
         SELECT sc.category_name,
            sc.skill_name,
            sc.jobs,
            row_number() OVER (PARTITION BY sc.category_name ORDER BY sc.jobs DESC, sc.skill_name) AS rn
           FROM skill_counts sc
        )
 SELECT r.category_name,
    r.skill_name,
    (((r.skill_name || ' · '::text) || (round(((100.0 * (r.jobs)::numeric) / (t.total)::numeric)))::integer) || '%'::text) AS skill_label,
    (r.jobs)::integer AS jobs,
    (round(((100.0 * (r.jobs)::numeric) / (t.total)::numeric)))::integer AS pct_of_sector,
    (r.rn)::integer AS rank_in_sector
   FROM (ranked r
     JOIN sector_total t USING (category_name))
  WHERE (r.rn <= 10);


--
-- Name: dash_top_skills; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dash_top_skills WITH (security_invoker='on') AS
 WITH total AS (
         SELECT count(*) AS n
           FROM public.fact_jobs
        )
 SELECT s.skill_name,
    count(DISTINCT f.job_id) AS jobs,
    round(((100.0 * (count(DISTINCT f.job_id))::numeric) / (( SELECT total.n
           FROM total))::numeric), 1) AS pct_of_jobs
   FROM ((public.fact_jobs f
     JOIN public.bridge_job_skill b ON ((b.job_id = f.job_id)))
     JOIN public.dim_skill s ON ((s.skill_key = b.skill_key)))
  WHERE (s.skill_type = 'hard'::text)
  GROUP BY s.skill_key, s.skill_name;


--
-- Name: dim_date; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_date (
    date_key integer NOT NULL,
    full_date date NOT NULL,
    year integer,
    quarter integer,
    month integer,
    month_label text,
    iso_week integer,
    weekday integer,
    weekday_mn text,
    is_weekend boolean
);


--
-- Name: map_employment_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_employment_type (
    source text NOT NULL,
    raw_value text NOT NULL,
    employment_type text NOT NULL
);


--
-- Name: dim_employment_type; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_employment_type WITH (security_invoker='on') AS
 SELECT map_employment_type.employment_type
   FROM public.map_employment_type
UNION
 SELECT 'Бусад'::text AS employment_type;


--
-- Name: dim_location; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_location (
    location_id integer NOT NULL,
    parent_id integer,
    name_mn text NOT NULL,
    name_en text,
    level text NOT NULL
);


--
-- Name: dim_location_flat; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_location_flat WITH (security_invoker='on') AS
 SELECT d.location_id,
        CASE COALESCE(p.name_mn, d.name_mn)
            WHEN 'Улаанбаатар хот'::text THEN 'Улаанбаатар'::text
            WHEN 'Дархан хот'::text THEN 'Дархан-Уул'::text
            WHEN 'Эрдэнэт хот'::text THEN 'Орхон'::text
            ELSE regexp_replace(COALESCE(p.name_mn, d.name_mn), '\s*аймаг$'::text, ''::text)
        END AS geo_region,
        CASE
            WHEN (d.level = 'district'::text) THEN regexp_replace(d.name_mn, '\s*дүүрэг$'::text, ''::text)
            ELSE NULL::text
        END AS geo_district,
    (COALESCE(p.name_mn, d.name_mn) = 'Улаанбаатар хот'::text) AS is_ub
   FROM (public.dim_location d
     LEFT JOIN public.dim_location p ON ((p.location_id = d.parent_id)));


--
-- Name: dim_salary_band; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.dim_salary_band WITH (security_invoker='on') AS
 SELECT DISTINCT salary_avg,
        CASE
            WHEN (salary_avg < 1500000) THEN '0.5–1.5'::text
            WHEN (salary_avg < 1800000) THEN '1.5–1.8'::text
            WHEN (salary_avg < 2100000) THEN '1.8–2.1'::text
            WHEN (salary_avg < 2500000) THEN '2.1–2.5'::text
            WHEN (salary_avg < 3000000) THEN '2.5–3.0'::text
            WHEN (salary_avg < 3500000) THEN '3.0–3.5'::text
            WHEN (salary_avg < 4000000) THEN '3.5–4.0'::text
            WHEN (salary_avg < 4500000) THEN '4.0–4.5'::text
            WHEN (salary_avg < 5000000) THEN '4.5–5.0'::text
            ELSE '5.0+'::text
        END AS band_label
   FROM public.fact_jobs
  WHERE (salary_status = 'monthly'::text);


--
-- Name: jobs_unified; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs_unified (
    id bigint NOT NULL,
    source text NOT NULL,
    job_code text,
    source_job_id text,
    title text,
    company_name text,
    salary_min numeric,
    salary_max numeric,
    employment_type_raw text,
    job_level_raw text,
    location_raw text,
    category_id text,
    category_name text,
    skills text[],
    benefits text[],
    experience_years integer,
    deadline timestamp with time zone,
    view_count integer,
    apply_count integer,
    duties_html text,
    requirements_html text,
    posted_at timestamp with time zone,
    first_seen_at timestamp with time zone,
    is_active boolean,
    closed_at timestamp with time zone,
    active_days integer,
    refreshed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: map_company_override; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_company_override (
    company_raw text NOT NULL,
    company_name text NOT NULL
);


--
-- Name: map_location; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_location (
    source text NOT NULL,
    location_raw text NOT NULL,
    location_id integer NOT NULL
);


--
-- Name: stg_jobs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.stg_jobs WITH (security_invoker='true') AS
 WITH company_keyed AS (
         SELECT j.id,
            j.source,
            j.company_name,
            public.norm_company(COALESCE(o.company_name, j.company_name)) AS company_key
           FROM (public.jobs_unified j
             LEFT JOIN public.map_company_override o ON ((o.company_raw = j.company_name)))
        ), company_display AS (
         SELECT DISTINCT ON (company_keyed.company_key) company_keyed.company_key,
            TRIM(BOTH FROM regexp_replace(regexp_replace(company_keyed.company_name, '["“”«»„]'::text, ''::text, 'g'::text), '\s+'::text, ' '::text, 'g'::text)) AS company_name
           FROM company_keyed
          WHERE (company_keyed.company_key IS NOT NULL)
          GROUP BY company_keyed.company_key, company_keyed.company_name, company_keyed.source
          ORDER BY company_keyed.company_key, (company_keyed.source = 'zangia'::text) DESC, (count(*)) DESC
        ), cleaned AS (
         SELECT j.id AS job_id,
            j.source,
            NULLIF(j.salary_min, (0)::numeric) AS salary_min,
            NULLIF(j.salary_max, (0)::numeric) AS salary_max,
            COALESCE(m.category, 'Бусад'::text) AS job_category,
            j.is_active,
            j.job_code,
            COALESCE(e.employment_type, 'Бусад'::text) AS employment_type,
            j.title,
            cd.company_name,
            d.name_mn AS location
           FROM ((((((public.jobs_unified j
             LEFT JOIN public.map_category m ON (((m.source = j.source) AND (m.source_category_id = j.category_id))))
             LEFT JOIN public.map_employment_type e ON (((e.source = j.source) AND (e.raw_value = j.employment_type_raw))))
             LEFT JOIN company_keyed ck ON ((ck.id = j.id)))
             LEFT JOIN company_display cd ON ((cd.company_key = ck.company_key)))
             LEFT JOIN public.map_location ml ON (((ml.source = j.source) AND (ml.location_raw = j.location_raw))))
             LEFT JOIN public.dim_location d ON ((d.location_id = ml.location_id)))
        ), calc AS (
         SELECT cleaned.job_id,
            cleaned.source,
            cleaned.salary_min,
            cleaned.salary_max,
            cleaned.job_category,
            cleaned.is_active,
            cleaned.job_code,
            cleaned.employment_type,
            cleaned.title,
            cleaned.company_name,
            cleaned.location,
                CASE
                    WHEN ((cleaned.salary_min IS NOT NULL) AND (cleaned.salary_max IS NOT NULL)) THEN round(((cleaned.salary_min + cleaned.salary_max) / (2)::numeric))
                    ELSE COALESCE(cleaned.salary_min, cleaned.salary_max)
                END AS raw_avg
           FROM cleaned
        )
 SELECT job_id,
    source,
    salary_min,
    salary_max,
    raw_avg AS salary_avg,
    job_category,
    employment_type,
        CASE
            WHEN (raw_avg IS NULL) THEN 'no_salary'::text
            WHEN ((employment_type = 'Цагийн ажил'::text) OR (raw_avg < (500000)::numeric)) THEN 'non_monthly'::text
            WHEN (raw_avg > (15000000)::numeric) THEN 'monthly_outlier'::text
            ELSE 'monthly'::text
        END AS salary_status,
    is_active,
    job_code,
    title,
    company_name,
    location
   FROM calc;


--
-- Name: mart_active_jobs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.mart_active_jobs AS
 SELECT job_id,
    source,
    job_category,
    employment_type,
    salary_min,
    salary_max,
    salary_avg,
    salary_status,
    job_code
   FROM public.stg_jobs
  WHERE is_active;


--
-- Name: raw_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.raw_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: raw_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.raw_jobs_id_seq OWNED BY public.raw_jobs.id;


--
-- Name: scan_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scan_runs (
    id bigint NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    pages_scanned integer,
    failed_pages integer,
    seen_count integer,
    new_count integer,
    closed_count integer,
    reopened_count integer,
    scan_completed boolean,
    source text DEFAULT 'zangia'::text NOT NULL
);


--
-- Name: scan_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scan_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scan_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scan_runs_id_seq OWNED BY public.scan_runs.id;


--
-- Name: raw_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_jobs ALTER COLUMN id SET DEFAULT nextval('public.raw_jobs_id_seq'::regclass);


--
-- Name: scan_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_runs ALTER COLUMN id SET DEFAULT nextval('public.scan_runs_id_seq'::regclass);


--
-- Name: map_category category_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_category
    ADD CONSTRAINT category_map_pkey PRIMARY KEY (source, source_category_id);


--
-- Name: dim_date dim_date_full_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_date
    ADD CONSTRAINT dim_date_full_date_key UNIQUE (full_date);


--
-- Name: dim_date dim_date_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_date
    ADD CONSTRAINT dim_date_pkey PRIMARY KEY (date_key);


--
-- Name: dim_location dim_location_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_location
    ADD CONSTRAINT dim_location_pkey PRIMARY KEY (location_id);


--
-- Name: map_employment_type employment_type_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_employment_type
    ADD CONSTRAINT employment_type_map_pkey PRIMARY KEY (source, raw_value);


--
-- Name: jobs_clean jobs_clean_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs_clean
    ADD CONSTRAINT jobs_clean_pkey PRIMARY KEY (id);


--
-- Name: jobs_unified jobs_unified_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs_unified
    ADD CONSTRAINT jobs_unified_pkey PRIMARY KEY (id);


--
-- Name: map_category_group map_category_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_category_group
    ADD CONSTRAINT map_category_group_pkey PRIMARY KEY (category_name);


--
-- Name: map_company_override map_company_override_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_company_override
    ADD CONSTRAINT map_company_override_pkey PRIMARY KEY (company_raw);


--
-- Name: map_job_level map_job_level_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_job_level
    ADD CONSTRAINT map_job_level_pkey PRIMARY KEY (source, raw_value);


--
-- Name: map_location map_location_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_location
    ADD CONSTRAINT map_location_pkey PRIMARY KEY (source, location_raw);


--
-- Name: map_skill_type map_skill_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_skill_type
    ADD CONSTRAINT map_skill_type_pkey PRIMARY KEY (skill_name);


--
-- Name: raw_jobs raw_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_jobs
    ADD CONSTRAINT raw_jobs_pkey PRIMARY KEY (id);


--
-- Name: raw_jobs raw_jobs_source_code_uk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_jobs
    ADD CONSTRAINT raw_jobs_source_code_uk UNIQUE (source, job_code);


--
-- Name: scan_runs scan_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scan_runs
    ADD CONSTRAINT scan_runs_pkey PRIMARY KEY (id);


--
-- Name: idx_raw_jobs_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_jobs_is_active ON public.raw_jobs USING btree (is_active);


--
-- Name: jobs_unified_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jobs_unified_category_idx ON public.jobs_unified USING btree (source, category_id);


--
-- Name: jobs_unified_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jobs_unified_source_idx ON public.jobs_unified USING btree (source);


--
-- Name: dim_location dim_location_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_location
    ADD CONSTRAINT dim_location_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.dim_location(location_id);


--
-- Name: map_location map_location_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_location
    ADD CONSTRAINT map_location_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.dim_location(location_id);


--
-- Name: dim_date; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dim_date ENABLE ROW LEVEL SECURITY;

--
-- Name: dim_location; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.dim_location ENABLE ROW LEVEL SECURITY;

--
-- Name: jobs_clean; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.jobs_clean ENABLE ROW LEVEL SECURITY;

--
-- Name: jobs_unified; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.jobs_unified ENABLE ROW LEVEL SECURITY;

--
-- Name: map_category; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_category ENABLE ROW LEVEL SECURITY;

--
-- Name: map_category_group; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_category_group ENABLE ROW LEVEL SECURITY;

--
-- Name: map_company_override; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_company_override ENABLE ROW LEVEL SECURITY;

--
-- Name: map_employment_type; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_employment_type ENABLE ROW LEVEL SECURITY;

--
-- Name: map_job_level; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_job_level ENABLE ROW LEVEL SECURITY;

--
-- Name: map_location; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_location ENABLE ROW LEVEL SECURITY;

--
-- Name: map_skill_type; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.map_skill_type ENABLE ROW LEVEL SECURITY;

--
-- Name: raw_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.raw_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: scan_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.scan_runs ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict R2U8giTWRytbHjFCLTkpBmprhBI3WAjvWaWNDvFVam8vp8lbnGVGU7gDOb7BD0b

