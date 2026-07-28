---
layout: default
title: Module 2 — Data Modeling & Schema Design
permalink: /modules/data-modeling-schema/
---

## Module 2 — Data Modeling & Schema Design

**Core job:** design a model that supports the metric from Module 1 without requiring ambiguous joins, fan-out fixes, or full-table rescans.

> **Convention Note: what is `ds`?**
> In Hive-style warehouse layouts, `ds` is the daily datestamp partition key (`'YYYY-MM-DD'`). Query engines such as Presto/Trino and Spark use it for partition pruning, so metric queries should nearly always bound `ds`.

## Table of Contents

1. [Fact Table Design](#1-fact-table-design)
   1. [Transaction vs. periodic snapshot vs. accumulating snapshot](#11-transaction-vs-periodic-snapshot-vs-accumulating-snapshot--decision-criteria)
   2. [Grain determination](#12-grain-determination-as-an-explicit-exercise)
   3. [Additive vs. semi-additive vs. non-additive measures](#13-additive-vs-semi-additive-vs-non-additive-measures)
2. [Dimension Design](#2-dimension-design)
   1. [Conformed dimensions](#21-conformed-dimensions-shared-across-multiple-fact-tables)
   2. [SCD Types 1–6](#22-scd-types-13-existing-plus-type-4-and-type-6)
   3. [Junk and degenerate dimensions](#23-junk-dimensions-and-degenerate-dimensions)
   4. [Role-playing dimensions](#24-role-playing-dimensions)
3. [Schema Patterns](#3-schema-patterns)
   1. [Star vs. snowflake vs. fact constellation](#31-star-vs-snowflake-vs-fact-constellation-galaxy-schema)
   2. [One Big Table vs. normalized star](#32-one-big-table-obt-vs-normalized-star)
4. [Event Logging Design](#4-event-logging-design)
   1. [Payload versioning strategy](#41-payload-versioning-strategy)
   2. [Required vs. optional fields, schema evolution](#42-required-vs-optional-fields-schema-evolution)
   3. [Idempotency keys as a schema-level decision](#43-idempotency-keys-as-a-schema-level-decision)

## 1. Fact Table Design

### 1.1 Transaction vs. periodic snapshot vs. accumulating snapshot — decision criteria

Choose the fact type based on the question you need to answer.

| Fact type | Row meaning | Best for | Example | Tradeoff |
|---|---|---|---|---|
| Transaction fact | One row per atomic event | Event-level analysis, funnels, auditability | one Reel view, one ad impression, one message send | Large volume |
| Periodic snapshot | One row per entity per period | Daily or hourly state reporting | seller daily inventory, conversation daily stats | Loses event-by-event detail |
| Accumulating snapshot | One row per entity updated over lifecycle milestones | Process tracking | order placed → shipped → delivered → refunded | Requires updates and careful late data handling |

Decision rule:
- If analysts need exact user sequence or event timing, choose **transaction fact**.
- If the key question is "what was true at the end of each day?", choose **periodic snapshot**.
- If the entity passes through distinct stages and you need stage durations, choose **accumulating snapshot**.

### 1.2 Grain determination as an explicit exercise

The most common modeling mistake is skipping grain definition.

Ask out loud:
1. What does one row represent?
2. What dimensions uniquely identify that row?
3. What measures live naturally at that grain?

#### Worked exercise: "Model ad performance"

Suppose the prompt is: *Design a schema for ad performance reporting.*

Possible grains:
- `campaign_id, day` — too coarse for placement-level reporting
- `ad_id, impression_id` — too fine for most daily performance dashboards
- `ad_id, placement_id, day` — usually the right balance

Final grain:

> One row per **ad_id × placement_id × day**.

Why:
- Ads behave differently in Feed vs. Stories vs. Reels placements.
- Daily reporting is the natural cadence for many BI use cases.
- Measures such as impressions, clicks, spend, and conversions aggregate cleanly.

Good measures at this grain:
- `impressions`
- `clicks`
- `spend_usd`
- `conversions`
- `revenue_usd`

Bad measures at this grain:
- raw creative text blobs
- user-level attributes
- latest campaign status without date qualification

#### Grain sanity checks

If you cannot answer these, the grain is not finished:
- Can a business key appear twice in the same fact row definition?
- Are any dimensions accidentally many-to-many?
- Would an analyst need `COUNT(DISTINCT ...)` just to fix your schema?

### 1.3 Additive vs. semi-additive vs. non-additive measures

| Measure type | Definition | Example | Safe aggregation |
|---|---|---|---|
| Additive | Can sum across all dimensions | impressions, spend, watch_time_ms | sum across users, dates, placements |
| Semi-additive | Can sum across some dimensions but not all | account_balance, inventory_on_hand | sum across users, not across time snapshots |
| Non-additive | Cannot be meaningfully summed | CTR, AOV, conversion rate | recompute from numerator and denominator |

Interview rule: never sum precomputed ratios. Store the numerator and denominator:
- `clicks` and `impressions`, not only `ctr`
- `orders` and `buyers`, not only `orders_per_buyer`

## 2. Dimension Design

### 2.1 Conformed dimensions shared across multiple fact tables

**Surrogate key vs natural key**

- **Natural/business key:** source-system identifier, often string-like (for example, `user_uuid`).
- **Surrogate key:** warehouse-generated integer key (for example, `user_key`).
- **Why interviewers prefer surrogate keys in dimensions:** faster integer joins at scale and stable historical linkage when source keys mutate across systems.

A **conformed dimension** means the same dimension can join consistently across multiple facts.

Common conformed dimensions:
- `dim_date`
- `dim_user`
- `dim_geo`
- `dim_device`

Why they matter:
- Marketplace buyer conversion and ads spend can both roll up by the same geography definition.
- Messenger engagement and Reels watch time can use the same date hierarchy.
- Executives get one definition of "country", not five incompatible ones.

Example:
- `fact_message`
- `fact_reel_impressions`
- `fact_marketplace_transactions`

All can share `dim_date` and `dim_user` if those dimensions are modeled consistently.

### 2.2 SCD Types 1–3 (existing) plus Type 4 and Type 6

Surrogate keys improve join performance and support history tracking. Avoid using external natural keys as primary warehouse join keys.

#### SCD Type 1

- **Definition:** overwrite old value with new value
- **Use when:** history does not matter
- **Example:** fix seller display-name typo

#### SCD Type 2

- **Definition:** create a new row for each change
- **Use when:** point-in-time correctness matters
- **Columns:** `effective_start_ds`, `effective_end_ds`, `is_current`

`dim_user` Type-2 state — this is the row shape to draw from memory:

| user_key (PK) | user_id | country | start_ds | end_ds | is_current |
|---|---|---|---|---|---|
| 1001 | 98401293 | US | 2024-01-01 | 2026-03-14 | FALSE |
| 1002 | 98401293 | UK | 2026-03-15 | 9999-12-31 | TRUE |

#### SCD Type 3

- **Definition:** keep current value and one prior value in the same row
- **Use when:** only limited history is needed
- **Example columns:** `current_plan_tier`, `previous_plan_tier`

#### SCD Type 4

- **Definition:** keep the current dimension in one table and full history in a separate history table
- **Use when:** current lookups must stay fast, but history must still be available

Worked example:

Current table:

`dim_seller_current`

| seller_id | risk_tier | onboarding_status | updated_ds |
|---|---|---|---|
| 501 | medium | verified | 2026-07-28 |

History table:

`dim_seller_history`

| seller_id | risk_tier | onboarding_status | effective_start_ds | effective_end_ds |
|---|---|---|---|---|
| 501 | low | pending | 2026-01-01 | 2026-03-31 |
| 501 | medium | verified | 2026-04-01 | 9999-12-31 |

Pattern advantage:
- dashboards that only need the latest seller state read `dim_seller_current`
- historical analyses join to `dim_seller_history`

#### SCD Type 6

- **Definition:** hybrid of Type 1 + Type 2 + Type 3
- **Use when:** you need full history, current overwrite convenience, and prior-value comparison

Worked example:

`dim_buyer_membership`

| buyer_key | buyer_id | current_loyalty_tier | previous_loyalty_tier | effective_start_ds | effective_end_ds | is_current |
|---|---|---|---|---|---|---|
| 7001 | 42 | Silver | Bronze | 2026-01-01 | 2026-05-31 | FALSE |
| 7002 | 42 | Gold | Silver | 2026-06-01 | 9999-12-31 | TRUE |

Why it is Type 6:
- **Type 2:** separate versioned rows
- **Type 3:** `previous_loyalty_tier`
- **Type 1 flavor:** current-facing attributes can be overwritten for convenience in some marts

### 2.3 Junk dimensions and degenerate dimensions

#### Junk dimension

A **junk dimension** groups low-cardinality flags that do not deserve separate dimensions.

Example:
- `is_promoted_listing`
- `is_trusted_seller`
- `is_cross_border`
- `is_mobile_web`

Instead of storing these small flags repeatedly across large fact tables, bundle them into `dim_listing_flags`.

Example `dim_listing_flags` (junk dimension):

| flag_key (PK) | is_promoted_listing | is_trusted_seller | is_cross_border | is_mobile_web |
|---|---|---|---|---|
| 1 | true | true | false | false |
| 2 | true | false | true | true |
| 3 | false | false | false | false |

#### Degenerate dimension

A **degenerate dimension** is a business identifier stored directly in the fact table with no separate dimension row.

Examples:
- `order_id`
- `conversation_id`
- `invoice_id`

Use when the identifier is analytically useful, but there is no stable descriptive dimension worth splitting out.

Example degenerate dimension in a fact table:

| transaction_id (degenerate dim) | buyer_id (FK) | seller_id (FK) | amount_usd |
|---|---|---|---:|
| `tx_8830192` | 102 | 904 | 45.00 |
| `tx_8830193` | 112 | 611 | 19.99 |

### 2.4 Role-playing dimensions

A **role-playing dimension** is one dimension reused under multiple semantic roles.

Examples:
- `dim_date` as `order_date`, `ship_date`, `delivery_date`
- `dim_user` as `buyer`, `seller`, `creator`

This is common in commerce:
- `fact_transaction` joins `dim_date` multiple times
- `dim_user` might be split into `dim_buyer` and `dim_seller` for semantic clarity even if sourced from a common user master

## 3. Schema Patterns

### 3.1 Star vs. snowflake vs. fact constellation (galaxy schema)

| Pattern | Description | Best use case | Tradeoff |
|---|---|---|---|
| Star schema | One central fact surrounded by denormalized dimensions | Fast analytics, easy BI | Some duplication in dimensions |
| Snowflake schema | Dimensions normalized into subdimensions | Strict data governance, shared hierarchies | More joins, harder for analysts |
| Fact constellation / galaxy | Multiple fact tables sharing conformed dimensions | Large product ecosystems | Requires grain discipline across facts |

#### Full star schema for Marketplace

Marketplace usually becomes a **fact constellation** with shared dimensions.

```text
dim_date          dim_listing             dim_buyer              dim_seller
  date_key    ┌─> listing_key         ┌─> buyer_key         ┌─> seller_key
              │   listing_id             buyer_id               seller_id
              │   category               join_ds                join_ds
              │   price_band             country                country
              │   condition              verification_tier      response_tier
              │
              │
              │   ┌────────────────────────────────────────────────────┐
              └───┤ fact_listing_daily                                 │
                  │ grain: listing_id × day                            │
                  │ measures: impressions, detail_views, saves,        │
                  │           messages_started, listing_active_flag     │
                  └────────────────────────────────────────────────────┘

              │   ┌────────────────────────────────────────────────────┐
              └───┤ fact_transaction                                   │
                  │ grain: transaction_id                              │
                  │ FKs: listing_key, buyer_key, seller_key, date_key  │
                  │ measures: item_price, shipping_fee, gmv_usd,       │
                  │           refund_usd, is_completed                 │
                  └────────────────────────────────────────────────────┘
```

```text
┌───────────────────────────────────────────────────────────────────┐
│                        ERD DIAGRAM LEGEND                         │
├───────────────────────────────────────────────────────────────────┤
│ PK : Primary Key (unique row identifier)                          │
│ FK : Foreign Key (references a dimension primary key)             │
│ 1:N : One-to-many relationship (1 dim row -> N fact rows)         │
│  -> : Cardinality direction from parent to child                  │
└───────────────────────────────────────────────────────────────────┘
```

Recommended tables:
- `fact_listing_daily`
- `fact_transaction`
- `dim_listing`
- `dim_buyer`
- `dim_seller`
- `dim_date`

Why two facts:
- listing discovery and buyer interest live at a different grain from closed transactions
- separating them avoids stuffing null-heavy transaction columns onto listing-impression rows

#### Full star schema for Messenger

Messenger also benefits from multiple facts:

```text
dim_date           dim_conversation       dim_participant       dim_message_type
  date_key     ┌─> conversation_key   ┌─> participant_key   ┌─> message_type_key
               │   conversation_id       user_id                text/image/video/sticker
               │   conversation_type     participant_role       ephemeral_flag
               │   member_count          country
               │
               │   ┌────────────────────────────────────────────────────┐
               └───┤ fact_conversation_daily                            │
                   │ grain: conversation_id × day                       │
                   │ measures: active_participants, sends, replies,     │
                   │           avg_latency_ms, notification_opens        │
                   └────────────────────────────────────────────────────┘

               │   ┌────────────────────────────────────────────────────┐
               └───┤ fact_message                                       │
                   │ grain: message_id                                  │
                   │ FKs: conversation_key, sender_participant_key,     │
                   │      recipient_participant_key, message_type_key,  │
                   │      date_key                                      │
                   │ measures: send_latency_ms, delivery_latency_ms,    │
                   │           message_size_bytes                       │
                   └────────────────────────────────────────────────────┘
```

Recommended tables:
- `fact_conversation_daily`
- `fact_message`
- `dim_conversation`
- `dim_participant`
- `dim_message_type`
- `dim_date`

#### Existing end-to-end example — logs → Reels star schema

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

```text
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
   │      event_timestamp, watch_time_ms,       │
   │      is_completed                          │
   │  PK,FK ds (partition key)                  │
   └───────────────────────────────────────────┘
              ▲
              │ 1:N
        dim_reel
   PK reel_id, creator_id, duration_ms, created_ds
```

### 3.2 One Big Table (OBT) vs. normalized star

| Approach | Strength | Weakness | When to use |
|---|---|---|---|
| OBT | Fast reads, fewer joins, simple dashboards | Wide, redundant, expensive to maintain, harder history rules | curated serving layer for a narrow workload |
| Normalized star | Clear grain, reusable dimensions, better governance | More joins | foundational warehouse design |

Good interview answer:

> "I would keep the canonical warehouse model as a star or constellation, then materialize an OBT only for latency-sensitive dashboards or repetitive BI workloads."

## 4. Event Logging Design

### 4.1 Payload versioning strategy

Every event contract should carry:
- `event_name`
- `event_version`
- `event_id`
- `event_timestamp`
- producer metadata such as `app_version`, `platform`, `schema_source`

Versioning rules:
1. Additive optional fields usually do **not** require a brand-new event name.
2. Breaking semantic changes should bump `event_version`.
3. Consumers should branch on explicit version, not on guessing field presence.

Example:
- `message_send` version 1: `{conversation_id, sender_id, send_ts}`
- `message_send` version 2: adds `{encryption_mode, message_type}`

### 4.2 Required vs. optional fields, schema evolution

Required fields should be truly indispensable for downstream correctness:
- `event_id`
- `event_timestamp`
- `user_id` or actor identifier when available
- key entity IDs such as `reel_id`, `listing_id`, `conversation_id`

Optional fields are suitable for:
- experimental UI metadata
- client-side diagnostic blobs
- fields not available on all platforms

#### Worked schema-evolution example: adding a new required field without breaking deployed clients

Suppose `marketplace_checkout_started` must eventually require `shipping_country`, but many existing mobile clients do not send it yet.

Why hard-required changes break in production:

- mobile clients are version-fragmented and cannot all upgrade immediately
- older app versions keep emitting payloads without newly required fields
- strict downstream parsers/deserializers then reject those records, causing parse failures or DLQ growth

Bad approach:
- mark `shipping_country` required immediately
- break all old clients and downstream validation

Safe approach:
1. **Phase 1:** add `shipping_country` as optional in event version 2.
2. **Phase 2:** deploy consumers that accept both:
   - if present, use payload value
   - if absent, derive from seller/buyer region when safe or mark as `UNKNOWN`
3. **Phase 3:** ship updated clients and monitor adoption by app version.
4. **Phase 4:** once old clients are below threshold, make `shipping_country` operationally required for accepted producer versions.
5. **Phase 5:** deprecate version 1 after downstream consumers are clean.

This is the core principle:

> Make wire-level evolution backward compatible first; make business-level enforcement stricter only after adoption is real.

### 4.3 Idempotency keys as a schema-level decision

Idempotency is not only a processing concern; it starts in the schema.

Recommended fields:
- `event_id` for globally unique event deduplication
- `request_id` for API retries
- `source_system`
- `producer_ts`

Examples:
- For checkout events, `order_request_id` prevents duplicate order creation on retry.
- For Kafka consumers, `event_id` lets you write `INSERT ... ON CONFLICT DO NOTHING`-style logic downstream.

## Scale mechanics

Partition by `ds` to bound scans; cluster or bucket on high-cardinality join keys such as `user_id`, `listing_id`, or `ad_id` to reduce shuffle. If you do not mention partition pruning when asked how this would run at Meta volume, that is a flag.
