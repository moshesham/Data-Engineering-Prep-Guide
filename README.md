# Meta Data Engineer Interview — Unified Study Guide

## How to Use This Guide

The source material treats Product Sense, Data Modeling, SQL, and Python as separate modules. In the actual onsite, they are **not separate** — each of the three "Blended" rounds throws all four at you inside one 45-minute conversation, in this order:

```
Product framing  →  Event payload  →  Star schema  →  SQL query  →  (sometimes) Python transform
   (2–3 min)          (5 min)          (8–10 min)      (15 min)          (10 min)
```

The interviewer is grading whether your SQL and your schema are *consistent with the metric you defined two minutes earlier* — not whether each piece is correct in isolation. Most candidates lose points not on syntax but on drift: they define a metric in Module 1 language, then write a query in Module 3 that silently answers a different question. Treat Modules 1–4 below as one skill, not four.

**Loop structure:**

```
Recruiter Screen (30 min)
        │
        ▼
Technical Screen (60 min — 5 SQL + 5 Python, speed round)
        │
        ▼
Onsite (4–5 rounds)
   ├─ 3× Blended round: Product Sense → Data Model → SQL → Python
   └─ 1× Behavioral & Ownership (STAR)
```

**Where your background maps directly.** Your stack (Iceberg, Snowflake, PySpark, Airflow, Kafka, Databricks) is functionally equivalent to what these rounds test — use it, don't translate it away:

| This guide says | You already run |
| :--- | :--- |
| Partitioned fact tables, `ds` scan pruning | Iceberg partitioning / Snowflake micro-partitions |
| Batch (Spark/Presto) | PySpark on Databricks |
| Streaming (Kafka/Flink) | Kafka |
| Idempotent backfill via staging + atomic swap | Iceberg snapshot/merge-on-read, Airflow-orchestrated backfills |
| DAG-based orchestration | Airflow |

The gap for you is almost never the engineering concept — it's translating credit-risk/fraud framing into consumer-social-product framing (DAU/retention instead of default rates, Reels watch time instead of transaction volume). Practice that translation explicitly; it's the actual thing being tested.

---

## Module 1 — Product Sense & Metrics

**Core job:** turn ambiguous product intent into a measurable, defensible metric, then know how to explain a metric that moved.

**Metric toolkit:**
- **North Star metrics** — the one number that matters long-term (e.g., Reels watch time, 15-day active creators).
- **L1/L2 decomposition** — break the North Star into levers: `DAU = New + Retained + Resurrected`.
- **Guardrails** — the metric you're *not* trying to move but must not break (ad load ↑ revenue but watch guardrail on uninstalls / D30 retention).
- **Ratios vs. totals** — ratios (CTR) normalize for traffic changes; totals measure gross scale. State which one you're optimizing and why.

**Root-cause framework for a metric drop** — always split into two branches before you start guessing:

```
Metric Drop Identified (e.g., Reels Watch Time -8%)
        │
   ┌────┴─────────────────────────┐
   ▼                              ▼
Technical/Data check       Product/Market check
- pipeline latency /       - regional or OS-specific?
  broken DAG                 (iOS vs. Android)
- missing logs / schema    - bad app release / build
  drift                      version bug?
- dedup logic failing      - external (holiday, outage,
                              competitor launch)?
```

**Worked example — "Daily Active Creators dropped 6% globally in 48 hours":**
1. Verify it's real user behavior, not a pipeline delay (DAG lag, missing ingestion batch, broken dedup).
2. Segment: device/OS/app-version, and creator tenure (new vs. power creators) — friction often hits one cohort, not everyone.
3. Form competing hypotheses and say which data would falsify each:
   - *Technical:* client logging failed to emit `reel_upload_success` on Android v312.0.
   - *Product:* a ranking change cut impression reach for new creators, killing posting motivation.
4. Resolve with a query: event volume by `app_version` and `device_os` over 72 hours.

