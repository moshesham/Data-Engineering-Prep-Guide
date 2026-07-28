---
layout: default
title: One-Page Recall Sheet
permalink: /recall-sheet/
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
