---
layout: default
title: Module 7 — Dashboards & Reporting
permalink: /modules/dashboards-reporting/
---

## Module 7 — Dashboards & Reporting

**Core job:** pick the right chart for the business question, and design the backend model so the dashboard doesn't need a full scan to render.

- Hierarchy: Executive KPIs → dimensional drill-downs → granular events.
- Line charts for trends; funnels for ordered conversion; cohort heatmaps (D1/D7/D30) for retention.

Funnel example:
```
Reel Impression        ████████████████████████████ 100%  (10.0M)
Watched > 3s           ████████████████             58%   (5.8M)
Liked / Commented      ████                         12%   (1.2M)
Shared                 █                             3%   (0.3M)
```

Cohort retention:
| Cohort | Users | D0 | D1 | D7 | D30 |
|---|---|---|---|---|---|
| 2026-06-01 | 100,000 | 100% | 42% | 28% | 18% |
| 2026-06-02 | 105,000 | 100% | 44% | 29% | 19% |
| 2026-06-03 | 98,000 | 100% | 39% | 25% | **15% — drop to investigate** |

That last row is deliberately planted — if you're presented a table like this, the interview wants you to notice the anomaly and propose the Module 1 diagnostic tree unprompted.