**Interview habit to practice:** state your metric definition out loud in one sentence *before* touching the schema or SQL. If you can't state it in one sentence, you don't have a metric yet — you have a topic.

---

## Module 2 — Data Modeling & Schema Design

**Core job:** design a model that supports the metric from Module 1 without needing a Cartesian join to compute it.

**Fact table types:**
- *Transaction facts* — one row per event (a purchase, a reel view).
- *Periodic snapshots* — one row per entity per period (daily account state).
- *Accumulating snapshots* — one row per entity, updated as it moves through a lifecycle (order fulfillment).

**Dimension design:**
- Surrogate keys (integer, monotonic) for join performance and history tracking — never join on natural keys you don't control.
- **Slowly Changing Dimensions:**
  - *Type 1 (overwrite)* — no history kept; fine for a typo fix.
  - *Type 2 (row versioning)* — `effective_start_ds`, `effective_end_ds`, `is_current`; use whenever "what did the user look like on that date" matters.
  - *Type 3 (extra column)* — keep prior + current value side by side; rare, used for single-attribute history.

**Scale mechanics:** partition by `ds` to bound scans; cluster/bucket on high-cardinality join keys (`user_id`) to avoid cross-node shuffles. If you don't mention partition pruning when asked "how would this run at Meta's volume," that's a flag.

**End-to-end example — logs → data mart:**

Raw client payload:
```json
{
  "event_id": "evt_8f93a1c2-9012-4b33",
  "event_type": "reel_view",
  "timestamp_ms": 1774191600000,
  "user_id": 98401293,
  "device_info": { "os": "iOS", "os_version": "17.4", "app_version": "312.0.0" },
  "payload": {
    "reel_id": 449102941,
    "creator_id": 1029384,
    "watch_time_ms": 14200,
    "reel_length_ms": 15000,
    "completed": true
  }
}
```

Star schema built from it:

```
        dim_user (SCD Type 2)                       dim_creator
   PK user_key, user_id, country,            PK creator_id, creator_name, tier
      registration_date, start_ds,
      end_ds, is_current
              │
              │ 1:N
              ▼
   ┌───────────────────────────────────────────┐
   │          fact_reel_impressions             │
   │  FK reel_id, FK user_key, FK creator_id    │
   │      event_timestamp, watch_time_ms,        │
   │      is_completed                           │
   │  PK,FK ds (partition key)                   │
   └───────────────────────────────────────────┘
              ▲
              │ 1:N
        dim_reel
   PK reel_id, creator_id, duration_ms, created_ds
```

`dim_user` Type-2 state — this is the row shape to draw from memory in an interview:

| user_key (PK) | user_id | country | start_ds | end_ds | is_current |
|---|---|---|---|---|---|
| 1001 | 98401293 | US | 2024-01-01 | 2026-03-14 | FALSE |
| 1002 | 98401293 | UK | 2026-03-15 | 9999-12-31 | TRUE |

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

---

## Module 4 — Python & Pipeline Scripting

**Core job:** solve with standard-library structures (`dict`, `set`, `list`) — Meta's Python round is not a Pandas round.

**Pattern inventory:**
- `dict` for O(1) lookups, JSON parsing, grouping, frequency counting.
- `set` for dedup and relationship operations (intersections/differences).
- `list`/`tuple` for sorting with `key=lambda x: x[1]`, slicing, comprehensions.
- Interval/overlap merges, string/log parsing, native `GROUP BY` via nested dicts, sliding-window rolling metrics.
- Defensive habits: handle `[]`, `None`, malformed rows, and use `dict.get(key, default)` instead of bare indexing.

**Worked problem:** merge overlapping session intervals and compute total non-overlapping active time.

```
Input:   [1,4], [3,6], [8,10], [10,12]
Merged:  [1,6], [8,12]  →  Active time = (6-1) + (12-8) = 9
```

