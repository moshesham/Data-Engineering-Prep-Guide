---
layout: default
title: Module 3 — SQL
permalink: /modules/sql/
---

## Module 3 — SQL

**Core job:** write analytically complete queries that don't fan out or full-scan, using the schema you just drew.

**Fundamentals to have cold:**
- `WHERE` (row-level, pre-aggregation) vs. `HAVING` (group-level, post-aggregation); three-valued logic with `NULL` — use `COALESCE`/`NULLIF` deliberately, don't let a silent `NULL` drop rows from a join.
- Join fan-out: a non-unique join key silently multiplies rows and inflates every downstream `SUM`. Say out loud how you'd verify row-count integrity after a join (`COUNT(*)` before/after, or `COUNT(DISTINCT pk)`).
- Window functions: `ROW_NUMBER()` / `RANK()` / `DENSE_RANK()` for top-N; `LEAD()`/`LAG()` for time deltas between sequential events; explicit frames (`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`) for rolling metrics.
- CTEs to modularize; partition filters and pushdown predicates to bound scans; `APPROX_DISTINCT` when exactness isn't worth the shuffle.

**Worked problem:** using `fact_reel_impressions(user_id, creator_id, watch_time_ms, ds)`, compute a 3-day rolling average watch time per user, and the top-2 creators by total watch time per country on `2026-07-20`.

```sql
WITH daily_user_watch AS (
    -- Pre-aggregate to daily grain before windowing, to cut row volume early
    SELECT user_id, ds, SUM(watch_time_ms) AS total_daily_watch_ms
    FROM fact_reel_impressions
    WHERE ds BETWEEN DATE_SUB('2026-07-20', 2) AND '2026-07-20'
    GROUP BY user_id, ds
),

rolling_user_avg AS (
    SELECT user_id, ds,
           AVG(total_daily_watch_ms) OVER (
               PARTITION BY user_id
               ORDER BY CAST(ds AS DATE)
               ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
           ) AS rolling_3d_avg_watch_ms
    FROM daily_user_watch
),

creator_country_watch AS (
    -- Point-in-time correct join: only the current dim_user row
    SELECT u.country, f.creator_id,
           SUM(f.watch_time_ms) AS total_creator_watch_ms,
           DENSE_RANK() OVER (
               PARTITION BY u.country
               ORDER BY SUM(f.watch_time_ms) DESC
           ) AS creator_rank
    FROM fact_reel_impressions f
    JOIN dim_user u
      ON f.user_id = u.user_id AND u.is_current = TRUE
    WHERE f.ds = '2026-07-20'
    GROUP BY u.country, f.creator_id
)

SELECT country, creator_id, total_creator_watch_ms
FROM creator_country_watch
WHERE creator_rank <= 2;
```

Notice the join in `creator_country_watch` filters `u.is_current = TRUE` — that's the SCD Type-2 discipline from Module 2 showing up in the query. If you drop that filter, a user who changed country mid-history double-counts. This is exactly the kind of drift interviewers are watching for.

