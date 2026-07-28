---
layout: default
title: Module 5 — Pipeline Reliability, Batch & Streaming
permalink: /modules/pipeline-reliability/
---

## Module 5 — Pipeline Reliability, Batch & Streaming

**Core job:** show that you know what breaks at scale, how to recover safely, and how to operationalize reliability rather than merely define it.

## Table of Contents

1. [Delivery Semantics](#1-delivery-semantics)
   1. [At-least-once vs. exactly-once vs. at-most-once](#11-at-least-once-vs-exactly-once-vs-at-most-once)
   2. [Idempotency keys as the practical mechanism](#12-idempotency-keys-as-the-mechanism-that-makes-at-least-once-behave-like-exactly-once)
2. [Backfill Strategies](#2-backfill-strategies)
   1. [Staging + atomic swap](#21-staging--atomic-swap)
   2. [Partition-level vs. full-table backfill](#22-partition-level-vs-full-table-backfill)
   3. [Backfilling without locking concurrent reads](#23-backfilling-without-locking-concurrent-reads)
3. [Late-Arriving Data](#3-late-arriving-data)
   1. [Watermarking](#31-watermarking)
   2. [Grace periods and reprocessing windows](#32-grace-periods-and-reprocessing-windows)
4. [Data Quality Gates](#4-data-quality-gates)
   1. [Null / range / row-count checks](#41-null--range--row-count-checks)
   2. [Schema-drift detection](#42-schema-drift-detection)
   3. [Volume-anomaly thresholds](#43-volume-anomaly-thresholds)
5. [Lineage & SLAs](#5-lineage--slas)
   1. [Upstream/downstream impact assessment](#51-upstreamdownstream-impact-assessment)
   2. [SLA definition and breach monitoring](#52-sla-definition-and-breach-monitoring)
6. [Failure Modes](#6-failure-modes)
   1. [Common Airflow DAG failure patterns](#61-common-airflow-dag-failure-patterns)
   2. [Retry/backoff design](#62-retrybackoff-design)

| Pattern | Best for | Pros | Cons |
|---|---|---|---|
| Batch (Spark/Presto) | Daily/hourly aggregation, heavy joins | High throughput, cheap, easy backfills | Latency in minutes–hours |
| Streaming (Kafka/Flink) | Real-time fraud/anomaly, live counters | Millisecond latency | Complex state, hard to backfill |
| Lambda | Real-time views + accurate batch truth | Best of both | Two pipelines to maintain — real ongoing cost |

## 1. Delivery Semantics

### 1.1 At-least-once vs. exactly-once vs. at-most-once

#### Delivery semantics primer

Suppose a Kafka consumer reads a batch of 1,000 events and crashes after writing 700 rows downstream.

| Semantic | What happens after crash | Risk |
|---|---|---|
| At-most-once | offsets may already be committed, so some of the 300 unwritten events are lost | data loss |
| At-least-once | offsets are not committed until processing completes, so the batch is replayed | duplicates possible |
| Exactly-once | each event affects downstream state once despite retries | hard to achieve end-to-end without careful system design |

Concrete interpretation:
- **At-most-once:** safer for avoiding duplicates, dangerous for correctness because missing data is permanent.
- **At-least-once:** safer for correctness because you can replay, but duplicate writes must be handled.
- **Exactly-once:** ideal user-facing outcome, but in practice it usually depends on atomic state updates, transactional sinks, or idempotent writes.

Interview-quality takeaway:

> In real pipelines, at-least-once delivery plus idempotent writes is often the practical way to approximate exactly-once behavior.

Exactly-once caveat worth stating out loud:

- Kafka transactions plus Spark Structured Streaming can provide end-to-end exactly-once behavior in specific designs.
- It requires transactional/idempotent sinks, consistent checkpointing, and careful failure semantics.
- It is not the default outcome of simply using Kafka or Spark.

### 1.2 Idempotency keys as the mechanism that makes at-least-once behave like exactly-once

An **idempotency key** ensures that replaying the same event does not apply the business effect twice.

Examples:
- `event_id` for immutable event ingestion
- `order_request_id` for purchase creation
- `message_id` for send acknowledgments

Typical implementation patterns:
- unique constraint on `event_id`
- upsert / merge keyed by `event_id`
- dedup state store in streaming engines

If a consumer crashes mid-batch:
1. Kafka replays the batch
2. downstream sees repeated `event_id`s
3. duplicates are ignored or overwritten safely

That is why idempotency is the **practical** answer, not just a conceptual one.

## 2. Backfill Strategies

Hive-style storage paths explanation:

- Paths like `s3://meta-raw-events/reel_view/ds=2026-07-20/` use Hive-style partitioning (`column=value`).
- Engines such as Spark and Presto parse partition values from directory names and can prune files before reading data contents.

### 2.1 Staging + atomic swap

**Idempotent backfill pattern** — this is the answer to many "how would you safely reprocess history?" questions:

```text
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

Why it works:
- readers continue using the old partition while validation runs
- the final publish step is atomic
- failures never partially corrupt the production partition

Atomic swap means readers see either the old partition snapshot or the new one after a single metadata switch, not a half-written intermediate state.

### 2.2 Partition-level vs. full-table backfill

Choose the smallest safe scope.

| Backfill type | Best when | Advantage | Risk |
|---|---|---|---|
| Partition-level | issue is localized to certain `ds` values | fast, cheap, low blast radius | may miss cross-partition dependencies |
| Full-table | logic changed globally or history is inconsistent | correctness across all history | expensive, long-running, higher operational risk |

Decision rule:
- if only one ingestion outage affected `2026-07-20`, backfill that partition
- if dedup logic changed for all historical events, plan a broader rebuild

### 2.3 Backfilling without locking concurrent reads

Recommended pattern:
1. write new data to shadow/staging location
2. validate counts, nulls, schema, and checksum-like aggregates
3. atomically repoint the partition or table pointer
4. keep the old version available for rollback

Good implementations:
- partition pointer swap
- Hive metastore partition replacement
- Iceberg/Delta/Hudi snapshot swap

Avoid:
- in-place overwrite while readers are actively scanning
- delete-then-insert workflows with long read windows

## 3. Late-Arriving Data

### 3.1 Watermarking

A **watermark** is the system's statement about how complete a stream is up to some event-time point.

Example:
- "We consider the `2026-07-28 05:00` event-time window complete once data up to 05:15 has arrived."

Why it matters:
- mobile events can arrive late due to offline buffering
- network issues create out-of-order arrival
- naive daily closes can undercount if you finalize too early

Interview phrasing: watermarking is an event-time completeness boundary. Data later than the watermark is treated as too-late for that finalized window. See Module 9 section "Structured Streaming with watermarking" for implementation syntax.

### 3.2 Grace periods and reprocessing windows

Design for late data explicitly:
- keep a **grace period** for window completion
- reopen recent partitions for reprocessing
- distinguish event time from processing time

Example policy:
- daily partition publishes at 6:00 AM PST
- accepts late events for 24 hours
- reprocesses rolling last 2 days each morning

This is often a better answer than promising impossible strict finality.

## 4. Data Quality Gates

### 4.1 Null / range / row-count checks

Abstract advice such as "verify row counts" is too weak. Use concrete thresholds.

Recommended defaults:
- row count must be within **±5%** of trailing 7-day average
- primary-key null rate must be **< 0.1%**
- critical numeric measures must fall within expected bounds
  - no negative watch time
  - no future timestamps
  - no impossible conversion counts

### 4.2 Schema-drift detection

Schema checks should compare the produced dataset against the registered contract:
- Glue schema
- Hive metastore schema
- Avro/Protobuf registry

Minimum checks:
- same required column set
- compatible types
- no silent column renames

### 4.3 Volume-anomaly thresholds

Volume anomalies catch upstream outages even when the job "succeeds."

Useful thresholds:
- daily row count outside ±5% of trailing 7-day average
- dimension cardinality drop > 10% on critical keys
- sudden zeroing of one region, platform, or app version

#### Python pseudo-code for quality gates

```python
def validate_partition(
    current_row_count: int,
    trailing_7d_avg_row_count: float,
    pk_null_count: int,
    total_rows: int,
    actual_schema: list[tuple[str, str]],
    expected_schema: list[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []

    lower_bound = trailing_7d_avg_row_count * 0.95
    upper_bound = trailing_7d_avg_row_count * 1.05
    if not (lower_bound <= current_row_count <= upper_bound):
        errors.append(
            f"row_count_out_of_range: current={current_row_count}, "
            f"expected_range=({lower_bound:.0f}, {upper_bound:.0f})"
        )

    null_rate = (pk_null_count / total_rows) if total_rows else 1.0
    if null_rate >= 0.001:  # 0.1%
        errors.append(f"pk_null_rate_too_high: null_rate={null_rate:.5f}")

    if actual_schema != expected_schema:
        errors.append(
            f"schema_mismatch: actual={actual_schema}, expected={expected_schema}"
        )

    return errors
```

## 5. Lineage & SLAs

### 5.1 Upstream/downstream impact assessment

Lineage is what lets you answer:
- what broke this table?
- which dashboards, models, or alerts depend on it?
- who should be paged?

When a schema changes, assess:
1. upstream sources affected
2. downstream tables/views impacted
3. dashboards and experiments that consume the output
4. whether the change is backward compatible

This is the difference between fixing one DAG and managing a production data platform.

### 5.2 SLA definition and breach monitoring

#### Worked SLA definition

Requirement:

> The executive revenue dashboard data must land by **6:00 AM PST**. Alert if the `ds` partition is missing by **6:15 AM**.

Operationalization:
- schedule the DAG on a PST-aligned timetable
- make the partition existence check an early task
- set `sla=timedelta(minutes=15)` on the critical task or DAG path
- fire an alert callback if the partition is still absent by 6:15

#### Airflow DAG sketch with sensor, Spark, retries, exponential backoff, and Slack SLA alert

Dependency note: `SparkSubmitOperator` requires the `apache-airflow-providers-apache-spark` provider package in the Airflow environment.

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook


def sla_miss_alert(dag, task_list, blocking_task_list, slas, blocking_tis):
    hook = SlackWebhookHook(slack_webhook_conn_id="slack_alerts")
    hook.send(
        text=(
            f":rotating_light: SLA miss in DAG `{dag.dag_id}`. "
            f"Tasks: {task_list}. Blocking tasks: {blocking_task_list}"
        )
    )


def assert_partition_exists(ds: str, **_context):
    """
    Replace this stub with a real metastore or object-store existence check.
    """
    partition_exists = True  # e.g. query Hive/Glue/S3 path for ds
    if not partition_exists:
        raise AirflowException(f"Missing required partition for ds={ds}")


default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


with DAG(
    dag_id="executive_revenue_dashboard_pipeline",
    start_date=datetime(2026, 1, 1, tzinfo=ZoneInfo("America/Los_Angeles")),
    schedule="0 6 * * *",
    catchup=False,
    default_args=default_args,
    sla_miss_callback=sla_miss_alert,
    tags=["revenue", "sla_critical"],
) as dag:

    wait_for_upstream_partition = ExternalTaskSensor(
        task_id="wait_for_upstream_partition",
        external_dag_id="upstream_revenue_fact_pipeline",
        external_task_id="publish_ds_partition",
        allowed_states=["success"],
        failed_states=["failed", "skipped"],
        timeout=60 * 20,        # wait up to 20 minutes
        poke_interval=60 * 5,   # check every 5 minutes
        mode="reschedule",
        sla=timedelta(minutes=15),
    )

    check_partition_exists = PythonOperator(
        task_id="check_partition_exists",
        python_callable=assert_partition_exists,
        op_kwargs={"ds": "{{ ds }}"},
        sla=timedelta(minutes=15),
    )

    run_spark_job = SparkSubmitOperator(
        task_id="run_spark_revenue_aggregation",
        application="/opt/airflow/jobs/revenue_dashboard.py",
        conn_id="spark_default",
        application_args=["--ds", "{{ ds }}"],
        executor_memory="8g",
        driver_memory="4g",
        num_executors=20,
        sla=timedelta(minutes=15),
    )

    wait_for_upstream_partition >> check_partition_exists >> run_spark_job
```

What this operationalizes:
- `ExternalTaskSensor` waits for upstream data
- `PythonOperator` explicitly checks the expected `ds` partition exists
- retries and exponential backoff handle transient failures
- `sla_miss_callback` sends Slack when a task misses its SLA deadline relative to the scheduled run time (not only when the task hard-fails)

## 6. Failure Modes

### 6.1 Common Airflow DAG failure patterns

Common operational failures:
- upstream partition arrives late, sensor times out
- task succeeds but writes partial data because one output partition failed
- retries re-run non-idempotent logic and duplicate data
- backfill overwhelms shared cluster capacity
- schema drift causes downstream Spark job parse errors
- too many small files degrade read performance and timeout downstream tasks

Interview tip: mention both **orchestration failures** and **data correctness failures**.

### 6.2 Retry/backoff design

Retries should match failure mode:
- transient network issue → retry with backoff
- missing upstream partition → sensor / defer / reschedule
- deterministic schema mismatch → fail fast and page
- idempotent backfill step → safe to retry
- side-effecting API without idempotency key → dangerous to retry blindly

Good retry design:
- 3 retries
- exponential backoff
- bounded max retry delay
- idempotent task semantics
- clear alerting on final failure

Other production topics to have ready:
- late-arriving mobile logs
- out-of-order processing vs. out-of-order arrival
- lineage tracking so you can say exactly which downstream dashboards break if an upstream table changes shape