```python
def calculate_total_active_time(intervals: list[list[int]]) -> int:
    """
    Merge overlapping intervals and sum active duration.
    Time: O(N log N) from the sort. Space: O(N).
    """
    if not intervals:
        return 0

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for start, end in sorted_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1][1] = max(prev_end, end)
        else:
            merged.append([start, end])

    return sum(end - start for start, end in merged)


if __name__ == "__main__":
    print(calculate_total_active_time([[1, 4], [3, 6], [8, 10], [10, 12]]))  # 9
```

Say the complexity out loud unprompted (`O(N log N)`, driven by the sort) — it signals you're not pattern-matching from memory.

---

## Module 5 — Pipeline Reliability, Batch & Streaming

**Core job:** show you know what breaks at scale and how you'd design around it before it does.

| Pattern | Best for | Pros | Cons |
|---|---|---|---|
| Batch (Spark/Presto) | Daily/hourly aggregation, heavy joins | High throughput, cheap, easy backfills | Latency in minutes–hours |
| Streaming (Kafka/Flink) | Real-time fraud/anomaly, live counters | Millisecond latency | Complex state, hard to backfill |
| Lambda | Real-time views + accurate batch truth | Best of both | Two pipelines to maintain — real ongoing cost |

**Idempotent backfill pattern** — this is the answer to almost every "how would you safely reprocess history" question:

```
Run Spark backfill (batch)
        │
        ▼
Write to staging partition (ds = '2026-07-20'_staging)
        │
        ▼
Run data-quality checks (row counts, non-null PKs, schema)
        │
   ┌────┴────┐
   ▼          ▼
 Pass       Fail
   │          │
Atomic     Abort +
swap to    alert
target ds  monitoring
```

Other things to have ready: late-arriving mobile logs (design for out-of-order arrival, not just out-of-order processing), and lineage tracking so you can say which downstream dashboards break if an upstream table changes shape.

---

## Module 6 — AI/ML Infrastructure

**Core job:** show you understand the infra a DE builds *for* ML teams, not that you build the models.

- **Feature stores** — one source of truth serving both low-latency online inference and offline batch training; the failure mode to name is **training-serving skew** (the feature computed differently in the two paths).
- **Vector embeddings** — unstructured content (text/image) converted to vectors for similarity-based recommendation; you don't need to build the model, but you should be able to describe where the embedding pipeline sits relative to the feature store.
- **Feature drift** — baseline distribution shift between training and current serving traffic; name it as a data-quality problem, not just a modeling problem.

```
Client events → Kafka/Flink → Feature store → ML inference
                    │                              ▲
                    ▼                              │
              Batch data lake ─────────────────────┘
              (offline training set)
```

---

## Module 7 — Dashboards & Reporting

**Core job:** pick the right chart for the business question, and design the backend model so the dashboard doesn't need a full scan to render.

- Hierarchy: Executive KPIs → dimensional drill-downs → granular events.
- Line charts for trends; funnels for ordered conversion; cohort heatmaps (D1/D7/D30) for retention.

Funnel example:
```
Reel Impression        ████████████████████████████ 100%  (10.0M)
Watched > 3s           ████████████████             58%   (5.8M)
Liked / Commented      ████                         12%   (1.2M)
Shared                 █                             3%   (0.3M)
```

Cohort retention:
| Cohort | Users | D0 | D1 | D7 | D30 |
|---|---|---|---|---|---|
| 2026-06-01 | 100,000 | 100% | 42% | 28% | 18% |
| 2026-06-02 | 105,000 | 100% | 44% | 29% | 19% |
| 2026-06-03 | 98,000 | 100% | 39% | 25% | **15% — drop to investigate** |

That last row is deliberately planted — if you're presented a table like this, the interview wants you to notice the anomaly and propose the Module 1 diagnostic tree unprompted.

---

## Module 8 — Behavioral & Ownership

**Core job:** STAR, with the "A" doing most of the work — interviewers weight the technical actions you personally took over the outcome.

```
S — Situation   business context, scale, the technical problem
T — Task        your specific responsibility
A — Action      the technical + cross-functional steps YOU took
R — Result      quantified outcome (latency, cost, reliability)
```

