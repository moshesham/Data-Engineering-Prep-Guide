---
layout: default
title: Module 9 — Apache Spark ETL Development Reference
permalink: /modules/spark-etl/
---



## Module 9 — Apache Spark ETL Development Reference

## Table of Contents
1. [Mental Model First](#1-mental-model-first)
2. [Architecture & Execution Model](#2-architecture--execution-model)
   1. [Driver / Executor Topology](#21-driver--executor-topology)
   2. [Unified Memory Model](#22-unified-memory-model)
3. [Canonical ETL Skeleton](#3-canonical-etl-skeleton)
4. [Explicit Schema Enforcement](#4-explicit-schema-enforcement)
5. [Syntax Inventory](#5-syntax-inventory)
6. [Complex & Hierarchical Data Handling](#6-complex--hierarchical-data-handling)
   1. [Nested struct access — dot notation](#61-nested-struct-access--dot-notation)
   2. [Flattening arrays with explode()](#62-flattening-arrays-with-explode)
   3. [Packing flat rows into structs and arrays](#63-packing-flat-rows-into-structs-and-arrays)
7. [Spark 4.0+ Variant Type](#7-spark-40-variant-type)
8. [Configs Worth Knowing Cold](#8-configs-worth-knowing-cold)
9. [Handling Skew & Tuning Joins](#9-handling-skew--tuning-joins)
10. [Complex ETL Patterns](#10-complex-etl-patterns)
    1. [Idempotent upsert / merge](#101-idempotent-upsert--merge)
    2. [Structured Streaming with watermarking](#102-structured-streaming-with-watermarking)
    3. [Unit-testing an ETL job](#103-unit-testing-an-etl-job)
    4. [Small-file problem and compaction](#104-small-file-problem-and-compaction)
    5. [Airflow-to-Spark orchestration](#105-airflow-to-spark-orchestration)
    6. [pandas_udf — vectorized UDF alternative](#106-pandas_udf--vectorized-udf-alternative)
11. [Debugging](#11-debugging)
    1. [Reading the Spark UI to spot skew](#111-reading-the-spark-ui-to-spot-skew)
    2. [Common OOM causes and fixes](#112-common-oom-causes-and-fixes)
12. [Memory & Performance Best Practices Checklist](#12-memory--performance-best-practices-checklist)
13. [How This Shows Up in the Loop](#13-how-this-shows-up-in-the-loop)

**Core job:** everything in Modules 2–5 gets implemented in Spark. This module goes from baseline syntax through the configs and patterns that separate "can write a job" from "can be trusted with a production pipeline at scale."

### 1. Mental Model First

DataFrame operations are **lazy** — nothing executes until an action (`.collect()`, `.count()`, `.write()`) forces Catalyst to plan and Tungsten to execute. Interviewers listen for whether you reason about the *physical plan*, not just the API call. Always be ready to say "I'd check `.explain(True)` here" when asked about performance.

Stick to the DataFrame/Dataset API. RDDs only come up if someone explicitly asks about internals (partitioning, lineage, `mapPartitions`).

A good mental shortcut:

- **read** defines your starting partitioning and file scan cost
- **transform** determines whether you trigger narrow ops or shuffles
- **join / aggregate / window** are where most expensive stages appear
- **write** determines downstream layout quality as much as current-job success

### 2. Architecture & Execution Model

#### 2.1 Driver / Executor Topology

Spark's distributed model splits work across two node roles. Understanding this distinction is the foundation of every performance and OOM conversation:

```
┌──────────────────────────────────────────────────────────────┐
│                      DRIVER PROCESS                          │
│  - Hosts SparkContext / SparkSession                         │
│  - Runs Catalyst (query planning) + Tungsten (code gen)      │
│  - Tracks DAG, stages, tasks via DAGScheduler                │
│  - Receives status updates from TaskScheduler                │
└──────────────────────┬───────────────────────────────────────┘
                       │  task dispatch / heartbeat / status
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Executor    │ │  Executor    │ │  Executor    │
│  Core 0 → T │ │  Core 0 → T │ │  Core 0 → T │
│  Core 1 → T │ │  Core 1 → T │ │  Core 1 → T │
│  Core 2 → T │ │  Core 2 → T │ │  Core 2 → T │
│  Core 3 → T │ │  Core 3 → T │ │  Core 3 → T │
│  Cache block│ │  Cache block│ │  Cache block│
└──────────────┘ └──────────────┘ └──────────────┘
   Worker node 1    Worker node 2    Worker node 3
   (T = one task per core slot)
```

Key points to articulate in an interview:

- The **driver** never processes data — it only plans and coordinates. A driver OOM means your application logic itself (e.g., a `.collect()` of millions of rows) is pulling too much data to the driver heap.
- **Executors** are JVM processes that run tasks and cache partitions. Each executor has a fixed number of cores and a fixed memory budget for the lifetime of the application.
- A **stage** is a maximal set of tasks that can run without a shuffle. A shuffle — caused by a wide transformation such as `groupBy`, `join`, or `repartition` — is the boundary between stages.
- A **task** is one unit of work applied to one partition. If you have 400 shuffle partitions, the downstream stage spawns 400 tasks. The minimum task duration should comfortably exceed the scheduling overhead (~100 ms); too many tiny tasks wastes the cluster.
- **Lazy evaluation**: transformations (`select`, `filter`, `join`) only build a logical plan. Catalyst compiles it to a physical plan when an *action* (`count`, `collect`, `write`) triggers execution.

Interview signal: saying "I'd add `.explain(True)` to inspect the physical plan before deciding whether to force a broadcast" shows you understand that the driver plans and the executors execute — and that the plan is inspectable without running the job.

#### 2.2 Unified Memory Model

Since Spark 1.6, all executor memory is managed in a *unified pool* — storage memory (caching) and execution memory (shuffles, sorts, aggregations) share the same region and can borrow from each other dynamically.

```
┌──────────────────────────────────────────────────────────────────┐
│              spark.executor.memory  (e.g., 8 g)                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │   Unified Memory Region  (spark.memory.fraction = 0.6)    │  │
│  │                                                            │  │
│  │  ┌──────────────────────┐  ┌──────────────────────────┐   │  │
│  │  │   Storage Memory     │  │   Execution Memory       │   │  │
│  │  │   (cache / persist)  │◄►│   (shuffle, sort, agg)   │   │  │
│  │  │                      │  │   Can evict Storage if   │   │  │
│  │  │  spark.memory.       │  │   under pressure         │   │  │
│  │  │  storageFraction     │  │                          │   │  │
│  │  └──────────────────────┘  └──────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │   User Memory (0.4 of executor.memory)                    │  │
│  │   Python UDF objects, task-local state, user data structs  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │   Reserved Memory (300 MB) — internal Spark overhead       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  + spark.executor.memoryOverhead  (off-heap: native / Python)    │
└──────────────────────────────────────────────────────────────────┘
```

Critical interview points:

- **JVM heap OOM** → check whether aggressive caching is stealing execution memory, or whether shuffle spill is creating extreme pressure. Execution memory evicts cached blocks when it needs space (if `StorageLevel` allows).
- **Overhead region OOM** → almost always caused by Python UDFs or libraries that allocate off-heap native memory. Increase `spark.executor.memoryOverhead` (default: max(10% of executor.memory, 384 MB)) or switch the UDF to `pandas_udf` (Arrow-based, more predictable overhead).
- Caching a DataFrame pins it in the Storage region. With `StorageLevel.MEMORY_ONLY`, eviction drops the block; with `MEMORY_AND_DISK`, it spills. Always call `unpersist()` when the cached DataFrame is no longer needed — Spark does not garbage-collect cached blocks automatically within a job.

**Common mistake:** assuming every OOM is "too little executor memory." More often, it is an executor.cores value that is too high (too many concurrent tasks sharing the same executor pool), a broadcast table that is larger than the threshold, or a Python UDF holding large objects in User Memory.

### 3. Canonical ETL Skeleton

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

### 4. Explicit Schema Enforcement

Schema inference is convenient for development but carries a full-scan cost in production — Spark must read a sample of the data before constructing the reader. For large datasets or streaming sources, always define an explicit schema.

| Approach | Cost | When to use |
|---|---|---|
| `inferSchema=True` | Spark reads a full pass to infer types; doubles scan I/O | Development / exploration only |
| `.schema(explicit_schema)` | Zero extra scan; Spark pushes the schema into the reader | Always in production |

```python
# dialect: PySpark
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, BooleanType
)

spark = SparkSession.builder.appName("schema_demo").getOrCreate()

# Explicit schema: documents expectations at the code layer and eliminates the inference scan.
# Mismatched or missing fields surface as NULL rather than a hard parse error,
# which is the desired behavior for tolerant ingestion.
event_schema = StructType([
    StructField("event_id",     StringType(),  nullable=False),
    StructField("user_id",      StringType(),  nullable=False),
    StructField("timestamp_ms", LongType(),    nullable=True),
    StructField("payload", StructType([
        StructField("creator_id",    StringType(),  nullable=True),
        StructField("watch_time_ms", LongType(),    nullable=True),
        StructField("completed",     BooleanType(), nullable=True),
    ])),
])

raw_df = (
    spark.read
    .format("json")
    .schema(event_schema)       # no inference scan; schema evolution surfaces as new NULL columns
    .load("s3://meta-raw-events/reel_view/ds=2026-07-20/")
)
```

The same `StructType` should be passed to `readStream` for Structured Streaming — the schema must always be explicit there because Spark cannot infer from an unbounded source.

Interview signal: "I always define an explicit `StructType` for production reads because inference requires a full scan and produces unpredictable types on evolving schemas" immediately differentiates you from candidates who only know `inferSchema=True`.

### 5. Syntax Inventory

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

### 6. Complex & Hierarchical Data Handling

Processing nested data — arrays of structs, struct-within-struct, maps — is a daily production reality at data-intensive companies. Interviewers test this explicitly because it is where candidates commonly introduce row explosions, NULL drops, and incorrect cardinality.

**Shared mock dataset used throughout this section:**

```python
# dialect: PySpark
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, BooleanType, ArrayType
)

spark = SparkSession.builder.appName("nested_data_demo").getOrCreate()

schema = StructType([
    StructField("user_id", StringType()),
    StructField("payload", StructType([
        StructField("creator_id",    StringType()),
        StructField("watch_time_ms", LongType()),
        StructField("completed",     BooleanType()),
    ])),
    StructField("interactions", ArrayType(StructType([
        StructField("action_type", StringType()),
        StructField("count",       LongType()),
    ]))),
])

data = [
    ("u1", ("c1", 15000, True),  [("like", 3), ("share", 1), ("comment", 2)]),
    ("u2", ("c2",  8000, False), [("like", 0)]),
    ("u3", ("c1", 25000, True),  []),   # empty interactions array — behavior differs between explode variants
]

df = spark.createDataFrame(data, schema)
```

#### 6.1 Nested Struct Access — Dot Notation

Access nested fields without any UDF or JSON parsing. Catalyst compiles dot access to a native field extraction with no Python overhead:

```python
# dialect: PySpark
flat_df = df.select(
    F.col("user_id"),
    F.col("payload.creator_id").alias("creator_id"),
    F.col("payload.watch_time_ms").alias("watch_time_ms"),
    F.col("payload.completed").alias("is_completed"),
)
# Result: flat row per user — user_id, creator_id, watch_time_ms, is_completed
```

The `.` operator works for arbitrarily deep nesting (`a.b.c.d`). Use `F.col("*")` to expand all top-level struct fields, but prefer explicit field naming in production to make the schema contract visible.

#### 6.2 Flattening Arrays with `explode()`

`explode()` converts each array element into its own row. All non-array columns are replicated for every element — this multiplies row count and can cause fan-out if not accounted for:

```python
# dialect: PySpark
exploded = (
    df
    .select(
        "user_id",
        F.col("payload.creator_id").alias("creator_id"),
        F.explode("interactions").alias("interaction"),  # one row per interaction element
    )
    .select(
        "user_id",
        "creator_id",
        F.col("interaction.action_type").alias("action_type"),
        F.col("interaction.count").alias("count"),
    )
)
# u3 (empty interactions array) produces ZERO rows with explode()
# Use explode_outer() to preserve the row with NULLs instead
```

**`explode()` vs. `explode_outer()`:**

| Function | Behavior on empty / NULL array | SQL analogy |
|---|---|---|
| `explode()` | Drops the row entirely | `INNER JOIN LATERAL` / `UNNEST` |
| `explode_outer()` | Keeps the row with NULL in the exploded column | `LEFT JOIN LATERAL` / `OUTER UNNEST` |

**Common mistake — chaining two `explode()` calls in a single `select()`:**

In Spark < 3.x this raises an `AnalysisException`; in newer versions it produces a cartesian product of the two arrays, which is almost never the intended behavior. Explode one array per `select`, then chain:

```python
# dialect: PySpark
# WRONG — avoid multiple explode calls in a single select
# df.select(F.explode("array_a"), F.explode("array_b"))  # cartesian product or error

# CORRECT — chain selects, one explode at a time
step1 = df.select("user_id", F.explode("interactions").alias("interaction"))
step2 = step1.select(
    "user_id",
    F.col("interaction.action_type").alias("action_type"),
    F.col("interaction.count").alias("count"),
)
```

#### 6.3 Packing Flat Rows into Structs and Arrays

The inverse operation — converting flat rows back into nested structures — uses `struct()`, `collect_list()`, and `collect_set()`. This pattern appears in feature engineering pipelines and denormalized write targets:

```python
# dialect: PySpark
# Goal: group per (user_id, creator_id) and collect all interaction records into an array of structs

repacked = (
    exploded
    .groupBy("user_id", "creator_id")
    .agg(
        F.collect_list(
            F.struct(
                F.col("action_type"),
                F.col("count"),
            )
        ).alias("interactions"),
        F.sum("count").alias("total_interactions"),
    )
)
# Result schema: user_id STRING, creator_id STRING,
#                interactions ARRAY<STRUCT<action_type: STRING, count: LONG>>,
#                total_interactions LONG
```

**`collect_list()` vs. `collect_set()`:**

| Function | Keeps duplicates? | Ordering guaranteed? | Memory usage | Use when |
|---|---|---|---|---|
| `collect_list()` | Yes | No (shuffle-order) | Higher | preserving all values, including duplicates |
| `collect_set()` | No (deduplicates) | No | Lower | distinct values only; also avoids unbounded growth on high-cardinality keys |

Neither function preserves sort order. If order within the collected array matters, `orderBy` the DataFrame before calling `collect_list()` — but note this adds a sort stage and the guarantee holds only within a single Spark partition unless followed by a shuffle.

**`struct()` builds a nested record inline from existing columns:**

```python
# dialect: PySpark
enriched = df.select(
    "user_id",
    F.struct(
        F.col("payload.creator_id").alias("creator_id"),
        F.col("payload.watch_time_ms").alias("watch_time_ms"),
    ).alias("summary"),
)
# summary column type: STRUCT<creator_id: STRING, watch_time_ms: LONG>
```

### 7. Spark 4.0+ — Variant Type for Schema-Agnostic JSON

Spark 4.0 introduced the `VARIANT` data type — a schema-agnostic container for semi-structured JSON data. It allows ingesting raw JSON payloads without committing to a rigid `StructType` upfront, then extracting typed values at query time using JSONPath expressions.

Two primary functions:

| Function | Purpose |
|---|---|
| `parse_json(col)` | Parses a JSON string column into a `VARIANT` column |
| `variant_get(col, path, type)` | Extracts a typed value from a `VARIANT` using a JSONPath expression |

```python
# dialect: PySpark 4.0+
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import StructType, StructField, StringType

spark = SparkSession.builder.appName("variant_demo").getOrCreate()

# Mock raw event log — schema varies by event type; enforcing a single StructType would reject valid rows
raw_data = [
    ('{"user_id":"u1","payload":{"watch_time_ms":15000,"creator_id":"c1"}}',),
    ('{"user_id":"u2","payload":{"watch_time_ms":8000,"creator_id":"c2"},"flags":["beta"]}',),
    ('{"user_id":"u3","action":"scroll","distance_px":350}',),   # entirely different schema
]
raw_schema = StructType([StructField("raw_json_str", StringType())])
raw_df = spark.createDataFrame(raw_data, raw_schema)

# Step 1 — parse the raw JSON string into a VARIANT column
df_variant = raw_df.withColumn("event_v", F.parse_json(F.col("raw_json_str")))

# Step 2 — drop the raw string payload immediately to avoid carrying large text downstream
df_variant = df_variant.drop("raw_json_str")

# Step 3 — extract typed fields using JSONPath; missing paths return NULL, not an error
enriched = df_variant.select(
    F.variant_get(F.col("event_v"), "$.user_id",               "string").alias("user_id"),
    F.variant_get(F.col("event_v"), "$.payload.watch_time_ms", "long"  ).alias("watch_time_ms"),
    F.variant_get(F.col("event_v"), "$.payload.creator_id",    "string").alias("creator_id"),
    F.variant_get(F.col("event_v"), "$.action",                "string").alias("action_type"),
)

enriched.show()
# u1: watch_time_ms=15000, creator_id=c1,  action_type=NULL
# u2: watch_time_ms=8000,  creator_id=c2,  action_type=NULL
# u3: watch_time_ms=NULL,  creator_id=NULL, action_type=scroll
```

**When to use `VARIANT` vs. `StructType`:**

| Approach | Catalyst optimization | Best for |
|---|---|---|
| Explicit `StructType` | Full column pruning and predicate pushdown at scan | Known, stable schemas |
| `VARIANT` + `variant_get` | Limited — schema unknown until extraction | Rapidly evolving or mixed-schema payloads |

Interview signal: "I'd reach for `VARIANT` when ingesting event streams where different event types have incompatible schemas — parse once to `VARIANT`, then extract only the fields each downstream query needs. For well-known schemas I always define an explicit `StructType` to let Catalyst prune columns at the scan level."

### 8. Configs Worth Knowing Cold

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

### 9. Handling Skew & Tuning Joins

- **Salting** — append a random suffix (`0`–`N`) to a skewed join key on both sides, join on `(key, salt)`, then aggregate away the salt. Standard fix when AQE skew-join handling isn't enough (e.g., pre-3.x clusters, or skew inside a single AQE partition).
- **Broadcast vs. shuffle join** — force a broadcast (`F.broadcast(small_df)`) for a dimension table that fits in memory; avoids shuffling the large fact table entirely.
- **`repartition` vs. `coalesce`** — `repartition(n)` does a full shuffle and can increase or decrease partitions; `coalesce(n)` only decreases partitions and avoids a full shuffle by merging adjacent ones. Use `coalesce` before a write when you over-partitioned upstream.
- **Cache/persist deliberately** — `df.persist(StorageLevel.MEMORY_AND_DISK)` when a DataFrame is reused across multiple actions; always `unpersist()` when done, or it silently holds executor memory for the rest of the job.

**Salting — concrete code example:**

```python
# dialect: PySpark
from pyspark.sql import functions as F

SALT_BUCKETS = 50  # tune based on skew severity; higher values distribute more evenly but replicate the small table more

# Large (skewed) table: append a random salt bucket to the join key
fact_salted = (
    fact_df
    .withColumn("_salt", (F.rand() * SALT_BUCKETS).cast("int"))
    .withColumn("skewed_key_salted", F.concat_ws("_", F.col("skewed_key"), F.col("_salt")))
)

# Small (dimension) table: replicate every row across all salt buckets
dim_exploded = (
    dim_df
    .withColumn("_salt", F.explode(F.array([F.lit(i) for i in range(SALT_BUCKETS)])))
    .withColumn("skewed_key_salted", F.concat_ws("_", F.col("join_key"), F.col("_salt")))
)

# Join on the composite salted key — the heavy key is now distributed across SALT_BUCKETS partitions
result = (
    fact_salted
    .join(dim_exploded, on="skewed_key_salted", how="inner")
    .drop("_salt", "skewed_key_salted")   # remove scaffolding columns from the output
)
```

Trade-off: salting replicates the small (dimension) table `SALT_BUCKETS` times. If the small table is large, broadcasting after salting may no longer be feasible — consider a hybrid approach where you try broadcasting first and only salt the keys that remain skewed.

A practical interview heuristic:

- If the large table is skewed and the small table fits in memory, **broadcast first**.
- If one or two keys dominate even after broadcast is impossible, **salt the heavy keys**.
- If the job writes thousands of tiny files after an otherwise good run, **fix the output partitioning**, not just the upstream shuffle.

### 10. Complex ETL Patterns

#### 10.1 Idempotent upsert / merge

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

#### 10.2 Structured Streaming with watermarking

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

**Output modes — what they mean and when each applies:**

| Output Mode | Semantics | Valid when |
|---|---|---|
| `append` | Only newly finalized rows written; previously written rows never updated | Queries with watermarks where rows are complete after the watermark passes |
| `update` | Only rows changed since the last trigger written; sink must support upserts | Stateful aggregations with progressive updates (e.g., windowed counts) |
| `complete` | Entire result table rewritten on every trigger | Aggregations without watermark; only for small result sets |

The example above uses `update` mode, which is appropriate for windowed aggregations where windows finalize progressively as late data passes the watermark threshold.

**Trigger types — controlling how often micro-batches run:**

```python
# dialect: PySpark
# Micro-batch: runs every N seconds (default when trigger is omitted)
query = windowed.writeStream.trigger(processingTime="30 seconds").start()

# Available Now: processes all backlogged data then stops — ideal for batch-on-demand streaming
query = windowed.writeStream.trigger(availableNow=True).start()

# Continuous: experimental sub-second latency mode; limited operator support
query = windowed.writeStream.trigger(continuous="1 second").start()
# Note: trigger(once=True) is deprecated — use availableNow=True instead
```

**Micro-batching vs. Continuous Processing:**

- **Micro-batching** (default): Spark collects data for a configurable interval, then processes the batch as a single job. Latency is in the seconds range. Supports all stateful operations, watermarks, and output modes. This is the production-safe choice for the vast majority of streaming workloads.
- **Continuous Processing**: Spark runs a persistent streaming pipeline with sub-millisecond checkpoint intervals. As of Spark 3.x it is experimental and supports only a subset of operators (no stateful aggregations, no windowing). Use only when latency requirements cannot be met by micro-batching.

**Stateful aggregations — tracking per-key state across micro-batches:**

Windowed aggregations are the most common form of stateful streaming. For arbitrary state logic (e.g., detecting a specific event sequence per user), use `applyInPandasWithState` (PySpark 3.4+):

```python
# dialect: PySpark 3.4+
from pyspark.sql.streaming.state import GroupStateTimeout
import pandas as pd

def track_session_state(
    key: tuple,
    pdfs,           # iterator of pandas DataFrames for this key in the current micro-batch
    state,          # GroupState object — persisted across micro-batches per key
) -> pd.DataFrame:
    user_id = key[0]
    if state.hasTimedOut:
        # Session timed out — emit a final record and clear the state
        final_count = state.get[0] if state.exists else 0
        state.remove()
        return pd.DataFrame({"user_id": [user_id], "session_event_count": [final_count]})
    current_count = state.get[0] if state.exists else 0
    for pdf in pdfs:
        current_count += len(pdf)
    state.update((current_count,))
    state.setTimeoutDuration(5 * 60 * 1000)   # 5-minute inactivity timeout in milliseconds
    return pd.DataFrame()   # no output until session closes via timeout

output_schema = "user_id string, session_event_count long"
state_schema  = "count long"

session_counts = (
    parsed
    .groupBy("user_id")
    .applyInPandasWithState(
        track_session_state,
        outputStructType=output_schema,
        stateStructType=state_schema,
        outputMode="append",
        timeoutConf=GroupStateTimeout.ProcessingTimeTimeout,
    )
)

query = (
    session_counts.writeStream
    .outputMode("append")
    .option("checkpointLocation", "s3://checkpoints/reel_sessions/")
    .trigger(processingTime="1 minute")
    .start()
)
```

Interview point: stateful operations require checkpoint storage because state must survive a driver restart. Always set `checkpointLocation` — without it, state is lost on failure and the stream restarts from scratch, duplicating or losing data.

#### 10.3 Unit-testing an ETL job

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

#### 10.4 Small-file problem and compaction

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

#### 10.5 Airflow-to-Spark orchestration

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

#### 10.6 `pandas_udf` — vectorized UDF alternative

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

### 11. Debugging

#### 11.1 Reading the Spark UI to spot skew

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

How this links back to Section 9:

- if a few join keys dominate, salting can split those heavy keys across partitions
- if a small dimension table is involved, broadcasting it may remove the skewed shuffle entirely
- if AQE is enabled, verify whether skew join handling actually triggered; if not, manual salting may still be necessary

#### 11.2 Common OOM causes and fixes

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

### 12. Memory & Performance Best Practices Checklist

Use this checklist before declaring a Spark job production-ready.

**Schema & Read**
- [ ] Explicit `StructType` schema passed to `spark.read` / `spark.readStream` — never `inferSchema=True` in production
- [ ] Partition pruning columns (e.g., `ds`) appear in `filter` / `WHERE` before any join or aggregation
- [ ] Column projection done as early as possible — select only columns the job needs
- [ ] Raw text payloads (JSON strings, binary blobs) dropped immediately after parsing — do not carry them through downstream joins

**Joins**
- [ ] Every join: check whether the small side fits within `spark.sql.autoBroadcastJoinThreshold` — force with `F.broadcast()` when safe
- [ ] AQE enabled (`spark.sql.adaptive.enabled = true`) — lets Spark choose join strategy at runtime with actual row counts
- [ ] Skewed join keys identified in Spark UI task list before shipping — salt when AQE's built-in skew join is insufficient
- [ ] `left_semi` / `left_anti` preferred over `INNER JOIN` for existence checks — avoids duplicating columns from the right side

**Aggregation & Shuffle**
- [ ] `spark.sql.shuffle.partitions` tuned to approximately (cluster cores × 2–4); default 200 is rarely optimal
- [ ] Pre-aggregate before joining when possible — reduces shuffle I/O on the larger table
- [ ] `dropDuplicates` on the deduplication key applied before any aggregation, not after

**Complex & Nested Data**
- [ ] `explode()` appears only once per `select()` — chain multiple explodes with intermediate `select` steps to avoid cartesian products
- [ ] `explode_outer()` used when empty-array rows must be preserved in the output
- [ ] `collect_set()` preferred over `collect_list()` when duplicates are undesirable — also avoids unbounded array growth on high-cardinality keys

**Caching & Persistence**
- [ ] `df.persist(StorageLevel.MEMORY_AND_DISK)` called only when the DataFrame is consumed by two or more downstream actions
- [ ] `df.unpersist()` called immediately after the last consumer action — prevents silent executor memory pinning
- [ ] `cache()` is shorthand for `persist(MEMORY_AND_DISK_DESER)` — prefer explicit `persist()` with a `StorageLevel` for predictable behavior

**Executor Sizing**
- [ ] `spark.executor.memory` sized for the task's actual data footprint; do not rely on disk spill as a substitute for adequate memory
- [ ] `spark.executor.memoryOverhead` increased when using Python UDFs, Arrow-based UDFs, or off-heap native libraries
- [ ] `spark.executor.cores` set to 4–5 for most workloads; higher values increase contention on the shared executor memory pool
- [ ] `spark.dynamicAllocation.enabled = true` for batch jobs with variable input sizes — prevents under- or over-provisioning

**Output & Compaction**
- [ ] `coalesce(n)` used to reduce output file count without an extra shuffle; `repartition(n)` when data rebalancing is also needed
- [ ] Small-file accumulation addressed at write time (coalesce) or maintenance time (Delta `OPTIMIZE` / Iceberg `rewrite_data_files`)
- [ ] Output format is columnar (Parquet, ORC, Iceberg-Parquet) unless the downstream consumer requires another format

**Saying it out loud:** "My first signal before any tuning is `.explain(True)` on the physical plan — I look for unexpected shuffle stages and join strategies. Then I open the Spark UI stage view to check task duration variance; a bimodal distribution is the diagnostic signature of data skew, not a resource problem."

**Practice problems:**
- `[Onsite-Medium]` Given a streaming Kafka source with an event schema containing a nested `payload` struct, write a PySpark job that extracts `user_id` and `watch_time_ms`, applies a 5-minute tumbling window aggregation with a 10-minute watermark, and writes results to an Iceberg table using `update` output mode. What output mode is correct and why?
- `[Onsite-Hard]` A join between a 10 TB fact table and a 500 MB dimension table is running for 3 hours; the Spark UI shows two tasks taking 2.5 hours each while the remaining 398 tasks finish in under 30 seconds. Diagnose the root cause and describe the two remediation strategies you would attempt in order.

### 13. How This Shows Up in the Loop

If a "blended" round asks you to implement the SQL query from Module 3 in Spark, the fastest credible path is: mirror the CTEs as chained DataFrame transformations 1:1 (pre-aggregate → window → filter), narrate the partition/shuffle implications as you go, and mention `dropDuplicates` on `event_id` before any aggregation — the same idempotency point graders look for in the SQL round.
