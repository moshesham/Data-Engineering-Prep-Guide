---
layout: default
title: Module 1 — Product Sense & Metrics
permalink: /modules/product-sense-metrics/
---

## Module 1 — Product Sense & Metrics

**Core job:** turn ambiguous product intent into a measurable, defensible metric, then explain why a metric moved without guessing.

## Table of Contents

1. [Metric Selection Frameworks](#1-metric-selection-frameworks)
   1. [North Star metrics by product surface](#11-north-star-metrics-by-product-surface-feed-reels-marketplace-messenger-ads)
   2. [L1/L2 metric-tree decomposition](#12-l1l2-metric-tree-decomposition--worked-not-just-defined)
   3. [Guardrail metric catalog](#13-guardrail-metric-catalog-mapped-per-product-type)
   4. [Ratio vs. absolute selection criteria](#14-ratio-vs-absolute-selection-criteria)
2. [Experimentation & A/B Testing](#2-experimentation--ab-testing)
   1. [Primary / secondary / guardrail metric design](#21-primary--secondary--guardrail-metric-design-for-a-launch)
   2. [Novelty effects, network effects, cannibalization](#22-novelty-effects-network-effects-cannibalization-between-features)
   3. [Attribution models](#23-attribution-models-last-touch-vs-multi-touch)
3. [Root Cause Analysis Playbook](#3-root-cause-analysis-playbook)
   1. [Technical/data diagnostic checklist](#31-technicaldata-diagnostic-checklist)
   2. [Segmentation-dimension catalog](#32-segmentation-dimension-catalog-region-os-version-cohort-tenure)
   3. [External/product-factor checklist](#33-externalproduct-factor-checklist)
   4. [Worked metric-drop scenarios](#34-multiple-worked-drop-scenarios-across-different-surfaces)
4. [Handling Ambiguity in the Prompt](#4-handling-ambiguity-in-the-prompt)
   1. [Clarifying-question framework](#41-clarifying-question-framework-for-an-open-ended-case)
   2. [Stating assumptions explicitly](#42-stating-assumptions-explicitly-and-moving-on)
   3. [Tradeoff articulation](#43-tradeoff-articulation-eg-engagement-vs-long-term-retention)

## 1. Metric Selection Frameworks

### 1.1 North Star metrics by product surface (Feed, Reels, Marketplace, Messenger, Ads)

**Metric toolkit:**
- **North Star metrics** — the one number that best captures durable user or business value.
- **L1/L2 decomposition** — break the North Star into controllable levers, such as `DAU = New + Retained + Resurrected`.
- **Guardrails** — metrics you are not explicitly maximizing, but must not damage.
- **Ratios vs. totals** — ratios normalize for traffic changes; totals measure gross scale. State which one matters and why.

The North Star should match the product's value exchange:

| Product surface | Primary value created | Good North Star metric | Why it fits | Common mistake |
|---|---|---|---|---|
| Feed | Relevance and time well spent | Meaningful Feed sessions per DAU or quality-adjusted time spent | Captures both usage and satisfaction | Using raw impressions, which rewards over-delivery |
| Reels | Short-form content consumption and creation flywheel | Total qualified watch time or 15-day active creators | Balances demand-side and supply-side health | Optimizing starts only, which can be gamed by autoplay |
| Marketplace | Matching buyers with sellers | Gross merchandise value (GMV) or successful transactions | Ties directly to liquidity and economic value | Using listing views alone without transaction closure |
| Messenger | Fast, reliable communication | Daily senders or messages sent per active conversation | Captures actual messaging utility | Counting app opens instead of communication |
| Ads | Advertiser value monetized without harming user experience | Revenue or value-optimized conversions per impression | Reflects business output | Maximizing ad load while ignoring user churn |

Use a **North Star table** in interviews when the prompt is broad. It shows you understand that different Meta surfaces have different optimization targets.

### 1.2 L1/L2 metric-tree decomposition — worked, not just defined

Metric trees turn a vague prompt into diagnostic structure.

#### Worked example: Reels watch time

Suppose the North Star is **daily qualified Reels watch time**.

```text
Total Reels Watch Time
= Reels DAU
  × Reels sessions per DAU
  × Reels plays per session
  × autoplay/start rate
  × avg qualified watch seconds per play
```

An interview-quality decomposition then goes one level deeper:

- **Reels DAU**
  - New users
  - Retained users
  - Resurrected users
- **Plays per session**
  - Session entry rate
  - Scroll depth
  - Ranking relevance
- **Avg qualified watch seconds**
  - Video length mix
  - Completion rate
  - Playback quality / buffering

This helps you distinguish **scale problems** from **efficiency problems**:
- If DAU is flat but watch time is down, the issue is likely within-session behavior.
- If watch seconds per play are flat but starts are down, the issue is discovery, ranking, or entry.

DAU cohort math to state explicitly when prompted:

`DAU(t) = New(t) + Retained(t) + Resurrected(t)`

- **New:** first-ever active users on day `t`.
- **Retained:** users active on day `t` and also active in the recent lookback window (often previous day).
- **Resurrected:** users active on day `t` after a defined inactivity gap (for example, no activity for 30+ days).

#### Worked example: Marketplace GMV

```text
GMV
= Transacting buyers
  × Orders per buyer
  × Average order value
```

L2 drill-down:
- **Transacting buyers**
  - Buyer visits
  - Search-to-detail CTR
  - Detail-to-message / checkout conversion
- **Orders per buyer**
  - Listing inventory depth
  - Match quality
  - Trust and safety friction
- **Average order value**
  - Category mix
  - Price inflation / discounts
  - Shipping fee policy

This decomposition is more useful than saying "I would segment the metric" because it tells the interviewer **what to segment on and why**.

### 1.3 Guardrail metric catalog, mapped per product type

Guardrails should map to the failure mode introduced by the proposed optimization.

| Product surface | Typical North Star | Common optimization move | Required guardrails | Why these guardrails matter |
|---|---|---|---|---|
| Feed | Meaningful sessions / time spent | Increase ranking aggressiveness | Hide/report rate, content integrity violations, D7 retention | More engagement can come from low-quality or polarizing content |
| Reels | Qualified watch time | Increase autoplay/start rate | Short-bounce rate, negative feedback rate, crash rate, creator retention | More starts can reduce satisfaction if quality drops |
| Marketplace | GMV | Reduce buyer friction or surface more listings | Fraud/chargeback rate, refund rate, seller response time, successful delivery rate | Faster commerce that increases bad transactions is not a win |
| Messenger | Daily senders / messages sent | Add lightweight reply affordances | Notification opt-out rate, send failure rate, conversation depth, latency | More sends are bad if reliability or trust drops |
| Ads | Revenue / conversion value | Increase ad load or widen targeting | User session length, advertiser ROI, hide-ad rate, latency | Monetization must not erode user experience or advertiser value |

#### Concrete North Star + guardrail pairs

| Surface | North Star | Core guardrail pair |
|---|---|---|
| Feed | Meaningful interactions per DAU | Hide/report rate + D30 retention |
| Reels | Qualified watch time | Short-bounce rate + creator posting retention |
| Marketplace | GMV | Refund/fraud rate + successful delivery rate |
| Messenger | Daily senders | Send failure rate + notification opt-out rate |
| Ads | Revenue | Ad hide rate + downstream session retention |

### 1.4 Ratio vs. absolute selection criteria

Use **absolute metrics** when the business question is about total value created:
- Total watch time
- Total GMV
- Total revenue
- Total daily senders

Use **ratio metrics** when you need to normalize for traffic mix or exposure:
- CTR
- Messages per active conversation
- Orders per buyer
- Revenue per thousand impressions

Decision rule:
1. If traffic is fluctuating and you want to understand **efficiency**, prefer a ratio.
2. If the company cares about **gross business output**, you still need an absolute metric.
3. In most launches, report **both**: one absolute outcome and one normalized rate.

Example:
- If Reels likes rise 20% because impressions doubled, the like rate may be unchanged.
- If Marketplace GMV is flat while conversion rate improves, traffic may have fallen.

## 2. Experimentation & A/B Testing

### 2.1 Primary / secondary / guardrail metric design for a launch

#### From-scratch metric definition example: launching a new Reels reaction feature

Prompt: *Meta is launching lightweight emoji reactions on Reels. How do you measure success?*

Start by clarifying:
1. Is the goal to increase viewer engagement, creator feedback, or downstream content creation?
2. Is the feature shown on all Reels or only eligible surfaces?
3. Is a reaction private, visible to the creator only, or visible to other viewers?

Assume the product goal is: **increase lightweight engagement without cannibalizing deeper engagement or hurting retention**.

**Metric design**

- **Primary metric:** reactions per reaction-eligible Reel viewer
  - Numerator: count of `reel_reaction_sent`
  - Denominator: unique users exposed to the reaction affordance
  - Why: directly measures whether the feature is used when available

- **Secondary metrics:**
  - Reels watch time per exposed user
  - Reels shares per exposed user
  - Creator received-engagement rate
  - 7-day creator posting retention for creators receiving reactions

- **Guardrails:**
  - Comment rate per exposed user
  - Share rate per exposed user
  - Hide / not interested rate
  - App crash rate
  - D7 viewer retention

Interpretation:
- If reactions go up but comments collapse, the feature may be **cannibalizing richer engagement**.
- If reactions go up and watch time rises slightly but retention drops, novelty may be masking a long-term quality problem.

Cross-reference to Section 1.3: these experiment guardrails are the same guardrail family (for example crash rate, hide/not-interested rate, retention) and serve as rollout stop conditions even when the primary metric is up.

**Launch readout template**

| Metric type | Metric | Result interpretation |
|---|---|---|
| Primary | Reactions per exposed viewer | Did the feature solve its direct objective? |
| Secondary | Watch time per exposed viewer | Did it deepen consumption? |
| Secondary | Creator received-engagement rate | Did creators get more feedback? |
| Guardrail | Comments per exposed viewer | Did lightweight taps replace richer interaction? |
| Guardrail | D7 retention | Did short-term engagement come at long-term cost? |

### 2.2 Novelty effects, network effects, cannibalization between features

#### Novelty effects

A **novelty effect** happens when users interact more because something is new, not because it adds lasting value.

Common signs:
- Immediate spike after launch, then decay toward baseline
- Strong lift in first-time exposed users, weak lift in repeat exposed users
- No long-term retention movement

How to address it:
- Read the experiment over multiple windows: Day 1, Week 1, Week 4
- Examine repeat behavior, not just first interaction
- Prefer retention, repeat rate, or creator-side persistence as supporting evidence

Concrete novelty-pattern example:

| Week post-launch | Daily reaction rate per exposed user | Interpretation |
|---|---:|---|
| Week 1 | 14.2% | Curiosity spike |
| Week 2 | 9.8% | Early decay |
| Week 3 | 5.4% | Nearing steady state |
| Week 4 | 5.1% | Stable baseline |

Practical mitigation: run at least 14-21 days and read lift separately for established cohorts versus first-time exposed users.

#### Network effects

Networked products can exhibit delayed treatment effects because one user's experience depends on others.

Examples:
- Messenger quick replies may be more useful only after enough recipients reply in kind.
- Marketplace buyer-side changes may affect seller responsiveness and inventory quality over time.

Implication: simple user-level randomization can underestimate or misread impact when treated and control users interact. In interviews, call out:
- interference/spillover
- cluster randomization when appropriate
- the need for longer measurement windows

#### Cannibalization

Cannibalization means the new behavior grows by replacing an existing valuable behavior.

Examples:
- Reactions replace comments
- One-click seller contact increases messages but reduces completed checkouts
- More Feed inventory for Reels entry points boosts Reels but hurts Feed quality

Always ask: **what valuable behavior might this feature displace?**

### 2.3 Attribution models: last-touch vs. multi-touch

Attribution matters when multiple surfaces influence the same outcome.

| Model | Definition | Best use case | Weakness |
|---|---|---|---|
| Last-touch | Credit all outcome value to the final touchpoint | Simple launch readouts, short funnels | Over-credits the final exposure |
| First-touch | Credit all value to the initial discovery source | Top-of-funnel acquisition | Ignores closing influence |
| Linear multi-touch | Split credit evenly across touches | Balanced directional readouts | Treats all touches as equally important |
| Time-decay multi-touch | Heavier credit to later touches | Longer journeys like commerce | More subjective weighting |

Examples:
- In Ads, a conversion after Feed impression → Reels reminder → Marketplace click can look very different under last-touch vs. multi-touch.
- In Marketplace, giving all credit to the final seller-message event may understate the importance of discovery ranking or saved-item reminders.

Attribution worked example:

User path: Ad A impression (Day 1) -> Ad B click (Day 2) -> Ad C view (Day 3) -> $100 purchase (Day 3).

| Model | Ad A | Ad B | Ad C | Revenue allocation |
|---|---:|---:|---:|---|
| First-touch | 100% | 0% | 0% | A = $100 |
| Last-touch | 0% | 0% | 100% | C = $100 |
| Linear | 33.3% | 33.3% | 33.3% | A/B/C = $33.33 each |
| Position-based (40/20/40) | 40% | 20% | 40% | A = $40, B = $20, C = $40 |

## 3. Root Cause Analysis Playbook

**Root-cause framework for a metric drop** — always split into two branches before guessing:

```text
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

### 3.1 Technical/data diagnostic checklist

Interview distinction before you start:

- **Metric drop prompt** (for example, "DAU fell 6%") -> diagnostic investigation: verify data health, segment, isolate root cause.
- **Feature launch prompt** (for example, "evaluate new comments feature") -> framework design: define success metric, guardrails, experiment horizon, and attribution.

Before inventing product explanations, verify the metric is real.

1. **Pipeline freshness**
   - DAG completed?
   - partitions landed?
   - upstream sensor delayed?
2. **Event volume integrity**
   - did event counts fall across all surfaces or one event only?
   - any app-version-specific logging cliff?
3. **Schema / instrumentation drift**
   - renamed event?
   - changed enum values?
   - missing required payload fields causing drops in downstream ETL?
4. **Dedup / join correctness**
   - duplicate suppression changed?
   - dimension join suddenly became non-unique?
5. **Metric-definition changes**
   - denominator changed?
   - filter tightened?
   - new bot filtering rule applied?

### 3.2 Segmentation-dimension catalog (region, OS, version, cohort, tenure)

Good segmentation dimensions are reusable across product cases:

| Dimension | Why it matters | Typical bug or product insight it reveals |
|---|---|---|
| Region / country | Captures market-specific outages, holidays, regulations | Only LATAM dropped after payments issue |
| Platform / OS | Mobile product bugs are often OS-specific | Android app release broke message sends |
| App version | Fastest route to isolating bad deploys | v312 logging regression |
| User tenure | New users and power users break differently | New sellers churned after onboarding friction |
| Acquisition cohort | Quality mix can shift overall aggregates | Cheap ad cohorts reduced retention |
| Surface / placement | UI changes can hurt one entry point only | Reels tray entry down, direct search stable |
| Creator / buyer / seller tier | High-value cohorts deserve separate diagnosis | Power sellers drove most GMV loss |
| Content or category mix | Mix shift can move averages without behavioral change | Auto category fell, apparel stable |

### 3.3 External/product-factor checklist

If the data is healthy, move to product and market explanations.

- **Recent launches:** ranking changes, UI changes, paywall or friction changes
- **Operational issues:** latency, message-send failures, payment processor degradation
- **Supply-side shocks:** fewer active creators, fewer sellers, missing inventory
- **External events:** holiday, sports final, outage, competitor launch, policy change
- **Trust & safety actions:** spam sweeps, fraud filtering, moderation policy changes
- **Seasonality and mix shifts:** weekday/weekend, end-of-month advertising budgets, major shopping events

### 3.4 Multiple worked drop scenarios across different surfaces

#### Worked example — Reels watch time drop

Case: **Reels watch time is down 8% day-over-day.**

1. **Clarify**
   - Is the drop global or region-specific?
   - Is it watch time total, per user, or per play?
   - Is Reels DAU stable?
2. **Segment**
   - By OS and app version
   - By entry surface (Feed entry, standalone Reels tab, notifications)
   - By content length bucket
3. **Hypothesize**
   - Technical: autoplay fails on one client version
   - Product: ranking change worsened relevance
   - External: large live-event day shifted time elsewhere
4. **Resolve**
   - If play starts dropped only on Android v312, it is likely client or logging
   - If starts are flat but watch seconds per play fell across all versions, ranking or content mix is more likely

#### Worked example — "Daily Active Creators dropped 6% globally in 48 hours"

1. Verify it's real user behavior, not a pipeline delay: DAG lag, missing ingestion batch, broken dedup.
2. Segment by device, OS, app version, creator tenure, and region.
3. Form competing hypotheses and say what would falsify each:
   - **Technical:** `reel_upload_success` failed to fire on Android v312.0.
   - **Product:** a ranking change reduced impression reach for new creators, weakening posting motivation.
4. Resolve with a targeted query: event volume and creator reach by `app_version`, `device_os`, and creator tenure over 72 hours.

#### Worked case study — Marketplace GMV drop

Case: **Marketplace GMV dropped 11% week-over-week.**

1. **Clarify**
   - Is this gross GMV or net of refunds/cancellations?
   - Is the drop in transacting buyers, orders per buyer, or AOV?
   - Is the issue in one category, one country, or all inventory?
2. **Segment**
   - Geography: country, metro, rural vs. urban
   - Category: electronics, home goods, vehicles, apparel
   - Funnel stage: listing view → message seller → transaction
   - Buyer vs. seller cohorts: new buyers, power sellers, verified sellers
3. **Hypothesize**
   - Buyer-side discovery regression reduced view-to-message conversion
   - Seller response times worsened, reducing close rate
   - Fraud policy tightened and suppressed legitimate listings
   - Payments or shipping integration degraded in one region
4. **Resolve**
   - Suppose sessions are stable, listing views are stable, but seller-response rate and transaction completion fell sharply in one region after a seller-app update.
   - Conclusion: GMV loss is operational/seller-side, not demand-side.
   - Action: roll back the seller messaging flow change and monitor response-time recovery, successful transaction rate, and refunds.

#### Worked case study — Messenger message-send drop

Case: **Messages sent dropped 7% in 24 hours.**

1. **Clarify**
   - Is the drop in attempted sends, successful sends, or daily senders?
   - Is it 1:1 messaging, groups, or business messaging?
   - Is latency or failure rate also moving?
2. **Segment**
   - OS, app version, network type, geography
   - Conversation type: 1:1, group, cross-app bridge
   - User tenure: heavy senders vs. casual users
3. **Hypothesize**
   - Client bug caused send button failures on one app version
   - Server-side latency increased, depressing send completion
   - New compose UI added friction for first-time sends
   - Notification delivery degraded, reducing reply loops
4. **Resolve**
   - Suppose attempted sends are flat but successful sends are down only on Android v314 with elevated timeout rate.
   - Conclusion: user intent is stable; message completion failed operationally.
   - Action: hotfix or rollback, then verify send success rate, latency p95, and sender retention.

#### Worked case study — Ads revenue drop

Case: **Ads revenue dropped 9% day-over-day.**

1. **Clarify**
   - Is the drop from impression volume, ad load, price, or conversion value?
   - Is this gross revenue, recognized revenue, or modeled advertiser value?
   - Is it all placements or one auction surface?
2. **Segment**
   - Placement: Feed, Stories, Reels
   - Market and advertiser vertical
   - Bid strategy and campaign objective
   - Device platform and app version
3. **Hypothesize**
   - Auction bug lowered ad load or ranking quality
   - Large advertisers hit budget caps earlier than usual
   - Measurement/attribution issue undercounted conversions
   - User experience changes reduced session supply
4. **Resolve**
   - If impressions are flat but CPM and conversion reporting drop only for one attribution pipeline version, revenue loss may be measurement-related rather than real marketplace weakness.
   - If ad impressions themselves fell due to reduced eligible supply in Reels, the problem is inventory, not pricing.

## 4. Handling Ambiguity in the Prompt

### 4.1 Clarifying-question framework for an open-ended case

A strong answer starts with three classes of questions:

1. **Objective**
   - What user or business problem are we solving?
   - Are we optimizing engagement, retention, monetization, or quality?
2. **Scope**
   - Which surface, geography, cohort, and time horizon matter?
   - Is this a launch, a post-launch readout, or a metric-drop investigation?
3. **Constraints**
   - Are there policy, trust, privacy, or latency constraints?
   - What metrics are non-negotiable guardrails?

If the interviewer will not answer, state reasonable assumptions and continue.

### 4.2 Stating assumptions explicitly and moving on

Do not stall when the prompt is underspecified. Say:

> "I'll assume the goal is durable engagement rather than short-term clicks, the feature is launching globally on mobile, and retention plus negative feedback are the main guardrails."

That single sentence does three things:
- narrows the metric space
- makes your reasoning auditable
- signals comfort with ambiguity

### 4.3 Tradeoff articulation (e.g., engagement vs. long-term retention)

Product metrics are rarely single-objective.

Common tradeoffs:
- **Engagement vs. long-term retention** — more notifications can increase immediate activity while raising opt-outs.
- **Revenue vs. user experience** — more ad load can lift short-term revenue while hurting session quality.
- **Buyer conversion vs. fraud risk** — lower friction can increase bad transactions.
- **Viewer taps vs. creator ecosystem health** — easy interactions may boost lightweight engagement but not creator motivation.

A high-quality articulation sounds like this:

> "I would optimize qualified watch time as the primary metric, but only if hide rate, crash rate, and D7 retention remain within guardrail bounds. Otherwise the lift is not durable."

**Interview habit to practice:** state your metric definition in one sentence before touching schema or SQL. If you cannot do that, you do not have a metric yet — you have a topic.