**Reference example — "a critical pipeline flaw you took ownership of":**
- *Situation:* a core revenue dashboard ran 4 hours late every Monday, delaying ad-inventory decisions.
- *Task:* find the root cause and redesign the pipeline to a 6:00 AM daily SLA.
- *Action:* traced a Cartesian join from unpartitioned weekend updates; rebuilt from full-table overwrites to incremental `ds` partition updates in Spark; replaced runtime `DISTINCT` with pre-aggregated staging tables; got upstream teams to make `event_id` a required logging field for dedup.
- *Result:* 75% reduction in processing time, SLA met consistently.

Meta's stated values to map stories to: **Focus on Impact**, **Move Fast** (iterate without letting technical debt go unmanaged), **Be Bold / Ownership** (accountability for accuracy and cross-functional outcomes).

---

## Module 9 — Apache Spark: ETL Development Reference

**Core job:** everything in Modules 2–5 gets implemented in Spark. This module goes from baseline syntax through the configs and patterns that separate "can write a job" from "can be trusted with a production pipeline at scale."

### 1. Mental Model First

DataFrame operations are **lazy** — nothing executes until an action (`.collect()`, `.count()`, `.write()`) forces Catalyst to plan and Tungsten to execute. Interviewers listen for whether you reason about the *physical plan*, not just the API call. Always be ready to say "I'd check `.explain(True)` here" when asked about performance.

Stick to the DataFrame/Dataset API. RDDs only come up if someone explicitly asks about internals (partitioning, lineage, `mapPartitions`).

### 2. Canonical ETL Skeleton (Extract → Transform → Load)

This is the shape every take-home and whiteboard Spark question reduces to. Note how it reuses the exact idempotency, partitioning, and window-function decisions from Modules 2–3 — same query, Spark syntax:

```python
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("reel_impressions_etl").getOrCreate()

# Extract
raw_df = (
    spark.read
    .format("json")
    .load("s3://meta-raw-events/reel_view/ds=2026-07-20/")
)

# Transform
clean_df = (
    raw_df
    .select(
        F.col("event_id"),
        F.col("user_id"),
        F.col("payload.creator_id").alias("creator_id"),
        F.col("payload.watch_time_ms").alias("watch_time_ms"),
        F.col("payload.completed").alias("is_completed"),
        F.to_date((F.col("timestamp_ms") / 1000).cast("timestamp")).alias("ds"),
    )
    .filter(F.col("watch_time_ms").isNotNull())
    .dropDuplicates(["event_id"])          # idempotency guard, same role as SQL dedup logic
)

daily_watch = (
    clean_df
    .groupBy("user_id", "ds")
    .agg(F.sum("watch_time_ms").alias("total_daily_watch_ms"))
)

w = Window.partitionBy("user_id").orderBy("ds").rowsBetween(-2, 0)
rolling = daily_watch.withColumn(
    "rolling_3d_avg_watch_ms", F.avg("total_daily_watch_ms").over(w)
)

# Load
(
    rolling.write
    .format("iceberg")
    .mode("overwrite")
    .partitionBy("ds")
    .saveAsTable("analytics.fact_user_watch_rolling")
)
```

### 3. Syntax Inventory (know these without looking up docs)

| Category | Calls |
|---|---|
| Column ops | `select`, `withColumn`, `drop`, `withColumnRenamed` |
| Row filtering | `filter` / `where` (identical), `isNotNull`, `isin` |
| Aggregation | `groupBy(...).agg(F.sum(...), F.avg(...), F.countDistinct(...))` |
| Joins | `inner`, `left`, `right`, `full`, `left_semi`, `left_anti`, `broadcast(df)` hint |
| Conditional | `F.when(cond, val).otherwise(default)` |
| Nested/array data | `F.explode`, `F.col("a.b.c")` for struct access, `F.from_json` |
| Window | `Window.partitionBy().orderBy().rowsBetween(-2, 0)` / `.rangeBetween(...)`, `F.rank()`, `F.dense_rank()`, `F.row_number()`, `F.lead()`, `F.lag()` |
| UDFs | Only when no native function exists — a Python UDF breaks Catalyst's optimizer and pays serialization cost every row. Prefer `pandas_udf` (vectorized) over a plain `udf` if you must. |

