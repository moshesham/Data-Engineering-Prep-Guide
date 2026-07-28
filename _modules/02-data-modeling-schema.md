---
layout: default
title: Module 2 — Data Modeling & Schema Design
permalink: /modules/data-modeling-schema/
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

