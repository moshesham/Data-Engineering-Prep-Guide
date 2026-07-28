---
layout: default
title: Module 6 — AI/ML Infrastructure
permalink: /modules/aiml-infrastructure/
---

## Module 6 — AI/ML Infrastructure

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

