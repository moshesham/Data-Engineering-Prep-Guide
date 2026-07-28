---
layout: default
title: Module 9 — Apache Spark ETL Development Reference
permalink: /modules/spark-etl/
---



## Module 9 — Apache Spark: ETL Development Reference

## Table of Contents
1. [Mental Model First](#1-mental-model-first-existing)
2. [Canonical ETL Skeleton](#2-canonical-etl-skeleton-existing)
3. [Syntax Inventory](#3-syntax-inventory-existing)
4. [Configs Worth Knowing Cold](#4-configs-worth-knowing-cold-existing)
5. [Handling Skew & Tuning Joins](#5-handling-skew--tuning-joins-existing)
6. [Complex ETL Patterns](#6-complex-etl-patterns-existing--new)
   1. [Idempotent upsert / merge](#61-idempotent-upsert--merge-existing)
   2. [Structured Streaming with watermarking](#62-structured-streaming-with-watermarking-existing)
   3. [Unit-testing an ETL job](#63-unit-testing-an-etl-job-existing)
   4. [Small-file problem and compaction](#64-small-file-problem-and-compaction-new)
   5. [Airflow-to-Spark orchestration](#65-airflow-to-spark-orchestration-new)
   6. [pandas_udf — vectorized UDF alternative](#66-pandas_udf--vectorized-udf-alternative-new)
7. [Debugging](#7-debugging-new-section)
   1. [Reading the Spark UI to spot skew](#71-reading-the-spark-ui-to-spot-skew)
   2. [Common OOM causes and fixes](#72-common-oom-causes-and-fixes)
8. [How This Shows Up in the Loop](#8-how-this-shows-up-in-the-loop)

**Core job:** everything in Modules 2–5 gets implemented in Spark. This module goes from baseline syntax through the configs and patterns that separate "can write a job" from "can be trusted with a production pipeline at scale."

### 1. Mental Model First (existing)

DataFrame operations are **lazy** — nothing executes until an action (`.collect()`, `.count()`, `.write()`) forces Catalyst to plan and Tungsten to execute. Interviewers listen for whether you reason about the *physical plan*, not just the API call. Always be ready to say "I'd check `.explain(True)` here" when asked about performance.

Stick to the DataFrame/Dataset API. RDDs only come up if someone explicitly asks about internals (partitioning, lineage, `mapPartitions`).

A good mental shortcut:

- **read** defines your starting partitioning and file scan cost
- **transform** determines whether you trigger narrow ops or shuffles
- **join / aggregate / window** are where most expensive stages appear
- **write** determines downstream layout quality as much as current-job success

### 2. Canonical ETL Skeleton (existing)

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

### 3. Syntax Inventory (existing)

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

### 4. Configs Worth Knowing Cold (existing)

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

### 5. Handling Skew & Tuning Joins (existing)

- **Salting** — append a random suffix (`0`–`N`) to a skewed join key on both sides, join on `(key, salt)`, then aggregate away the salt. Standard fix when AQE skew-join handling isn't enough (e.g., pre-3.x clusters, or skew inside a single AQE partition).
- **Broadcast vs. shuffle join** — force a broadcast (`F.broadcast(small_df)`) for a dimension table that fits in memory; avoids shuffling the large fact table entirely.
- **`repartition` vs. `coalesce`** — `repartition(n)` does a full shuffle and can increase or decrease partitions; `coalesce(n)` only decreases partitions and avoids a full shuffle by merging adjacent ones. Use `coalesce` before a write when you over-partitioned upstream.
- **Cache/persist deliberately** — `df.persist(StorageLevel.MEMORY_AND_DISK)` when a DataFrame is reused across multiple actions; always `unpersist()` when done, or it silently holds executor memory for the rest of the job.

A practical interview heuristic:

- If the large table is skewed and the small table fits in memory, **broadcast first**.
- If one or two keys dominate even after broadcast is impossible, **salt the heavy keys**.
- If the job writes thousands of tiny files after an otherwise good run, **fix the output partitioning**, not just the upstream shuffle.

### 6. Complex ETL Patterns (existing + new)

#### 6.1 Idempotent upsert / merge (existing)

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

#### 6.2 Structured Streaming with watermarking (existing)

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

#### 6.3 Unit-testing an ETL job (existing)

**Testing an ETL job:** build small, explicit in-memory DataFrames (`spark.createDataFrame([...], schema)`) and assert on the output rather than running against production data — schema mismatches and null-handling bugs are the two things worth writing a test for first.

A minimal structure:

```python
def test_deduplicates_by_event_id(spark_session):
    input_df = spark_session.createDataFrame(
        [
            ("e1", "u1", 1000),
            ("e1", "u1", 1000),
            ("e2", "u1", 500),
        ],
        ["event_id", "user_id", "watch_time_ms"],
    )

    actual = transform_watch_events(input_df)

    assert actual.count() == 2
```

#### 6.4 Small-file problem and compaction (new)

The small-file problem is one of the most common Spark production anti-patterns.

Why it hurts downstream reads:

- **High file-open overhead**: scanning 20,000 tiny Parquet files can spend more time opening files than reading useful data.
- **Poor columnar encoding efficiency**: very small files limit row-group size, so compression and predicate pushdown become less effective.
- **Metastore/catalog pressure**: large numbers of partitions and files slow table planning and metadata operations.
- **Scheduler overhead**: Spark creates more tasks than the workload justifies.

Typical cause: a wide upstream shuffle writes one file per task per partition, and the task count was tuned for compute parallelism rather than output layout.

**Fix 1 — controlled write with `coalesce(n)`**

Use this when you know the target output should be fewer files and you are only decreasing partition count.

```python
(
    daily_watch
    .coalesce(32)
    .write
    .format("parquet")
    .mode("overwrite")
    .partitionBy("ds")
    .save("s3://analytics/fact_user_watch_daily/")
)
```

Use `coalesce` when:

- the dataset is already partitioned enough upstream
- you only need to reduce file count before the write
- you want to avoid an extra full shuffle

If you need to rebalance data more evenly, use `repartition`, but remember that it adds a shuffle.

**Fix 2 — periodic compaction with Delta `OPTIMIZE`**

```python
spark.sql("""
OPTIMIZE analytics.fact_user_watch_daily
WHERE ds >= '2026-07-01'
""")
```

**Fix 3 — periodic compaction with Iceberg `rewrite_data_files`**

```python
spark.sql("""
CALL analytics.system.rewrite_data_files(
    table => 'analytics.fact_user_watch_daily',
    where => 'ds >= DATE ''2026-07-01'''
)
""")
```

Interview phrasing to remember:

- `coalesce(n)` is a **write-time control**
- `OPTIMIZE` / `rewrite_data_files` is a **maintenance-time control**

Good production answer: first prevent the small-file explosion where possible, then run compaction periodically for tables that still accumulate fragmented files due to streaming ingestion or frequent incremental writes.

#### 6.5 Airflow-to-Spark orchestration (new)

This is where Module 5 orchestration concepts become a concrete production DAG.

Requirements:

1. wait for the upstream `fact_reel_impressions` partition to land
2. submit the Spark ETL job
3. run a downstream data-quality check

Complete example:

```python
from datetime import datetime, timedelta

from airflow import DAG
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator


def validate_output_partition(**context):
    ds = context["ds"]
    # Replace with warehouse query, Great Expectations check, or row-count reconciliation.
    # The point of the example is the orchestration shape: dependency gate -> Spark -> DQ.
    if ds is None:
        raise ValueError("Execution date is required")


default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="reel_share_feature_etl",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule_interval="0 6 * * *",
    catchup=True,
    max_active_runs=1,
    tags=["spark", "etl", "reels"],
) as dag:

    wait_for_impressions = ExternalTaskSensor(
        task_id="wait_for_fact_reel_impressions",
        external_dag_id="fact_reel_impressions_pipeline",
        external_task_id="publish_fact_reel_impressions_partition",
        allowed_states=["success"],
        failed_states=["failed", "skipped"],
        execution_delta=timedelta(hours=0),
        timeout=60 * 60,
        poke_interval=300,
        mode="reschedule",
    )

    build_features = SparkSubmitOperator(
        task_id="build_reel_share_features",
        application="jobs/reel_share_feature_etl.py",
        name="reel_share_feature_etl",
        conn_id="spark_default",
        application_args=[
            "--ds", "{{ ds }}",
            "--input-table", "analytics.fact_reel_impressions",
            "--output-table", "ml.feature_reel_share_daily",
        ],
        conf={
            "spark.sql.adaptive.enabled": "true",
            "spark.sql.shuffle.partitions": "400",
            "spark.dynamicAllocation.enabled": "true",
        },
        executor_cores=4,
        executor_memory="8g",
        num_executors=20,
        verbose=False,
    )

    quality_check = PythonOperator(
        task_id="validate_feature_output",
        python_callable=validate_output_partition,
        provide_context=True,
    )

    wait_for_impressions >> build_features >> quality_check
```

What to say in an interview:

- the sensor enforces **data dependency correctness**
- SparkSubmitOperator executes the actual ETL job
- the final quality check closes the loop so success means **usable data**, not just a finished compute task

#### 6.6 `pandas_udf` — vectorized UDF alternative (new)

The existing warning against plain Python UDFs is important, but interviewers may ask what you would use when native Spark expressions are insufficient.

A plain Python UDF works row by row and pays Python serialization overhead per record. A `pandas_udf` batches rows into Arrow-backed pandas Series, so the Python boundary is crossed in vectorized chunks rather than one row at a time.

**Plain UDF version:**

```python
from pyspark.sql import functions as F, types as T

@F.udf(returnType=T.DoubleType())
def engagement_score_udf(watch_time_ms, like_cnt, comment_cnt, share_cnt):
    return (
        min(watch_time_ms or 0, 30000) / 30000.0
        + 2.0 * (like_cnt or 0)
        + 3.0 * (comment_cnt or 0)
        + 5.0 * (share_cnt or 0)
    )

scored = events_df.withColumn(
    "engagement_score",
    engagement_score_udf("watch_time_ms", "like_cnt", "comment_cnt", "share_cnt"),
)
```

**Vectorized `pandas_udf` version:**

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql import types as T

@pandas_udf(T.DoubleType())
def engagement_score_pandas_udf(
    watch_time_ms: pd.Series,
    like_cnt: pd.Series,
    comment_cnt: pd.Series,
    share_cnt: pd.Series,
) -> pd.Series:
    clipped_watch = watch_time_ms.fillna(0).clip(upper=30000) / 30000.0
    return (
        clipped_watch
        + 2.0 * like_cnt.fillna(0)
        + 3.0 * comment_cnt.fillna(0)
        + 5.0 * share_cnt.fillna(0)
    )

scored = events_df.withColumn(
    "engagement_score",
    engagement_score_pandas_udf(
        F.col("watch_time_ms"),
        F.col("like_cnt"),
        F.col("comment_cnt"),
        F.col("share_cnt"),
    ),
)
```

Why the vectorized version is faster:

- fewer Python boundary crossings
- Arrow-based columnar transfer
- pandas vectorized math instead of Python row loops
- better executor throughput for medium-complexity custom logic

The precise wording to use in an interview is: Spark still cannot optimize custom Python logic the way it can optimize native expressions, but `pandas_udf` keeps execution batch-oriented and avoids the per-row serialization penalty of a plain UDF, so the surrounding plan stays far healthier.

Important nuance: if Spark native expressions can express the logic, they are still preferable. `pandas_udf` is the **fallback after native functions**, not the first choice.

### 7. Debugging (new section)

#### 7.1 Reading the Spark UI to spot skew

The Spark UI Stage view is one of the highest-signal debugging surfaces in production.

**Healthy stage pattern:** task durations are relatively tight, and shuffle read size per task is in the same ballpark.

```text
Healthy stage
Task durations:  8s  9s 10s  9s 11s 10s  8s  9s
Shuffle read:   220MB 210MB 235MB 225MB 240MB 230MB 215MB 225MB
```

**Skewed stage pattern:** most tasks finish fast, but one or two tasks run dramatically longer because one partition owns far more data.

```text
Skewed stage
Task durations:  2s  2s  3s  2s  2s  180s 175s  3s
Shuffle read:    40MB 35MB 45MB 42MB 39MB 5.8GB 5.5GB 41MB
```

What to inspect in the Stage view task list:

- **Duration**: are one or two tasks extreme outliers?
- **Shuffle Read Size / Records**: do the slow tasks read orders of magnitude more data?
- **Input Size**: did the skew originate earlier than the current join?
- **Executor logs**: are the slow tasks spilling heavily or retrying?

The key diagnosis line:

> If 95% of tasks finish in ~2 seconds but 1–2 tasks take ~180 seconds, you do not have a general cluster-sizing problem; you have a partition imbalance problem.

How this links back to Section 5:

- if a few join keys dominate, salting can split those heavy keys across partitions
- if a small dimension table is involved, broadcasting it may remove the skewed shuffle entirely
- if AQE is enabled, verify whether skew join handling actually triggered; if not, manual salting may still be necessary

#### 7.2 Common OOM causes and fixes

OOM debugging is easier if you separate **where** memory pressure occurs.

Common causes and fixes:

| Cause | Symptom | Fix |
|---|---|---|
| Broadcast table too large | executor crashes during join setup | lower broadcast threshold or force shuffle join |
| Too many concurrent tasks per executor | random executor OOM under moderate data sizes | reduce `spark.executor.cores` or increase executor memory |
| Large Python UDF state | PySpark worker crashes or high memory overhead | replace with native expressions or `pandas_udf`; increase memory overhead |
| Wide rows after explode/join | spill-heavy stage, long GC pauses | project fewer columns early; aggregate before join |
| Excessive caching | job slows over time, executor memory remains pinned | persist only reused DataFrames and `unpersist()` promptly |
| Skewed partition | one task OOMs while others finish | salt the key, broadcast small side, or split hot keys |

Fast interview-safe debugging order:

1. Look at the failed stage and task skew.
2. Check whether the join strategy matched the table sizes.
3. Inspect row explosion from `explode`, one-to-many joins, or missing filters.
4. Revisit executor cores vs. memory pressure.
5. Remove unnecessary caching and Python-heavy transforms.

### 8. How This Shows Up in the Loop

If a "blended" round asks you to implement the SQL query from Module 3 in Spark, the fastest credible path is: mirror the CTEs as chained DataFrame transformations 1:1 (pre-aggregate → window → filter), narrate the partition/shuffle implications as you go, and mention `dropDuplicates` on `event_id` before any aggregation — the same idempotency point graders look for in the SQL round.
