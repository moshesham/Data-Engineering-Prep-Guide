#  Data Engineer Interview — Study Guide

⚠️ **Executable Pseudocode Disclaimer:** Code snippets and SQL queries in this guide are production-grade interview solutions designed to demonstrate conceptual logic, performance optimization, and algorithmic correctness. Table names (for example, `fact_reel_impressions`) and client event schemas are representative interview mocks.

## How to Use This Guide

The source material treats Product Sense, Data Modeling, SQL, and Python as separate modules. In the actual onsite, they are **not separate** — each of the three "Blended" rounds throws all four at you inside one 45-minute conversation, in this order:

```
Product framing  →  Event payload  →  Star schema  →  SQL query  →  (sometimes) Python transform
   (2–3 min)          (5 min)          (8–10 min)      (15 min)          (10 min)
```

The interviewer is grading whether your SQL and your schema are *consistent with the metric you defined two minutes earlier* — not whether each piece is correct in isolation. Most candidates lose points not on syntax but on drift: they define a metric in Module 1 language, then write a query in Module 3 that silently answers a different question. Treat Modules 1–4 below as one skill, not four.

### Anatomy of a 45-Minute Blended Round

Blended rounds are candidate-led: the interviewer gives a top-level product prompt and you drive the sequence below.

1. **Product Sense (8–10 min):** clarify the goal, define North Star and L1/L2 metrics, name guardrails.
2. **Event Logging + Data Modeling (10–12 min):** propose payload contracts, grain, and star schema decisions.
3. **SQL Analytics (10–12 min):** write query logic for funnel, retention, or RCA segmentation.
4. **Python Transformation / ETL (8–10 min):** implement parsing, aggregation, or sessionization logic clearly.

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

> **Convention Note: what is `ds`?**
> In Big Data ecosystems (Hive, Presto/Trino, Spark) and at Meta, `ds` is the daily datestamp partition key formatted as `'YYYY-MM-DD'`. It maps directly to partition folders and enables partition pruning, for example `WHERE ds = '2026-07-20'`.

The gap for you is almost never the engineering concept — it's translating credit-risk/fraud framing into consumer-social-product framing (DAU/retention instead of default rates, Reels watch time instead of transaction volume). Practice that translation explicitly; it's the actual thing being tested.

### Key Concepts Summary

- **Schema Drift:** payload structure changes (added/removed/renamed fields) that can break ingestion and ETL assumptions.
- **Feature / Concept Drift:** serving-time feature distributions shift away from training-time distributions and degrade model behavior.
- **Metric Drift:** business logic for a metric changes over time (for example, redefining DAU), making time-series comparisons inconsistent unless versioned.

---

## Study Modules

### Core Modules (Foundation)

- [**Module 1: Product Sense & Metrics**](_modules/01-product-sense-metrics.md)
  North Star metrics by product surface · L1/L2 metric-tree decomposition · guardrail catalog · A/B testing design · novelty effects · RCA playbook with worked drop scenarios (Reels, Marketplace GMV, Messenger, Ads) · handling ambiguity

- [**Module 2: Data Modeling & Schema Design**](_modules/02-data-modeling-schema.md)
  Fact table types and grain determination · additive vs. semi-additive measures · SCD Types 1–6 · conformed/junk/degenerate/role-playing dimensions · star/snowflake/OBT tradeoffs · full star schemas for Reels, Marketplace, and Messenger · schema evolution for event payloads

- [**Module 3: SQL**](_modules/03-sql.md)
  WHERE/HAVING/QUALIFY · NULL three-valued logic · join fan-out and anti-joins · window functions with frame semantics · **funnel conversion query** · **retention/cohort query** · **sessionization (gaps-and-islands)** · partition pruning · approximate aggregation

- [**Module 4: Python & Pipeline Scripting**](_modules/04-python-pipeline-scripting.md)
  Dict/set/heap data structures · **top-K heap pattern** · **mutual-connections set intersection** · **defensive log parsing with malformed lines** · merge intervals · **max-concurrent-sessions sweep-line** · sliding windows · Big-O communication

