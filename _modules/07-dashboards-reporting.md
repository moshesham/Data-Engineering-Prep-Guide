---
layout: default
title: Module 7 — Dashboards & Reporting
permalink: /modules/dashboards-reporting/
---

## Module 7 — Dashboards & Reporting

## Table of Contents
1. [Dashboard Architecture](#1-dashboard-architecture)
   1. [KPI layer vs. drill-down layer vs. raw-event layer](#11-kpi-layer-vs-drill-down-layer-vs-raw-event-layer)
   2. [Pre-aggregation strategy](#12-pre-aggregation-strategy)
2. [Chart Selection](#2-chart-selection)
   1. [When to use line vs. bar vs. funnel vs. cohort heatmap](#21-when-to-use-line-vs-bar-vs-funnel-vs-cohort-heatmap)
3. [Funnel Design](#3-funnel-design)
   1. [Backing table schema for a funnel](#31-backing-table-schema-for-a-funnel)
   2. [SQL that populates it](#32-the-sql-that-populates-it-link-to-module-3)
4. [Retention/Cohort Design](#4-retentioncohort-design)
   1. [Backing table schema for a cohort matrix](#41-backing-table-schema-for-a-cohort-matrix)
   2. [SQL that populates it](#42-the-sql-that-populates-it-link-to-module-3)
5. [Anomaly Flagging](#5-anomaly-flagging)
   1. [Threshold-based alerting logic](#51-threshold-based-alerting-logic)
   2. [Visual convention for flagging anomalous cells](#52-visual-convention-for-flagging-anomalous-cells)

**Core job:** pick the right chart for the business question, and design the backend model so the dashboard doesn't need a full scan to render.

- Hierarchy: Executive KPIs → dimensional drill-downs → granular events.
- Line charts for trends; funnels for ordered conversion; cohort heatmaps (D1/D7/D30) for retention.

### 1. Dashboard Architecture

Dashboarding questions are usually about two things at once:

1. Can you choose the right visual for the business question?
2. Can you design the data model so the BI layer is fast, stable, and explainable?

A strong DE answer starts with a layered serving model rather than a single monolithic table.

#### 1.1 KPI layer vs. drill-down layer vs. raw-event layer

- **KPI layer**: compact pre-aggregated tables for top-line metrics such as DAU, watch time, impressions, shares, revenue.
- **Drill-down layer**: dimensions like country, device, surface, creator segment, campaign, or experiment arm.
- **Raw-event layer**: immutable facts used for audits, backfills, and incident investigation.

Think in terms of query paths:

```text
Executive dashboard → KPI mart
Product analyst drill-down → dimensional aggregate mart
Root-cause investigation → raw event tables
```

If an executive chart requires a full scan of raw events each refresh, the backend model is wrong.

#### 1.2 Pre-aggregation strategy

Pre-aggregation is not an optimization afterthought; it is the primary design choice.

Good pre-aggregation rules:

- Precompute at the **lowest grain that supports expected drill-downs**.
- Keep dimensions stable and business-defined.
- Store additive metrics when possible.
- Materialize the funnel/cohort math into backing tables instead of letting the BI tool do it ad hoc.

Common pattern:

| Layer | Grain | Example |
|---|---|---|
| KPI mart | `ds` | daily total Reel impressions |
| Drill-down mart | `ds, country, app_surface` | daily impressions by country and surface |
| Raw facts | `event_id` | every impression event |

### 2. Chart Selection

#### 2.1 When to use line vs. bar vs. funnel vs. cohort heatmap

- **Line chart**: trend over time; use for DAU, watch time, revenue, latency, or null-rate monitoring.
- **Bar chart**: compare categories at one point in time; use for country mix, device mix, or top creators.
- **Funnel**: ordered attrition through a sequence; use when step order matters and denominators should be explicit.
- **Cohort heatmap**: retention over time since a cohort started; use when behavior needs to be normalized by signup or acquisition date.

Interview trap to avoid: do not use a pie chart for high-cardinality comparisons and do not use a funnel for unordered event counts.

### 3. Funnel Design

Funnel example:
```
Reel Impression        ████████████████████████████ 100%  (10.0M)
Watched > 3s           ████████████████             58%   (5.8M)
Liked / Commented      ████                         12%   (1.2M)
Shared                 █                             3%   (0.3M)
```

The chart is the easy part. The real design question is what table backs it.

#### 3.1 Backing table schema for a funnel

There are two common designs.

**Option A — one row per user per funnel step per day**

Schema:

```sql
fact_reel_funnel_user_day(
    ds DATE,
    user_id STRING,
    funnel_name STRING,
    step_name STRING,
    step_order INT,
    reached_step BOOLEAN,
    first_step_ts TIMESTAMP
)
```

Example rows:

| ds | user_id | funnel_name | step_name | step_order | reached_step | first_step_ts |
|---|---|---|---|---:|---|---|
| 2026-07-28 | `u_101` | `reel_engagement` | `impression` | 1 | true | `2026-07-28 09:01:00` |
| 2026-07-28 | `u_101` | `reel_engagement` | `watched_3s` | 2 | true | `2026-07-28 09:01:04` |
| 2026-07-28 | `u_101` | `reel_engagement` | `liked_or_commented` | 3 | false | `NULL` |
| 2026-07-28 | `u_101` | `reel_engagement` | `shared` | 4 | false | `NULL` |

Pros:

- Supports user-level drill-down and re-segmentation later.
- Lets you ask questions like "which users watched but did not share?"

Cons:

- Larger storage footprint.
- Dashboard queries need an aggregation step.

**Option B — one row per step per day with aggregated counts**

Schema:

```sql
agg_reel_funnel_day(
    ds DATE,
    funnel_name STRING,
    step_name STRING,
    step_order INT,
    user_count BIGINT,
    prior_step_user_count BIGINT,
    conversion_rate_from_prior DOUBLE,
    conversion_rate_from_entry DOUBLE
)
```

Example rows:

| ds | funnel_name | step_name | step_order | user_count | prior_step_user_count | conversion_rate_from_prior | conversion_rate_from_entry |
|---|---|---|---:|---:|---:|---:|---:|
| 2026-07-28 | `reel_engagement` | `impression` | 1 | 10000000 | 10000000 | 1.00 | 1.00 |
| 2026-07-28 | `reel_engagement` | `watched_3s` | 2 | 5800000 | 10000000 | 0.58 | 0.58 |
| 2026-07-28 | `reel_engagement` | `liked_or_commented` | 3 | 1200000 | 5800000 | 0.21 | 0.12 |
| 2026-07-28 | `reel_engagement` | `shared` | 4 | 300000 | 1200000 | 0.25 | 0.03 |

Pros:

- Fastest for dashboards.
- Very small table.
- Explicitly stores the denominators the chart needs.

Cons:

- No user-level drill-down.
- Less flexible if stakeholders later ask for segmentation the table did not precompute.

Interview answer: choose **Option A** if analysis flexibility matters, **Option B** if the dashboard is stable and latency-sensitive. Many production systems keep both: a user-grain fact table plus a smaller aggregate serving table.

#### 3.2 The SQL that populates it (link to Module 3)

This is structurally the same as a SQL funnel question from Module 3: identify the earliest timestamp for each step, preserve the step order, then aggregate.

Example user-grain build:

```sql
WITH impression AS (
    SELECT
        DATE(event_ts) AS ds,
        user_id,
        MIN(event_ts) AS first_step_ts,
        'impression' AS step_name,
        1 AS step_order
    FROM fact_reel_impressions
    GROUP BY 1,2
),
watched_3s AS (
    SELECT
        DATE(event_ts) AS ds,
        user_id,
        MIN(event_ts) AS first_step_ts,
        'watched_3s' AS step_name,
        2 AS step_order
    FROM fact_reel_watch
    WHERE watch_time_ms >= 3000
    GROUP BY 1,2
),
liked_or_commented AS (
    SELECT
        DATE(event_ts) AS ds,
        user_id,
        MIN(event_ts) AS first_step_ts,
        'liked_or_commented' AS step_name,
        3 AS step_order
    FROM fact_reel_engagement
    WHERE engagement_type IN ('like', 'comment')
    GROUP BY 1,2
),
shared AS (
    SELECT
        DATE(event_ts) AS ds,
        user_id,
        MIN(event_ts) AS first_step_ts,
        'shared' AS step_name,
        4 AS step_order
    FROM fact_reel_engagement
    WHERE engagement_type = 'share'
    GROUP BY 1,2
),
unioned AS (
    SELECT * FROM impression
    UNION ALL
    SELECT * FROM watched_3s
    UNION ALL
    SELECT * FROM liked_or_commented
    UNION ALL
    SELECT * FROM shared
)
SELECT
    ds,
    user_id,
    'reel_engagement' AS funnel_name,
    step_name,
    step_order,
    TRUE AS reached_step,
    first_step_ts
FROM unioned;
```

From there, the aggregate serving table is just a `GROUP BY ds, funnel_name, step_name, step_order` plus window logic for prior-step denominators.

### 4. Retention/Cohort Design

Cohort retention:
| Cohort | Users | D0 | D1 | D7 | D30 |
|---|---|---|---|---|---|
| 2026-06-01 | 100,000 | 100% | 42% | 28% | 18% |
| 2026-06-02 | 105,000 | 100% | 44% | 29% | 19% |
| 2026-06-03 | 98,000 | 100% | 39% | 25% | **15% — drop to investigate** |

That last row is deliberately planted — if you're presented a table like this, the interview wants you to notice the anomaly and propose the Module 1 diagnostic tree unprompted.

#### 4.1 Backing table schema for a cohort matrix

The cleanest backing table is one row per `(cohort_date, day_offset)`.

Schema:

```sql
agg_user_retention_cohort(
    cohort_date DATE,
    day_offset INT,
    user_count BIGINT,
    retained_count BIGINT,
    retention_rate DOUBLE
)
```

Example rows:

| cohort_date | day_offset | user_count | retained_count | retention_rate |
|---|---:|---:|---:|---:|
| 2026-06-01 | 0 | 100000 | 100000 | 1.00 |
| 2026-06-01 | 1 | 100000 | 42000 | 0.42 |
| 2026-06-01 | 7 | 100000 | 28000 | 0.28 |
| 2026-06-01 | 30 | 100000 | 18000 | 0.18 |
| 2026-06-03 | 30 | 98000 | 14700 | 0.15 |

How the named cells are defined:

- **D1** = users active 1 day after cohort start / users in cohort
- **D7** = users active 7 days after cohort start / users in cohort
- **D30** = users active 30 days after cohort start / users in cohort

The heatmap UI typically pivots `day_offset` across columns, but the backing table should stay normalized.

#### 4.2 The SQL that populates it (link to Module 3)

A standard pattern:

```sql
WITH first_seen AS (
    SELECT
        user_id,
        MIN(DATE(event_ts)) AS cohort_date
    FROM fact_user_activity
    GROUP BY 1
),
activity_days AS (
    SELECT DISTINCT
        user_id,
        DATE(event_ts) AS activity_date
    FROM fact_user_activity
),
retention_events AS (
    SELECT
        f.cohort_date,
        DATE_DIFF('day', f.cohort_date, a.activity_date) AS day_offset,
        f.user_id
    FROM first_seen f
    JOIN activity_days a
      ON f.user_id = a.user_id
    WHERE a.activity_date >= f.cohort_date
),
cohort_sizes AS (
    SELECT cohort_date, COUNT(*) AS user_count
    FROM first_seen
    GROUP BY 1
),
retained AS (
    SELECT
        cohort_date,
        day_offset,
        COUNT(DISTINCT user_id) AS retained_count
    FROM retention_events
    GROUP BY 1,2
)
SELECT
    r.cohort_date,
    r.day_offset,
    c.user_count,
    r.retained_count,
    r.retained_count * 1.0 / c.user_count AS retention_rate
FROM retained r
JOIN cohort_sizes c
  ON r.cohort_date = c.cohort_date;
```

Again, this is a Module 3 SQL pattern wrapped in a dashboard-serving use case.

### 5. Anomaly Flagging

Dashboards should not just display numbers; they should help operators notice when a number is abnormal.

#### 5.1 Threshold-based alerting logic

A simple threshold rule might say:

- alert if D30 retention drops below 16%, or
- alert if D30 retention falls more than 3 percentage points day-over-day.

These are easy to explain and stable when the metric has strong seasonality controls elsewhere.

The more adaptive rule from the prompt is statistical:

> Flag any cell where `retention_rate < trailing_4_week_avg_retention - 2 * stddev`.

Worked SQL example for D30 retention:

```sql
WITH d30 AS (
    SELECT
        cohort_date,
        retention_rate
    FROM agg_user_retention_cohort
    WHERE day_offset = 30
),
baseline AS (
    SELECT
        cohort_date,
        retention_rate,
        AVG(retention_rate) OVER (
            ORDER BY cohort_date
            ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
        ) AS trailing_4_week_avg_retention,
        STDDEV_SAMP(retention_rate) OVER (
            ORDER BY cohort_date
            ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING
        ) AS trailing_4_week_stddev
    FROM d30
)
SELECT
    cohort_date,
    retention_rate,
    trailing_4_week_avg_retention,
    trailing_4_week_stddev,
    CASE
        WHEN trailing_4_week_avg_retention IS NULL THEN FALSE
        WHEN retention_rate < trailing_4_week_avg_retention - 2 * trailing_4_week_stddev THEN TRUE
        ELSE FALSE
    END AS is_alert
FROM baseline
ORDER BY cohort_date;
```

How this would flag the planted example:

- Suppose recent D30 cohorts averaged ~18.5% with a standard deviation of ~1.2%.
- Alert threshold = `18.5% - 2 * 1.2% = 16.1%`.
- The `2026-06-03` D30 value of `15%` falls below that threshold.
- Result: the dashboard cell is flagged automatically.

Threshold-based vs. statistical alerting:

- **Threshold-based** is simpler, easier to explain, and better when the business already has a known failure boundary.
- **Statistical alerting** adapts better to historical variance and is more useful when "normal" drifts over time.
- In practice, teams often use both: a hard floor for severe incidents and a rolling anomaly detector for earlier warning.

#### 5.2 Visual convention for flagging anomalous cells

Good visual conventions:

- Use a consistent color treatment such as red text or a red cell border.
- Add an icon or annotation, not just a color shift, so the alert survives grayscale exports and accessibility constraints.
- Show the comparison baseline in a tooltip: current value, trailing mean, standard deviation, and z-score.

Example convention:

- Normal cell: `18%`
- Warning cell: `15% ⚠ (2.9σ below trailing mean)`

That is what turns a dashboard from a reporting artifact into an operational tool.