### 4. Configs Worth Knowing Cold

These come up both as "what would you tune" interview questions and as real production levers:

| Config | What it controls |
|---|---|
| `spark.sql.shuffle.partitions` | Partition count after a shuffle (default 200) — too low under-parallelizes, too high adds scheduling overhead |
| `spark.sql.adaptive.enabled` (AQE) | Runtime re-planning: coalesces small post-shuffle partitions, converts joins when actual sizes are known |
| `spark.sql.adaptive.skewJoin.enabled` | Auto-splits skewed partitions during a join under AQE |
| `spark.sql.autoBroadcastJoinThreshold` | Table size (default 10MB) below which Spark broadcasts instead of shuffling; set `-1` to force a shuffle join |
| `spark.executor.memory` / `spark.executor.memoryOverhead` | JVM heap vs. off-heap (native/PySpark process) memory per executor — OOMs are usually an overhead problem, not a heap problem |
| `spark.executor.cores` | Task parallelism per executor; too high causes contention on shared executor memory |
| `spark.dynamicAllocation.enabled` | Elastic executor count between `minExecutors`/`maxExecutors` based on pending tasks |
| `spark.sql.files.maxPartitionBytes` | Target input split size when reading — controls initial task count on read |
| `spark.serializer` | Set to `KryoSerializer`; materially faster than the Java default for shuffles |

**Interview answer pattern:** if asked "the job is slow, what do you check" — walk the list in this order: (1) `explain()` the physical plan, (2) look for data skew in the shuffle stage (Spark UI stage view, task duration variance), (3) check partition count vs. cluster parallelism, (4) check for an unintended shuffle-heavy join that should've been broadcast, (5) check serialization and caching. Naming the order matters more than naming every config.

### 5. Handling Skew & Tuning Joins

- **Salting** — append a random suffix (`0`–`N`) to a skewed join key on both sides, join on `(key, salt)`, then aggregate away the salt. Standard fix when AQE skew-join handling isn't enough (e.g., pre-3.x clusters, or skew inside a single AQE partition).
- **Broadcast vs. shuffle join** — force a broadcast (`F.broadcast(small_df)`) for a dimension table that fits in memory; avoids shuffling the large fact table entirely.
- **`repartition` vs. `coalesce`** — `repartition(n)` does a full shuffle and can increase or decrease partitions; `coalesce(n)` only decreases partitions and avoids a full shuffle by merging adjacent ones. Use `coalesce` before a write when you over-partitioned upstream.
- **Cache/persist deliberately** — `df.persist(StorageLevel.MEMORY_AND_DISK)` when a DataFrame is reused across multiple actions; always `unpersist()` when done, or it silently holds executor memory for the rest of the job.

### 6. Complex ETL Patterns

**Idempotent upsert / merge (Iceberg or Delta syntax)** — this is the production version of the Module 5 backfill pattern:

```python
from delta.tables import DeltaTable

target = DeltaTable.forName(spark, "analytics.dim_user")

(
    target.alias("t")
    .merge(clean_df.alias("s"), "t.user_id = s.user_id AND t.is_current = true")
    .whenMatchedUpdate(set={
        "end_ds": "s.effective_start_ds",
        "is_current": "false",
    })
    .execute()
)

# then insert the new current row separately (two-step Type-2 merge)
new_rows = clean_df.withColumn("is_current", F.lit(True))
new_rows.write.format("delta").mode("append").saveAsTable("analytics.dim_user")
```

**Structured Streaming — windowed aggregation with watermarking** (the streaming counterpart to the rolling-average query from Module 3):

