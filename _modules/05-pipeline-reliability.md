---
layout: default
title: Module 5 — Pipeline Reliability, Batch & Streaming
permalink: /modules/pipeline-reliability/
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