### Advanced Modules

- [**Module 5: Pipeline Reliability, Batch & Streaming**](_modules/05-pipeline-reliability.md)
  **Delivery semantics primer** (at-least/at-most/exactly-once) · idempotency keys · staging + atomic swap backfill · late-arriving data / watermarking · **concrete data-quality gate thresholds** · **full Airflow DAG with sensor, retry, SLA callback** · lineage and breach monitoring

- [**Module 6: AI/ML Infrastructure**](_modules/06-aiml-infrastructure.md)
  Feature store online/offline consistency · **point-in-time-correct training set** · **feature store table schema with dual timestamps** · embeddings and ANN search · **worked training-serving skew bug** · feature drift detection and retraining triggers

- [**Module 7: Dashboards & Reporting**](_modules/07-dashboards-reporting.md)
  Dashboard layer hierarchy · chart selection guide · **funnel backing table schema** · **cohort retention backing table schema** · the SQL that populates both (linking to Module 3) · **automated anomaly-detection alert logic**

- [**Module 8: Behavioral & Ownership**](_modules/08-behavioral-ownership.md)
  STAR mechanics and timing · **5 story archetypes**: technical ownership, conflict/disagreement, failure/mistake, ambiguity, cross-functional influence · Meta values mapping · **personal story bank template** · drill-down question handling

### Reference Modules

- [**Module 9: Apache Spark: ETL Development Reference**](_modules/09-spark-etl.md)
  Mental model + lazy execution · canonical ETL skeleton · full syntax inventory · configs reference · skew and join tuning · SCD merge and structured streaming · **small-file/compaction problem** · **Airflow-to-Spark DAG** · **pandas_udf vectorized example** · **Spark UI skew reading** · OOM diagnosis

  *Note: Module 9 is a reference module. Spark syntax itself is less common in the initial rapid-fire screen (usually SQL + Python), but Spark architecture, shuffle behavior, skew handling, and memory tradeoffs are frequently tested in onsite infra/system-design discussions.*

---

## Study Resources

- [**4-Week Study Plan**](_pages/study-plan.md) — Week-by-week focus areas and goals
- [**One-Page Recall Sheet**](_pages/recall-sheet.md) — Key concepts and formulas for quick reference

---

## Quick Navigation

| Interview Stage | Primary Modules | What to Practice |
|---|---|---|
| **Recruiter Screen** (30 min) | — | Project overview, data system experience |
| **Technical Screen** (60 min) | 3, 4 | Timed SQL & Python speed rounds |
| **Onsite Blended** (3 rounds) | 1 → 2 → 3 → 4 | Full loop: Metric → Schema → SQL → Python |
| **Onsite Pipeline/Infra** | 5, 9 | Reliability, backfill, Spark optimization |
| **Onsite ML Infra** | 6, 7 | Feature stores, dashboards, anomaly detection |
| **Behavioral** (1 round) | 8 | STAR stories mapped to Meta values |

---

## Module Dependency Map

```
Module 1 (Metric)
    │  defines what to measure
    ▼
Module 2 (Schema)
    │  defines the tables the query runs against
    ▼
Module 3 (SQL) ←───── Module 7 (Dashboards — backed by Module 3 queries)
    │  logic implemented in Spark
    ▼
Module 4 (Python) + Module 9 (Spark)
    │  reliability built on top
    ▼
Module 5 (Pipeline Reliability)
    │  supports ML infra
    ▼
Module 6 (AI/ML Infrastructure)

Module 8 (Behavioral) — parallel to all technical rounds
```

Each module stands alone but builds toward the integrated loop: **metric definition → event payload design → schema modeling → SQL query → Spark implementation → pipeline reliability → ML serving**. Master the translation from one module's language to the next.

**Last updated:** July 2026
