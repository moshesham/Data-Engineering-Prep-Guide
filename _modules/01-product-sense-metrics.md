---
layout: default
title: Module 1 — Product Sense & Metrics
permalink: /modules/product-sense-metrics/
---

## Module 1 — Product Sense & Metrics

**Core job:** turn ambiguous product intent into a measurable, defensible metric, then know how to explain a metric that moved.

**Metric toolkit:**
- **North Star metrics** — the one number that matters long-term (e.g., Reels watch time, 15-day active creators).
- **L1/L2 decomposition** — break the North Star into levers: `DAU = New + Retained + Resurrected`.
- **Guardrails** — the metric you're *not* trying to move but must not break (ad load ↑ revenue but watch guardrail on uninstalls / D30 retention).
- **Ratios vs. totals** — ratios (CTR) normalize for traffic changes; totals measure gross scale. State which one you're optimizing and why.

**Root-cause framework for a metric drop** — always split into two branches before you start guessing:

```
Metric Drop Identified (e.g., Reels Watch Time -8%)
        │
   ┌────┴─────────────────────────┐
   ▼                              ▼
Technical/Data check       Product/Market check
- pipeline latency /       - regional or OS-specific?
  broken DAG                 (iOS vs. Android)
- missing logs / schema    - bad app release / build
  drift                      version bug?
- dedup logic failing      - external (holiday, outage,
                              competitor launch)?
```

**Worked example — "Daily Active Creators dropped 6% globally in 48 hours":**
1. Verify it's real user behavior, not a pipeline delay (DAG lag, missing ingestion batch, broken dedup).
2. Segment: device/OS/app-version, and creator tenure (new vs. power creators) — friction often hits one cohort, not everyone.
3. Form competing hypotheses and say which data would falsify each:
   - *Technical:* client logging failed to emit `reel_upload_success` on Android v312.0.
   - *Product:* a ranking change cut impression reach for new creators, killing posting motivation.
4. Resolve with a query: event volume by `app_version` and `device_os` over 72 hours.

**Interview habit to practice:** state your metric definition out loud in one sentence *before* touching the schema or SQL. If you can't state it in one sentence, you don't have a metric yet — you have a topic.

