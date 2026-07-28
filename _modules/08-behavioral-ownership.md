---
layout: default
title: Module 8 — Behavioral & Ownership
permalink: /modules/behavioral-ownership/
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

