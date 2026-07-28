---
layout: default
title: Module 6 — AI/ML Infrastructure
permalink: /modules/aiml-infrastructure/
---

## Module 6 — AI/ML Infrastructure

## Table of Contents
1. [Feature Store Architecture](#1-feature-store-architecture)
   1. [Online vs. offline store consistency](#11-online-vs-offline-store-consistency)
   2. [Point-in-time correctness for training data](#12-point-in-time-correctness-for-training-data-leakage-prevention)
2. [Embeddings & Vector Retrieval](#2-embeddings--vector-retrieval)
   1. [How embeddings get generated and stored](#21-how-embeddings-get-generated-and-stored)
   2. [Approximate nearest-neighbor search](#22-approximate-nearest-neighbor-search-concept-level)
3. [Training-Serving Skew](#3-training-serving-skew)
   1. [Common causes](#31-common-causes-different-code-paths-for-the-same-feature)
   2. [Detection strategies](#32-detection-strategies)
4. [Feature Drift & Monitoring](#4-feature-drift--monitoring)
   1. [Distribution-shift detection](#41-distribution-shift-detection)
   2. [Retraining triggers](#42-retraining-triggers)

**Core job:** show you understand the infra a DE builds *for* ML teams, not that you build the models.

- **Feature stores** — one source of truth serving both low-latency online inference and offline batch training; the failure mode to name is **training-serving skew** (the feature computed differently in the two paths).
- **Vector embeddings** — unstructured content (text/image) converted to vectors for similarity-based recommendation; you don't need to build the model, but you should be able to describe where the embedding pipeline sits relative to the feature store.
- **Feature drift** — baseline distribution shift between training and current serving traffic; name it as a data-quality problem, not just a modeling problem.

```
Client events → Kafka/Flink → Feature store → ML inference
                    │                              ▲
                    ▼                              │
              Batch data lake ─────────────────────┘
              (offline training set)
```

### 1. Feature Store Architecture

A strong interview answer makes one distinction immediately: the data engineer is responsible for the **data contracts, correctness guarantees, storage design, and serving path consistency** around features. You do not need to train the ranking model, but you do need to make sure the model sees the same definition of a feature in offline training and online inference.

#### 1.1 Online vs. offline store consistency

The online store exists for low-latency lookups during inference. The offline store exists for backfills, exploratory analysis, and training-set construction. They often serve different workloads, but they should represent the **same logical feature definition**.

A practical feature-store table shape is:

| Column | Meaning |
|---|---|
| `entity_id` | The serving key, such as `user_id`, `creator_id`, or `(user_id, reel_id)` |
| `feature_key` | Feature name such as `user_avg_watch_time_1h` |
| `feature_value` | Serialized value; may be numeric, boolean, JSON, or vector depending on the store |
| `event_ts` | When the source behavior actually happened |
| `ingestion_ts` | When the pipeline processed and published that feature value |

Example rows:

| entity_id | feature_key | feature_value | event_ts | ingestion_ts |
|---|---|---:|---|---|
| `u_101` | `user_avg_watch_time_1h` | `18.4` | `2026-07-28 09:00:00` | `2026-07-28 09:01:12` |
| `u_101` | `user_share_rate_7d` | `0.031` | `2026-07-28 09:00:00` | `2026-07-28 09:04:41` |
| `u_202` | `is_new_user_30d` | `true` | `2026-07-28 08:55:00` | `2026-07-28 08:55:10` |

Why both timestamps matter:

- `event_ts` is what makes **point-in-time-correct joins** possible for training data.
- `ingestion_ts` is what lets you debug **pipeline lateness**, late-arriving data, and backfill behavior.
- If you only store current values, you cannot reconstruct what the model would have seen at prediction time.
- If you only store `event_ts` and not `ingestion_ts`, you cannot tell whether a feature was logically valid but operationally unavailable when inference happened.

A concise architecture answer:

- **Streaming path** computes and publishes fresh features for online inference.
- **Batch path** materializes historical feature values for offline training.
- **Shared definitions** or a unified computation layer prevent divergence.
- **Point-in-time joins** keep training labels honest.

#### 1.2 Point-in-time correctness for training data (leakage prevention)

This is the classic interview question: *how do you avoid using future data to predict the past?*

Suppose we want to predict whether a user will share a Reel after an impression. Our label table is `fact_reel_impressions`, and our feature history lives in `dim_user_features`. The key rule is:

> For each impression at time `event_ts`, join only the feature values that were available as of that timestamp.

If you join to the current snapshot of the user, you leak future information. For example, if the user became a heavy sharer next week, that future state must not appear in a training row for today's impression.

Example schemas:

```sql
fact_reel_impressions(
    impression_id STRING,
    user_id STRING,
    reel_id STRING,
    event_ts TIMESTAMP,
    ingestion_ts TIMESTAMP,
    shared_within_24h BOOLEAN
)


dim_user_features(
    user_id STRING,
    feature_key STRING,
    feature_value DOUBLE,
    event_ts TIMESTAMP,
    ingestion_ts TIMESTAMP
)
```

Point-in-time-correct training-set construction:

```sql
WITH impression_base AS (
    SELECT
        impression_id,
        user_id,
        reel_id,
        event_ts,
        shared_within_24h AS label
    FROM fact_reel_impressions
    WHERE event_ts >= DATE '2026-07-01'
      AND event_ts < DATE '2026-08-01'
),
feature_candidates AS (
    SELECT
        i.impression_id,
        i.user_id,
        i.reel_id,
        i.event_ts AS impression_ts,
        i.label,
        f.feature_key,
        f.feature_value,
        f.event_ts AS feature_event_ts,
        f.ingestion_ts AS feature_ingestion_ts,
        ROW_NUMBER() OVER (
            PARTITION BY i.impression_id, f.feature_key
            ORDER BY f.event_ts DESC, f.ingestion_ts DESC
        ) AS rn
    FROM impression_base i
    JOIN dim_user_features f
      ON i.user_id = f.user_id
     AND f.event_ts <= i.event_ts
     AND f.ingestion_ts <= i.event_ts
)
SELECT
    impression_id,
    user_id,
    reel_id,
    impression_ts,
    MAX(CASE WHEN feature_key = 'user_avg_watch_time_1h' THEN feature_value END) AS user_avg_watch_time_1h,
    MAX(CASE WHEN feature_key = 'user_share_rate_7d' THEN feature_value END) AS user_share_rate_7d,
    MAX(CASE WHEN feature_key = 'is_new_user_30d' THEN feature_value END) AS is_new_user_30d,
    label
FROM feature_candidates
WHERE rn = 1
GROUP BY 1,2,3,4,8;
```

Why the join uses both timestamps:

- `f.event_ts <= i.event_ts` prevents using behavior that happened after the impression.
- `f.ingestion_ts <= i.event_ts` prevents using a feature value that was computed later and therefore was not actually available to the model at serve time.

That second condition is subtle and very interview-worthy. If upstream mobile events arrived late, a feature may describe the past correctly but still have been **unknown** when the model made the prediction.

A credible debugging example:

- Impression happened at `10:00:00`.
- User watch event happened at `09:58:00`.
- Due to a Kafka lag incident, the feature row was ingested at `10:07:00`.
- For training rows representing what the model knew at `10:00:00`, that feature must be excluded.

### 2. Embeddings & Vector Retrieval

Embeddings become relevant when the product needs retrieval over unstructured content: semantic search, similar-Reel recommendation, creator matching, or candidate generation before the ranker runs.

#### 2.1 How embeddings get generated and stored

A typical DE-owned pipeline looks like this:

1. Source content lands: Reel captions, hashtags, audio metadata, image frames, or user profile text.
2. A model service converts that content into dense vectors.
3. The vector is written to a vector index or vector-capable database.
4. Metadata joins back to the entity graph: reel ID, creator ID, locale, safety filters, freshness attributes.
5. Downstream ranking systems fetch candidate IDs from vector search, then enrich them with structured features from the feature store.

Conceptually:

```text
Raw content → embedding model → vector store / ANN index → candidate retrieval
                                        │
                                        └── joins with metadata + feature store for ranking
```

What interviewers care about:

- You know embeddings are usually **inputs to retrieval**, not replacements for the full serving stack.
- You know the vector pipeline has the same production concerns as any other data pipeline: freshness, backfills, schema versioning, and monitoring.
- You can explain where it sits relative to structured features: vector retrieval finds candidates; structured features help rank them.

Example storage shape:

| reel_id | embedding_vector | embedding_model_version | generated_ts | ingestion_ts |
|---|---|---|---|---|
| `r_901` | `[0.18, -0.04, ...]` | `text_image_v3` | `2026-07-28 08:50:00` | `2026-07-28 08:52:11` |

#### 2.2 Approximate nearest-neighbor search (concept level)

At scale, you do not brute-force compare every vector against every other vector at request time. ANN systems trade a little exactness for a large latency win.

The interview-safe explanation is:

- Exact nearest-neighbor search becomes too slow when the corpus is large and the vectors are high-dimensional.
- ANN structures prune the search space so you can return *good-enough* nearest neighbors quickly.
- The DE angle is not implementing the math; it is maintaining the pipeline that refreshes embeddings, rebuilds indexes, and preserves metadata consistency.

Operational questions you should be ready for:

- How often do embeddings refresh?
- What happens when the embedding model version changes?
- How do you backfill old content into the new index?
- How do you filter deleted or policy-blocked content out of retrieval?

### 3. Training-Serving Skew

Training-serving skew is one of the highest-signal concepts in ML infrastructure interviews because it reveals whether you understand that a feature name is meaningless if the computation path differs.

#### 3.1 Common causes (different code paths for the "same" feature)

Common causes:

- The online pipeline uses a streaming rolling window, while the offline pipeline uses a batch daily aggregate.
- Null handling differs between code paths.
- Time-zone handling differs between training and serving.
- The online path uses deduplicated events but the offline path does not.
- One path excludes bots, deleted content, or policy-violating traffic and the other does not.

**Worked example — skew bug:**

The online feature `user_avg_watch_time_1h` is computed in Flink as a true rolling 1-hour average over the last 60 minutes of watch events.

The offline feature with the same name is computed in Spark as:

```sql
SUM(watch_time_ms) / COUNT(*)
GROUP BY user_id, DATE(event_ts)
```

That is a **daily batch average**, not a rolling 1-hour average.

Same feature name, completely different definition.

Symptom pattern:

- Offline model validation looks strong because the training data is internally consistent.
- Production model quality degrades: lower precision, worse ranking, or reduced share/watch conversion.
- Feature inspection shows the online feature is far more volatile and responsive to recent behavior than the offline feature used during training.

Diagnosis:

1. Compare online inference logs to the offline training-set values for the same `(user_id, event_ts)`.
2. Sample several examples where predictions were poor.
3. Recompute both feature definitions side by side.
4. Notice that the online feature changes within the hour, while the offline feature is constant for the whole day.

Illustrative comparison:

| user_id | prediction_time | online `user_avg_watch_time_1h` | offline `user_avg_watch_time_1h` |
|---|---|---:|---:|
| `u_101` | `2026-07-28 09:15` | `24.8` | `11.3` |
| `u_101` | `2026-07-28 09:45` | `18.1` | `11.3` |
| `u_101` | `2026-07-28 10:05` | `6.4` | `11.3` |

Fix:

- Move the feature definition into a **shared transformation spec** or shared library.
- Materialize the same rolling-window logic for offline backfills.
- Add regression tests that compare online/offline outputs for the same event stream.
- Version feature definitions explicitly so changes are auditable.

The clean interview answer is: *never allow "same feature name, different code path, different semantics."*

#### 3.2 Detection strategies

Good teams do not wait for model performance degradation to discover skew.

Detection strategies:

- **Offline/online parity checks**: sample entities and timestamps, then compare feature values computed by both paths.
- **Feature-level SLAs**: freshness, null rate, min/max ranges, and population coverage.
- **Shadow inference**: log live requests and recompute the training-set feature view for those exact records.
- **Definition reviews**: feature names map to versioned specs, not free-form code in multiple repos.

A concrete parity-check idea:

```sql
SELECT
    o.user_id,
    o.prediction_ts,
    o.feature_value AS online_value,
    b.feature_value AS offline_value,
    ABS(o.feature_value - b.feature_value) AS abs_diff
FROM online_feature_log o
JOIN offline_feature_backtest b
  ON o.user_id = b.user_id
 AND o.feature_key = b.feature_key
 AND o.prediction_ts = b.prediction_ts
WHERE o.feature_key = 'user_avg_watch_time_1h'
  AND ABS(o.feature_value - b.feature_value) > 0.01;
```

If this query starts returning many rows, you likely have skew, a backfill bug, or a timestamp-alignment problem.

### 4. Feature Drift & Monitoring

Feature drift is a production data-quality problem first and a model-quality problem second. The DE owns the monitoring surface that tells the ML team when the serving distribution no longer looks like the training distribution.

#### 4.1 Distribution-shift detection

Useful drift checks:

- Mean/median change for continuous features.
- Percentile movement (`p50`, `p95`, `p99`).
- Bucket distribution changes for categorical features.
- Null-rate increase.
- Coverage drop: the percentage of requests with the feature present.

Example monitoring table:

| feature_key | ds | p50 | p95 | null_rate | coverage_rate |
|---|---|---:|---:|---:|---:|
| `user_avg_watch_time_1h` | `2026-07-27` | `8.1` | `42.4` | `0.02` | `0.99` |
| `user_avg_watch_time_1h` | `2026-07-28` | `3.4` | `17.8` | `0.19` | `0.81` |

That pattern suggests a pipeline issue before you even ask whether the model should be retrained.

#### 4.2 Retraining triggers

Retraining triggers should be tied to both data and business evidence.

Typical triggers:

- Sustained feature-distribution shift beyond agreed thresholds.
- Label-distribution shift.
- Model-quality decay in online metrics.
- New product surfaces or logging changes that materially alter the feature space.

A mature answer separates three decisions:

1. **Do we have a data-quality issue?** Example: null rate spiked due to a bad upstream deploy.
2. **Do we have a product-behavior shift?** Example: new Reel surface changed user engagement patterns.
3. **Do we need retraining or feature redesign?** Example: the model is now stale even though the pipeline is healthy.

If you frame drift this way, you sound like someone who can operate ML infrastructure, not just describe buzzwords.