```python
stream_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka-broker:9092")
    .option("subscribe", "reel_view_events")
    .load()
)

parsed = (
    stream_df
    .select(F.from_json(F.col("value").cast("string"), event_schema).alias("data"))
    .select("data.*")
)

windowed = (
    parsed
    .withWatermark("event_timestamp", "10 minutes")   # tolerate 10 min of late arrival
    .groupBy(F.window("event_timestamp", "5 minutes"), "creator_id")
    .agg(F.sum("watch_time_ms").alias("watch_ms_5min"))
)

query = (
    windowed.writeStream
    .outputMode("update")
    .option("checkpointLocation", "s3://checkpoints/reel_watch_5min/")
    .trigger(processingTime="1 minute")
    .start()
)
```

Two details interviewers probe on: **watermarking** (how late data is tolerated before a window is finalized — this *is* the Module 5 "late-arriving data" concept, implemented) and **checkpointing** (where offsets and state live so a restart resumes exactly, not from zero — this *is* the idempotency concept, for streaming).

**Testing an ETL job:** build small, explicit in-memory DataFrames (`spark.createDataFrame([...], schema)`) and assert on the output rather than running against production data — schema mismatches and null-handling bugs are the two things worth writing a test for first.

### 7. How This Shows Up in the Loop

If a "blended" round asks you to implement the SQL query from Module 3 in Spark, the fastest credible path is: mirror the CTEs as chained DataFrame transformations 1:1 (pre-aggregate → window → filter), narrate the partition/shuffle implications as you go, and mention `dropDuplicates` on `event_id` before any aggregation — the same idempotency point graders look for in the SQL round.

---

## 4-Week Study Plan

| Week | Focus | Modules | Goal |
|---|---|---|---|
| 1 | Screening speed | 3, 4, 9 | 5 SQL + 5 Python in 60-min timed blocks; window functions and dict-based aggregation cold; rewrite one SQL solution as a PySpark DataFrame chain |
| 2 | Modeling | 2 | Star schemas for 5 Meta surfaces (Reels, Marketplace, Messages, Ads, Stories); SCD Type 2 merge logic from memory |
| 3 | Product sense | 1, 6, 7 | Full loop out loud: metric → payload → schema → query, end to end; RCA trees for metric drops |
| 4 | Reliability + behavioral | 5, 8 | Idempotency/backfill/partitioning talking points; 5 STAR stories mapped to Meta's values |

---

## One-Page Recall Sheet

- **Metric hierarchy:** North Star → L1/L2 drivers → guardrails. State the one-sentence metric definition before anything else.
- **RCA split:** technical/data check vs. product/market check — always both branches.
- **SCD:** Type 1 overwrite, Type 2 versioned (`start_ds`/`end_ds`/`is_current`), Type 3 extra column.
- **Fact types:** transaction, periodic snapshot, accumulating snapshot.
- **Scale:** partition by `ds`, cluster on join keys, watch for fan-out on non-unique join keys.
- **Window functions:** `ROW_NUMBER`/`RANK`/`DENSE_RANK` for top-N, `LEAD`/`LAG` for deltas, explicit frame for rolling windows.
- **Batch vs. streaming vs. Lambda:** throughput/cost vs. latency vs. dual-pipeline maintenance cost.
- **Idempotent backfill:** staging partition → data-quality gate → atomic swap or abort-and-alert.
- **STAR:** weight the Action; quantify the Result.
- **Spark tuning order when asked "why is this slow":** `explain()` plan → check skew → partition count vs. parallelism → unnecessary shuffle/join strategy → serialization/caching.
- **Spark configs to name on demand:** `shuffle.partitions`, AQE (`adaptive.enabled`, `adaptive.skewJoin.enabled`), `autoBroadcastJoinThreshold`, `executor.memoryOverhead`, `dynamicAllocation.enabled`.
- **`repartition` (full shuffle, can increase) vs. `coalesce` (merge only, decreases, no full shuffle).**
