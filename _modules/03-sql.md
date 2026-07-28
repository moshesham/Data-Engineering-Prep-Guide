---
layout: default
title: Module 3 — SQL
permalink: /modules/sql/
---

## Module 3 — SQL

**Core job:** write analytically complete queries that do not fan out, silently drop `NULL`s, or full-scan history unnecessarily.

### SQL engine compatibility key

Primary dialect in this guide is **ANSI SQL / Presto (Trino)-style analytics SQL**.

| Topic | Snowflake / BigQuery | Presto/Trino / Spark SQL | PostgreSQL-style note |
|---|---|---|---|
| `QUALIFY` on window results | native support | use CTE/subquery + outer `WHERE` in Presto/Trino | usually CTE/subquery + outer `WHERE` |
| Date subtraction | `DATEADD`/engine function variants | `date_add`/interval expressions (engine-specific) | `'2026-07-20'::date - INTERVAL '2 days'` |
| Window frames | full support | full support; always specify frame explicitly | full support |

## Table of Contents

1. [Core Semantics](#1-core-semantics)
   1. [WHERE vs. HAVING vs. QUALIFY](#11-where-vs-having-vs-qualify)
   2. [NULL handling and three-valued logic](#12-null-handling-and-three-valued-logic)
   3. [UNION / UNION ALL / INTERSECT / EXCEPT](#13-unionunion-allintersectexcept)
2. [Joins](#2-joins)
   1. [Join types and fan-out risk](#21-join-types-and-fan-out-risk)
   2. [Anti-join / semi-join patterns](#22-anti-join--semi-join-for-did-x-but-not-y-patterns)
   3. [Self-joins for adjacent-event comparison](#23-self-joins-for-adjacent-event-comparison)
3. [Window Functions](#3-window-functions)
   1. [Ranking and offset families](#31-ranking-and-offset-families)
   2. [Running totals and moving averages](#32-running-totals-and-moving-averages)
   3. [ROWS vs. RANGE frame semantics](#33-rows-vs-range-frame-semantics)
4. [Advanced Query Patterns](#4-advanced-query-patterns)
   1. [Funnel conversion query](#41-funnel-conversion-query)
   2. [Retention / cohort query](#42-retention--cohort-query)
   3. [Sessionization (gaps-and-islands)](#43-sessionization-gaps-and-islands)
   4. [Pivot / unpivot](#44-pivot--unpivot)
   5. [Existing rolling-average and top-N example](#45-existing-worked-problem-rolling-average--top-2-creators)
5. [Performance](#5-performance)
   1. [Partition pruning and predicate pushdown](#51-partition-pruning-and-predicate-pushdown)
   2. [Approximate aggregation functions](#52-approximate-aggregation-functions)

## 1. Core Semantics

### 1.1 WHERE vs. HAVING vs. QUALIFY

| Clause | Filters what | When it runs | Example |
|---|---|---|---|
| `WHERE` | raw rows | before aggregation | restrict to `ds >= '2026-07-01'` |
| `HAVING` | grouped rows | after aggregation | keep creators with `COUNT(*) >= 100` |
| `QUALIFY` | windowed rows | after window functions | keep `ROW_NUMBER() = 1` per user |

Rule of thumb:
- use `WHERE` to shrink the scan early
- use `HAVING` for aggregate conditions
- use `QUALIFY` when your warehouse supports it; otherwise compute window columns in a CTE/subquery and filter in outer `WHERE`

### 1.2 NULL handling and three-valued logic

SQL uses **TRUE / FALSE / UNKNOWN**.

Implications:
- `WHERE country = 'US'` excludes `NULL` countries
- `NULL = NULL` is not `TRUE`
- `NOT IN (...)` can behave unexpectedly if the subquery contains `NULL`

Defensive habits:
- use `COALESCE(country, 'UNKNOWN')`
- use `NULLIF(denominator, 0)` for division safety
- prefer `NOT EXISTS` over `NOT IN` for anti-joins

`NOT IN` trap demonstration:

```sql
-- blocklist contains (101, 102, NULL)
SELECT user_id
FROM users
WHERE user_id NOT IN (SELECT user_id FROM blocklist);

-- Returns 0 rows because NULL in the subquery makes the predicate UNKNOWN.

-- Safe pattern 1: NOT EXISTS
SELECT u.user_id
FROM users u
WHERE NOT EXISTS (
        SELECT 1
        FROM blocklist b
        WHERE b.user_id = u.user_id
);

-- Safe pattern 2: LEFT JOIN anti-join
SELECT u.user_id
FROM users u
LEFT JOIN blocklist b
    ON u.user_id = b.user_id
WHERE b.user_id IS NULL;
```

### 1.3 UNION/UNION ALL/INTERSECT/EXCEPT

| Operator | Behavior | Use case |
|---|---|---|
| `UNION ALL` | append all rows, keep duplicates | stitching partitions or event streams |
| `UNION` | append then deduplicate | combining logically identical result sets |
| `INTERSECT` | rows present in both | users active in both weeks |
| `EXCEPT` | rows in left, not right | churn candidate sets |

Use `UNION ALL` by default unless you explicitly need deduplication, because dedup requires extra work and can hide upstream data quality issues.

## 2. Joins

### 2.1 Join types and fan-out risk

Join fan-out is one of the most common SQL interview mistakes.

| Join type | Keeps rows from | Typical use |
|---|---|---|
| `INNER JOIN` | only matching rows | enriched metrics where match is required |
| `LEFT JOIN` | all left rows | retention, optional dimensions, anti-join patterns |
| `RIGHT JOIN` | all right rows | rare; usually rewrite as `LEFT JOIN` |
| `FULL OUTER JOIN` | rows from both sides | reconciliation |

Fan-out warning signs:
- joining fact-to-fact without pre-aggregation
- joining to a dimension that is not unique on the join key
- forgetting SCD point-in-time filters

Verification habit:
- compare `COUNT(*)` before and after the join
- compare `COUNT(DISTINCT primary_key)` before and after the join

### 2.2 Anti-join / semi-join for "did X but not Y" patterns

#### Worked example: users active last week but NOT active this week

Assume:
- "last week" = `2026-07-13` through `2026-07-19`
- "this week" = `2026-07-20` through `2026-07-26`

**Approach 1: `NOT EXISTS`**

```sql
WITH last_week_active AS (
    SELECT DISTINCT user_id
    FROM fact_user_events
    WHERE ds BETWEEN '2026-07-13' AND '2026-07-19'
)
SELECT lwa.user_id
FROM last_week_active lwa
WHERE NOT EXISTS (
    SELECT 1
    FROM fact_user_events f
    WHERE f.user_id = lwa.user_id
      AND f.ds BETWEEN '2026-07-20' AND '2026-07-26'
);
```

**Approach 2: `LEFT JOIN ... IS NULL`**

```sql
WITH last_week_active AS (
    SELECT DISTINCT user_id
    FROM fact_user_events
    WHERE ds BETWEEN '2026-07-13' AND '2026-07-19'
),
this_week_active AS (
    SELECT DISTINCT user_id
    FROM fact_user_events
    WHERE ds BETWEEN '2026-07-20' AND '2026-07-26'
)
SELECT lwa.user_id
FROM last_week_active lwa
LEFT JOIN this_week_active twa
  ON lwa.user_id = twa.user_id
WHERE twa.user_id IS NULL;
```

Use this pattern for churn lists, dropped senders, lapsed buyers, or creators who stopped posting.

### 2.3 Self-joins for adjacent-event comparison

Self-joins and window offsets solve sequence questions.

Example prompt:
- compare each user's current event to the immediately previous event
- compute time between messages
- detect event order violations

You can do this with `LAG()` or with a self-join on ranked events. `LAG()` is usually simpler:

```sql
SELECT
    user_id,
    event_type,
    event_timestamp,
    LAG(event_type) OVER (
        PARTITION BY user_id
        ORDER BY event_timestamp
    ) AS previous_event_type,
    LAG(event_timestamp) OVER (
        PARTITION BY user_id
        ORDER BY event_timestamp
    ) AS previous_event_timestamp
FROM fact_user_events
WHERE ds BETWEEN '2026-07-20' AND '2026-07-26';
```

## 3. Window Functions

### 3.1 Ranking and offset families

Must-know window functions:
- `ROW_NUMBER()` — unique ordering
- `RANK()` — ties leave gaps
- `DENSE_RANK()` — ties do not leave gaps
- `LAG()` / `LEAD()` — prior/next row access

Typical use cases:
- top-3 creators per country
- first signup event per user
- time since previous session

### 3.2 Running totals and moving averages

Examples:
- running spend by campaign
- 7-day rolling watch time
- cumulative messages sent within a conversation

Always specify the frame explicitly when the default is ambiguous:

```sql
SUM(spend_usd) OVER (
    PARTITION BY campaign_id
    ORDER BY ds
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
) AS running_spend_usd
```

### 3.3 ROWS vs. RANGE frame semantics

- `ROWS` counts physical rows relative to the current row
- `RANGE` groups peers with the same ordering value

Why it matters:
- if multiple rows share the same `ds`, `RANGE` can include all peers with that date
- `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` means exactly three rows

In interview SQL, prefer `ROWS` unless you intentionally want peer grouping behavior.

Tie example (same ordering value):

- Rows: `(ds='2026-07-20', val=10)`, `(ds='2026-07-20', val=20)`
- `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`:
    - row 1 running sum = `10`
    - row 2 running sum = `30`
- `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`:
    - row 1 running sum = `30`
    - row 2 running sum = `30` (both rows are peers on `ds`)

## 4. Advanced Query Patterns

### 4.1 Funnel conversion query

Prompt: Given `fact_user_events(user_id, event_type, event_timestamp, ds)`, compute a Reels funnel:

**Impression → Watch >3s → Like → Share**

Show counts and conversion rates at each step.

Assumptions:
- `event_type` values are `reel_impression`, `reel_watch_3s`, `reel_like`, `reel_share`
- a user must complete steps in order
- query window is bounded by `ds`

Conditional aggregation idiom to know by memory:

```sql
COUNT(DISTINCT CASE WHEN event_type = 'reel_impression' THEN user_id END)
```

Why it works: `CASE` yields `NULL` for non-matching rows, and `COUNT(DISTINCT ...)` ignores `NULL`, so you count unique users only for the matching step in one scan.

```sql
WITH impression_users AS (
    SELECT
        user_id,
        MIN(event_timestamp) AS impression_ts
    FROM fact_user_events
    WHERE ds BETWEEN '2026-07-20' AND '2026-07-26'
      AND event_type = 'reel_impression'
    GROUP BY user_id
),
watch_users AS (
    SELECT
        i.user_id,
        MIN(f.event_timestamp) AS watch_ts
    FROM impression_users i
    JOIN fact_user_events f
      ON f.user_id = i.user_id
     AND f.event_type = 'reel_watch_3s'
     AND f.event_timestamp >= i.impression_ts
     AND f.ds BETWEEN '2026-07-20' AND '2026-07-26'
    GROUP BY i.user_id
),
like_users AS (
    SELECT
        w.user_id,
        MIN(f.event_timestamp) AS like_ts
    FROM watch_users w
    JOIN fact_user_events f
      ON f.user_id = w.user_id
     AND f.event_type = 'reel_like'
     AND f.event_timestamp >= w.watch_ts
     AND f.ds BETWEEN '2026-07-20' AND '2026-07-26'
    GROUP BY w.user_id
),
share_users AS (
    SELECT
        l.user_id,
        MIN(f.event_timestamp) AS share_ts
    FROM like_users l
    JOIN fact_user_events f
      ON f.user_id = l.user_id
     AND f.event_type = 'reel_share'
     AND f.event_timestamp >= l.like_ts
     AND f.ds BETWEEN '2026-07-20' AND '2026-07-26'
    GROUP BY l.user_id
),
funnel_counts AS (
    SELECT 'impression' AS funnel_step, COUNT(*) AS user_count FROM impression_users
    UNION ALL
    SELECT 'watch_3s'   AS funnel_step, COUNT(*) AS user_count FROM watch_users
    UNION ALL
    SELECT 'like'       AS funnel_step, COUNT(*) AS user_count FROM like_users
    UNION ALL
    SELECT 'share'      AS funnel_step, COUNT(*) AS user_count FROM share_users
)
SELECT
    funnel_step,
    user_count,
    LAG(user_count) OVER (ORDER BY
        CASE funnel_step
           WHEN 'impression' THEN 1
           WHEN 'watch_3s'   THEN 2
           WHEN 'like'       THEN 3
           WHEN 'share'      THEN 4
        END
    ) AS previous_step_users,
    ROUND(
        100.0 * user_count
        / NULLIF(
           LAG(user_count) OVER (ORDER BY
               CASE funnel_step
                   WHEN 'impression' THEN 1
                   WHEN 'watch_3s'   THEN 2
                   WHEN 'like'       THEN 3
                   WHEN 'share'      THEN 4
               END
           ),
           0
        ),
        2
    ) AS step_conversion_pct,
    ROUND(
        100.0 * user_count
        / NULLIF(
           MAX(CASE WHEN funnel_step = 'impression' THEN user_count END) OVER (),
           0
        ),
        2
    ) AS overall_conversion_pct
FROM funnel_counts
ORDER BY
    CASE funnel_step
        WHEN 'impression' THEN 1
        WHEN 'watch_3s'   THEN 2
        WHEN 'like'       THEN 3
        WHEN 'share'      THEN 4
    END;
```

What this query shows:
- count at each stage
- step-to-step conversion
- overall conversion from impression baseline

Practice transfer prompts:
- Rewrite this pattern for `fact_marketplace_transactions` as `listing_view -> message_seller -> checkout_started -> transaction_completed`.
- Rewrite this pattern for `fact_messenger_messages` as `conversation_open -> message_sent -> reply_received`.

### 4.2 Retention / cohort query

Prompt: Given `fact_user_events(user_id, event_type, event_timestamp, ds)`, compute a signup cohort retention matrix:
- for each signup cohort day
- what percent of users returned on **D1, D7, D30**

Assumptions:
- `event_type = 'signup'` marks signup
- any later event counts as a return event
- a user belongs to the date of their first signup

Join-flow walkthrough:

```text
first_signup (cohort spine per user)
    |
    | LEFT JOIN by user_id + exact day offsets (D1/D7/D30)
    v
d1_retained / d7_retained / d30_retained
    |
    | LEFT JOIN onto cohort_sizes by signup_date
    v
final retention percentages by cohort_date
```

```sql
WITH signup_ranked AS (
    SELECT
        user_id,
        CAST(event_timestamp AS DATE) AS signup_date,
        ROW_NUMBER() OVER (
           PARTITION BY user_id
           ORDER BY event_timestamp
        ) AS rn
    FROM fact_user_events
    WHERE event_type = 'signup'
),
first_signup AS (
    SELECT
        user_id,
        signup_date
    FROM signup_ranked
    WHERE rn = 1
),
cohort_sizes AS (
    SELECT
        signup_date,
        COUNT(*) AS cohort_size
    FROM first_signup
    GROUP BY signup_date
),
activity_days AS (
    SELECT DISTINCT
        user_id,
        CAST(event_timestamp AS DATE) AS activity_date
    FROM fact_user_events
    WHERE event_type <> 'signup'
),
d1_retained AS (
    SELECT
        fs.signup_date,
        COUNT(DISTINCT a.user_id) AS retained_users
    FROM first_signup fs
    LEFT JOIN activity_days a
      ON a.user_id = fs.user_id
     AND a.activity_date = fs.signup_date + INTERVAL '1 day'
    GROUP BY fs.signup_date
),
d7_retained AS (
    SELECT
        fs.signup_date,
        COUNT(DISTINCT a.user_id) AS retained_users
    FROM first_signup fs
    LEFT JOIN activity_days a
      ON a.user_id = fs.user_id
     AND a.activity_date = fs.signup_date + INTERVAL '7 day'
    GROUP BY fs.signup_date
),
d30_retained AS (
    SELECT
        fs.signup_date,
        COUNT(DISTINCT a.user_id) AS retained_users
    FROM first_signup fs
    LEFT JOIN activity_days a
      ON a.user_id = fs.user_id
     AND a.activity_date = fs.signup_date + INTERVAL '30 day'
    GROUP BY fs.signup_date
)
SELECT
    c.signup_date AS cohort_date,
    c.cohort_size,
    COALESCE(d1.retained_users, 0) AS d1_users,
    ROUND(100.0 * COALESCE(d1.retained_users, 0) / NULLIF(c.cohort_size, 0), 2) AS d1_retention_pct,
    COALESCE(d7.retained_users, 0) AS d7_users,
    ROUND(100.0 * COALESCE(d7.retained_users, 0) / NULLIF(c.cohort_size, 0), 2) AS d7_retention_pct,
    COALESCE(d30.retained_users, 0) AS d30_users,
    ROUND(100.0 * COALESCE(d30.retained_users, 0) / NULLIF(c.cohort_size, 0), 2) AS d30_retention_pct
FROM cohort_sizes c
LEFT JOIN d1_retained d1
  ON c.signup_date = d1.signup_date
LEFT JOIN d7_retained d7
  ON c.signup_date = d7.signup_date
LEFT JOIN d30_retained d30
  ON c.signup_date = d30.signup_date
ORDER BY c.signup_date;
```

Why interviewers like this pattern:
- it combines window functions, deduplication, left joins, and retention reasoning
- it forces you to distinguish **cohort date** from **activity date**

### 4.3 Sessionization (gaps-and-islands)

Prompt: assign a `session_id` to each event, where a new session starts when the gap between consecutive events for the same user is **more than 30 minutes**.

This is a classic event-stream pattern.

```sql
WITH ordered_events AS (
    SELECT
        user_id,
        event_type,
        event_timestamp,
        ds,
        LAG(event_timestamp) OVER (
           PARTITION BY user_id
           ORDER BY event_timestamp
        ) AS prev_event_timestamp
    FROM fact_user_events
    WHERE ds BETWEEN '2026-07-20' AND '2026-07-26'
),
session_boundaries AS (
    SELECT
        user_id,
        event_type,
        event_timestamp,
        ds,
        CASE
           WHEN prev_event_timestamp IS NULL THEN 1
           WHEN event_timestamp > prev_event_timestamp + INTERVAL '30 minute' THEN 1
           ELSE 0
        END AS is_new_session
    FROM ordered_events
),
session_numbered AS (
    SELECT
        user_id,
        event_type,
        event_timestamp,
        ds,
        -- running count of session starts becomes a stable per-user session number
        SUM(is_new_session) OVER (
           PARTITION BY user_id
           ORDER BY event_timestamp
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS session_sequence
    FROM session_boundaries
)
SELECT
    user_id,
    event_type,
    event_timestamp,
    ds,
    session_sequence,
    CONCAT(CAST(user_id AS VARCHAR), '_', CAST(session_sequence AS VARCHAR)) AS session_id
FROM session_numbered
ORDER BY user_id, event_timestamp;
```

Why this works:
- `LAG()` detects the prior event timestamp
- `CASE` turns the gap rule into a session-start flag
- running `SUM()` turns flags into stable session numbers

### 4.4 Pivot / unpivot

Pivot and unpivot are useful when the interviewer wants dashboard-shaped output.

Example use cases:
- show D1 / D7 / D30 retention as columns
- show send counts by message type as columns
- normalize wide campaign metrics back into long form for downstream logic

Some engines support native `PIVOT`; otherwise use conditional aggregation:

```sql
SELECT
    ds,
    SUM(CASE WHEN message_type = 'text' THEN 1 ELSE 0 END) AS text_messages,
    SUM(CASE WHEN message_type = 'image' THEN 1 ELSE 0 END) AS image_messages,
    SUM(CASE WHEN message_type = 'video' THEN 1 ELSE 0 END) AS video_messages
FROM fact_message
GROUP BY ds;
```

### 4.5 Existing worked problem: rolling average + top-2 creators

Using `fact_reel_impressions(user_id, creator_id, watch_time_ms, ds)`, compute a 3-day rolling average watch time per user, and the top-2 creators by total watch time per country on `2026-07-20`.

```sql
WITH daily_user_watch AS (
    SELECT
        user_id,
        ds,
        SUM(watch_time_ms) AS total_daily_watch_ms
    FROM fact_reel_impressions
    WHERE ds BETWEEN DATE_SUB('2026-07-20', 2) AND '2026-07-20'
    GROUP BY user_id, ds
),
rolling_user_avg AS (
    SELECT
        user_id,
        ds,
        AVG(total_daily_watch_ms) OVER (
           PARTITION BY user_id
           ORDER BY CAST(ds AS DATE)
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS rolling_3d_avg_watch_ms
    FROM daily_user_watch
),
creator_country_watch AS (
    SELECT
        u.country,
        f.creator_id,
        SUM(f.watch_time_ms) AS total_creator_watch_ms,
        DENSE_RANK() OVER (
           PARTITION BY u.country
           ORDER BY SUM(f.watch_time_ms) DESC
        ) AS creator_rank
    FROM fact_reel_impressions f
    JOIN dim_user u
      ON f.user_id = u.user_id
     AND u.is_current = TRUE
    WHERE f.ds = '2026-07-20'
    GROUP BY u.country, f.creator_id
)
SELECT country, creator_id, total_creator_watch_ms
FROM creator_country_watch
WHERE creator_rank <= 2;
```

Notice the join in `creator_country_watch` filters `u.is_current = TRUE` — that is SCD Type-2 discipline from Module 2. Without it, a user who changed country mid-history can double-count.

## 5. Performance

### 5.1 Partition pruning and predicate pushdown

Performance basics to say out loud:
- always filter `ds` or partition columns early
- project only needed columns
- pre-aggregate before joining when possible
- push predicates into CTEs or subqueries close to the scan

Bad:
- join a full fact table to a dimension, then filter dates later

Better:
- filter `ds` in the fact scan first, then join

### 5.2 Approximate aggregation functions

At Meta scale, exact distinct counts can be expensive.

Common tools:
- `APPROX_DISTINCT`
- `HLL` / HyperLogLog-based sketches
- approximate percentiles

Use them when:
- dashboards tolerate tiny error
- the alternative is a massive global shuffle

Do not use them when:
- finance reconciliation requires exactness
- the interviewer asks for exact cohort sizes or billing numbers
