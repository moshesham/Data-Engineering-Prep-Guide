---
layout: default
title: Module 9 — Apache Spark: ETL Development Reference
permalink: /modules/spark-etl/
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

