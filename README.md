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

## Study Modules

### Core Modules (Foundation)
- [**Module 1: Product Sense & Metrics**](_modules/01-product-sense-metrics.md) — Turn ambiguous product intent into measurable metrics; root-cause analysis for metric drops
- [**Module 2: Data Modeling & Schema Design**](_modules/02-data-modeling-schema.md) — Star schemas, fact tables, slowly changing dimensions, and scale mechanics
- [**Module 3: SQL**](_modules/03-sql.md) — Window functions, aggregations, joins, and query optimization
- [**Module 4: Python & Pipeline Scripting**](_modules/04-python-pipeline-scripting.md) — Data processing, dictionary-based aggregation, and integration patterns

### Advanced Modules
- [**Module 5: Pipeline Reliability, Batch & Streaming**](_modules/05-pipeline-reliability.md) — Idempotency, backfill strategies, and pipeline orchestration
- [**Module 6: AI/ML Infrastructure**](_modules/06-aiml-infrastructure.md) — ML systems, feature stores, and model evaluation
- [**Module 7: Dashboards & Reporting**](_modules/07-dashboards-reporting.md) — Data visualization, metric tracking, and alerting
- [**Module 8: Behavioral & Ownership**](_modules/08-behavioral-ownership.md) — STAR stories, leadership principles, and ownership mindset

### Reference Modules
- [**Module 9: Apache Spark: ETL Development Reference**](_modules/09-spark-etl.md) — Extract, Transform, Load patterns; Spark DataFrame API and optimization

---

## Study Resources

- [**4-Week Study Plan**](_pages/study-plan.md) — Week-by-week focus areas and goals
- [**One-Page Recall Sheet**](_pages/recall-sheet.md) — Key concepts and formulas for quick reference

---

## Quick Navigation

| Interview Stage | Focus Areas |
|---|---|
| **Recruiter Screen** (30 min) | Project overview, data system experience |
| **Technical Screen** (60 min) | Modules 3 & 4 — timed SQL & Python speed rounds |
| **Onsite Blended** (3 rounds) | Modules 1-5 in sequence: Metric → Schema → SQL → (Python) |
| **Behavioral** (1 round) | Module 8 — STAR stories mapped to company values |

---

Each module stands alone but builds toward the integrated loop: **metric definition → event payload design → schema modeling → SQL query → (sometimes) Python implementation**. Master the translation from one module's language to the next.

**Last updated:** July 2026
