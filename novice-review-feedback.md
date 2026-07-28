# Novice Review Feedback — Meta DE Interview Prep Guide

**Reviewer persona:** Someone with solid software engineering experience but limited prior exposure to data warehousing, dimensional modeling, or large-scale data infrastructure. Has written SQL but never designed a star schema. Has used Python but never processed streaming events at scale.

**Purpose:** This document is a candid readthrough from a novice perspective, flagging every point where a first-time reader would be confused, lost, or lacking the context to apply the material. It is intended to be picked up by another reviewer or editor who will decide which gaps to close.

**Scope:** All 9 modules plus the README, reviewed in reading order.

---

## README.md

### What works well
- The interview loop diagram is immediately clarifying — knowing the exact structure (recruiter → technical screen → 3 onsite blended + 1 behavioral) helps frame all the modules.
- The "where your background maps" table is excellent for an experienced engineer new to the Meta framing.
- The dependency map at the bottom is helpful for understanding how to sequence study.

### Clarity gaps

**Gap R-1 — What is a "Blended round" exactly?**
The README says each blended round covers "Product Sense → Data Model → SQL → Python" in 45 minutes. A novice reader will want to know: does the interviewer explicitly announce which phase they're on? Does the candidate propose the schema, or does the interviewer hand one over? A single sentence explaining the *format* of a blended round (interviewer gives an open-ended prompt, candidate leads the conversation) would help enormously.

**Gap R-2 — "Drift" is introduced without definition.**
The sentence "most candidates lose points on drift" uses the word without defining it in the README context. The concept is explained later in Module 3, but a reader who doesn't know it will be confused here.

**Gap R-3 — Module 9 is listed under "Reference Modules" but the label is never explained.**
Why is Spark a "reference" module? Is it less important? Less likely to appear? A one-line note ("Spark knowledge is assessed in later-stage blended rounds or take-home tasks, not usually in the initial screen") would help readers prioritize.

---

## Module 1 — Product Sense & Metrics

### What works well
- The North Star metrics table by product surface is concrete and interview-ready.
- The L1/L2 decomposition worked example (Reels watch time tree) is excellent — seeing the math in the tree makes it click.
- Multiple worked RCA cases (Reels, Marketplace, Messenger, Ads) give the pattern enough repetitions.

### Clarity gaps

**Gap 1-1 — "DAU = New + Retained + Resurrected" is not explained.**
This formula appears in Section 1.2 without defining what "Resurrected" means. A novice will assume it means users who were previously inactive and came back — but that should be confirmed with a one-line definition. Also, "New" and "Retained" need brief definitions (first-time users vs. users who were active the prior day).

**Gap 1-2 — "Guardrail" concept is defined but the relationship to guardrails in A/B tests is confusing.**
Section 1.3 defines guardrails as metrics you must not break. Section 2.1 introduces "guardrail metrics" again in the context of an A/B test. A novice reading both will wonder: are these the same thing? Why do guardrails get mentioned in two separate places? A cross-reference sentence would help: "These guardrails are the same metrics you monitor in Section 1.3 — you track them during an experiment to ensure the new feature doesn't damage them."

**Gap 1-3 — Novelty effect explanation is brief.**
Section 2.2 mentions the novelty effect but doesn't give a concrete example of what the data looks like during a novelty spike. A reader who has never run an A/B test won't know *why* this matters until seeing a chart showing a spike at launch that then decays. Even a simple table of week-1, week-2, week-4 values showing the pattern would make this tangible.

**Gap 1-4 — Attribution models section (2.3) is brief.**
Last-touch vs. multi-touch is mentioned but not demonstrated. A novice won't know how this affects metric design. One worked example (a user sees 3 ads before purchasing — what revenue gets credited to each ad under each model?) would make this applicable.

**Gap 1-5 — The "define the metric for a new launch" example could be clearer on what "new" means.**
The worked example for a Reels reaction launch is good. However, it's not immediately obvious why a *launch* RCA is structurally different from a drop RCA. A one-sentence explicit statement would help: "A launch prompt asks you to invent a metric definition; a drop prompt asks you to diagnose a change in an existing metric. They require different opening moves."

---

## Module 2 — Data Modeling & Schema Design

### What works well
- The grain determination exercise ("model ad performance") is one of the best additions — it shows *how to think*, not just what to know.
- The Marketplace and Messenger star schemas make the pattern concrete across multiple surfaces.
- The SCD Type 4 and Type 6 definitions fill a meaningful gap.

### Clarity gaps

**Gap 2-1 — "Surrogate key" is mentioned but not explained for newcomers.**
Section 2's SCD discussion references surrogate keys without defining them. A novice coming from application development will know what a primary key is but not necessarily what "surrogate" means in the DWH context (a synthetic integer key generated by the warehouse, not the natural business key). One sentence of definition is all that's needed.

**Gap 2-2 — The schema diagrams use ASCII art with no caption or explanation of notation.**
The star schema diagrams (e.g., the Reels schema with 1:N arrows) are excellent but assume the reader knows what 1:N means. A brief key — "1:N means one record in the parent table joins to many records in the child table" — would help readers who haven't seen ERD notation before.

**Gap 2-3 — SCD Type 4 and Type 6 examples feel brief relative to Type 2.**
Type 2 gets a full table showing `start_ds`, `end_ds`, `is_current`. Type 4 gets a description and a schema, but no populated sample rows. Type 6 gets an explanation but no concrete before/after rows. For a topic that interviewers "sometimes push past Type 2 to test," this feels thin. Adding a two-row example table for Type 4 and Type 6 would close this gap.

**Gap 2-4 — Schema evolution section doesn't explain WHY clients break.**
Section 4.2 explains that adding a required field breaks deployed clients, but doesn't explain the mechanism to a novice. The mechanism is: existing clients that were built before the field existed will not emit it, so the field will be missing/null in their log payloads. A one-sentence clarification of this would make the "backward compatibility" concept land.

**Gap 2-5 — Junk dimensions and degenerate dimensions are defined but not illustrated.**
Section 2.3 defines both terms. A junk dimension is never shown with an example schema. A novice cannot apply a definition without seeing what a junk dimension table actually looks like vs. putting those columns directly in the fact table. A small example (4-5 flag columns that become a junk dimension) would close this.

---

## Module 3 — SQL

### What works well
- The funnel query is the highest-value addition in the guide. Seeing the exact SQL for impression → watch → like → share makes abstract funnel concepts concrete.
- The sessionization (gaps-and-islands) query is excellent and clearly commented.
- The WHERE/HAVING/QUALIFY table is immediately memorizable.
- The anti-join with both NOT EXISTS and LEFT JOIN / IS NULL patterns side-by-side is helpful.

### Clarity gaps

**Gap 3-1 — The QUALIFY clause needs a caveat.**
Section 1.1 mentions QUALIFY but doesn't note that it's not available in all warehouses — it's Snowflake-native and newer. A reader preparing for a Presto/Hive context might assume they can use it and look wrong. A one-line note ("QUALIFY is supported in Snowflake and BigQuery; in Presto/Hive, wrap in a subquery and filter on the window result") would prevent this mistake.

**Gap 3-2 — NULL three-valued logic: the NOT IN trap is mentioned but not demonstrated.**
Section 1.2 says "NOT IN behaves unexpectedly if the subquery contains NULL." A novice won't understand *how* it goes wrong without a concrete example. Showing `WHERE user_id NOT IN (SELECT user_id FROM blocklist)` failing silently when one `user_id` in the blocklist is NULL would make this immediately memorable.

**Gap 3-3 — The funnel query uses a conditional COUNT pattern that isn't explained.**
The funnel SQL uses `COUNT(DISTINCT CASE WHEN event_type = 'impression' THEN user_id END)` which is a powerful but non-obvious idiom. A first-time reader will not know why this works. A one-sentence comment — "CASE WHEN returns NULL for rows that don't match, and COUNT(DISTINCT ...) ignores NULLs, so this counts only users who hit this step" — would make the pattern transferable.

**Gap 3-4 — The cohort retention query is complex and has no diagram showing the join logic.**
The query chains multiple CTEs (`first_signup`, `d1_retained`, `d7_retained`, `d30_retained`) and the relationship between them is not immediately obvious. A small diagram or narrative explanation of "we build the cohort spine first, then LEFT JOIN each retention window against it" would help a reader understand the structure before reading the SQL.

**Gap 3-5 — The sessionization query's "session boundary" logic could be explained more explicitly.**
The LAG + SUM trick for sessionization is clever but not obvious on first read. Specifically, the step where `SUM(is_new_session) OVER (...)` creates a session ID is a non-obvious use of cumulative sums. A one-line comment inside the SQL like `-- running sum of session starts = session identifier` would make it click.

**Gap 3-6 — ROWS vs. RANGE section is brief.**
Section 3.3 defines the difference but doesn't show when RANGE causes unexpected results (e.g., when two rows have the same ORDER BY value, RANGE includes all peers while ROWS does not). A two-row tie example would make this practical.

---

## Module 4 — Python

### What works well
- The top-K heap worked example is concrete and well-explained.
- The mutual-connections set problem directly maps to the social-graph framing Meta uses.
- The defensive log parsing example with a malformed line shows the right habits.
- Explicit Big-O analysis on every problem is excellent discipline.

### Clarity gaps

**Gap 4-1 — `heapq.nlargest` vs. manual min-heap: the tradeoff is not explained.**
The top-K solution uses `heapq.nlargest`. A novice will accept this, but an interviewer may ask "what if the list doesn't fit in memory?" The solution should note when to prefer `heapq.nlargest` (fits in memory, simpler) vs. a manual min-heap of size K that streams input (memory-bounded O(K) space regardless of N). Adding two sentences on this tradeoff would complete the answer.

**Gap 4-2 — The concurrent overlaps problem (sweep-line) is the most algorithmically complex section and the explanation moves fast.**
The event-decomposition trick (splitting each session into a +1 start event and a -1 end event, then sorting and scanning) is non-obvious. A reader unfamiliar with sweep-line algorithms will follow the code but not understand *why* it works. Walking through a three-row example by hand before showing the code would make this transferable to novel problems.

**Gap 4-3 — Variable-size sliding window section is brief.**
Section 4.2 defines the pattern but the worked example is short. Variable-size windows (expand right, contract left when a condition is violated) are a common interview pattern. A worked problem like "find the longest subarray where the average watch time exceeds a threshold" with explicit expand/contract logic annotated would be stronger.

**Gap 4-4 — Defensive log parsing: the regex pattern isn't explained.**
The regex used for log parsing is correct but not annotated. A novice who hasn't used Python `re` will not know what each group captures. Inline comments on the regex components (e.g., `(\d{4}-\d{2}-\d{2})` matches a date like 2026-07-20) would make the example educational rather than just a reference.

---

## Module 5 — Pipeline Reliability

### What works well
- The delivery semantics primer is one of the most important additions — it was genuinely missing context. The Kafka crash example makes the three semantics immediately concrete.
- The Airflow DAG code is real and runnable — this is much more useful than pseudocode.
- The data-quality gate thresholds (±5% row count, < 0.1% null rate on PK) give the guide something concrete to cite in an interview.

### Clarity gaps

**Gap 5-1 — "Exactly-once semantics" caveat is not given.**
Section 1.1 correctly describes exactly-once as hard to achieve end-to-end. But a novice will still wonder: does Kafka support it? Does Spark? The guide should note that Kafka transactions + Spark Structured Streaming can achieve end-to-end exactly-once in some configurations, but this requires transactional sinks and is not the default. Without this, a reader might claim "Kafka gives us exactly-once" in an interview and be wrong.

**Gap 5-2 — "Atomic swap" is mentioned but not explained for a reader unfamiliar with partitioned storage.**
Section 2.1 describes the staging → atomic swap pattern with a diagram. But "atomic swap" might not be meaningful to someone who doesn't know how partitioned tables work on S3/HDFS/Iceberg. A one-sentence explanation — "Atomic swap means we move the staging partition into the target location in a single metadata operation, so readers either see the old data or the new data, never a partial write" — would help.

**Gap 5-3 — Watermarking section references Module 9 but doesn't self-explain.**
Section 3.1 says to see Module 9 Structured Streaming for watermarking implementation. A reader reading Module 5 in isolation will be left without enough context to use watermarking in an interview. A one-paragraph self-contained explanation here (even if Module 9 has more detail) would make the module stand alone.

**Gap 5-4 — The Airflow DAG references `SparkSubmitOperator` without noting that the `apache-airflow-providers-apache-spark` package is required.**
This is a minor but real gap — an interviewer who follows up with "how would you deploy this?" will expose the gap if the reader doesn't know about provider packages. One line noting the provider dependency would complete the answer.

**Gap 5-5 — SLA monitoring: the guide defines the SLA but doesn't explain how to detect a breach at runtime.**
Section 5.2 describes how to define an SLA (6:00 AM partition landing, alert by 6:15). The Airflow `sla` parameter is shown. But the guide doesn't explain what Airflow actually does when an SLA is missed — it triggers the `sla_miss_callback`. A one-line explanation of when `sla_miss_callback` fires (when the task hasn't finished within the `sla` duration after the DAG's scheduled time) would make this operational.

---

## Module 6 — AI/ML Infrastructure

### What works well
- The feature store table shape with dual timestamps (`event_ts` + `ingestion_ts`) and the explanation of why both are needed is excellent.
- The training-serving skew bug is the most valuable worked example — it's concrete, realistic, and shows both the symptom and the fix.
- The point-in-time join example makes "data leakage" tangible instead of abstract.

### Clarity gaps

**Gap 6-1 — ANN (Approximate Nearest Neighbor) search is introduced but the "why approximate" is not explained.**
Section 2.2 describes ANN search for embeddings. A novice will want to know why approximation is acceptable here. The answer (exact nearest-neighbor search over billions of vectors is computationally infeasible; ANN trades a small recall loss for orders-of-magnitude speedup) is not given. Two sentences would close this.

**Gap 6-2 — The online store vs. offline store distinction could use a latency number.**
Section 1.1 says the online store is "low-latency." A novice doesn't know what "low-latency" means in this context. Saying "online stores typically serve features with < 10ms P99 latency; offline stores may take seconds to minutes to query" would make the distinction concrete.

**Gap 6-3 — "Distribution shift" is used but not defined.**
Section 4.1 introduces distribution shift as the core of feature drift. A reader who hasn't taken an ML course won't know what "distribution" refers to here. A one-sentence definition — "the statistical distribution of feature values at serving time has shifted away from the distribution seen during training, so the model's expectations are violated" — would help.

**Gap 6-4 — The architecture diagram at the top of the module is good, but "Batch data lake" and "Feature store" are boxes that a novice may conflate.**
Some readers will wonder: are these the same system? A one-sentence clarification in the diagram's caption — "the feature store is a separate low-latency serving layer on top of, not a replacement for, the batch data lake" — would prevent confusion.

---

## Module 7 — Dashboards & Reporting

### What works well
- The three-layer dashboard architecture (KPI → drill-down → raw events) is clear and immediately applicable.
- The funnel and cohort backing schemas are concrete and complete — exactly what was missing before.
- The anomaly detection SQL with a rolling z-score is sophisticated and shows how to operationalize alerting.

### Clarity gaps

**Gap 7-1 — The funnel schema has two options (user-level vs. aggregate) but doesn't say which is more common in practice.**
Section 3.1 presents both schema options without a recommendation. A novice preparing for an interview needs to know which to present as default and which as an alternative. A sentence like "Default to the aggregate schema for dashboard performance; only use the user-level schema if the dashboard needs to drill down to individual users" would help.

**Gap 7-2 — The cohort matrix schema mentions "day_offset" but doesn't explain how D0/D1/D7/D30 map to it.**
Section 4.1 uses `day_offset` as a column. A reader unfamiliar with cohort analysis will wonder: is D1 offset = 1? Is it exactly one day or within 1–7 days? Clarifying that D1 = day_offset = 1 (exactly the next calendar day), D7 = day_offset = 7 (exactly 7 days after signup), etc., would remove ambiguity.

**Gap 7-3 — The anomaly detection SQL uses a z-score approach but doesn't explain what a z-score means.**
Section 5.1 shows SQL computing `(value - avg) / stddev`. A reader who hasn't studied statistics won't know what the resulting number represents or why a threshold of 2 (standard deviations) is reasonable. A one-sentence explanation — "a z-score measures how many standard deviations a value is from the mean; a score above 2 indicates the value is unusually far from normal" — would make this accessible.

**Gap 7-4 — The relationship between the funnel in Module 7 and the funnel SQL in Module 3 is referenced but not shown explicitly.**
Section 3.2 says "see Module 3 for the SQL" but doesn't show how the Module 3 query output maps to the backing schema defined in Module 7. A reader who has studied both would be able to connect them, but an explicit sentence — "the Module 3 funnel query's output matches the aggregate funnel schema column for column" — would make the cross-module connection explicit.

---

## Module 8 — Behavioral & Ownership

### What works well
- The five story archetypes make a formerly thin module much more useful.
- The story bank template with explicit S/T/A/R prompts is the most immediately actionable addition.
- The drill-down handling section addresses a real interview gap — most guides end at the STAR story and don't prepare candidates for follow-up.

### Clarity gaps

**Gap 8-1 — The STAR timing guidance (10–15s Situation, 35–45s Action) assumes the reader can calibrate this without practice.**
The guide states the timing but doesn't give a concrete mechanism for practicing it. Adding a sentence like "Record yourself answering and use a stopwatch — most people spend 40+ seconds on Situation and under 20 seconds on Action in their first attempt" would give the reader an actionable calibration technique.

**Gap 8-2 — The conflict story archetype could clarify what "conflict" means in this context.**
The worked example is a technical disagreement about feature engineering. Some readers will wonder if "conflict" includes interpersonal disagreements, or if Meta only wants professional/technical disagreements. A clarifying sentence — "Meta behavioral questions about conflict are looking for professional or technical disagreements, not interpersonal friction; keep the story about a decision or tradeoff, not a personality issue" — would prevent candidates from choosing the wrong story.

**Gap 8-3 — The failure story template's "what changed afterward" section needs more guidance.**
The archetype shows what went wrong and what the immediate fix was. But the most important part — "what changed in your process afterward" — is thin. Interviewers specifically probe whether the candidate made a systemic change or just fixed the instance. Providing two examples of process-change answers (e.g., "I added automated row-count assertions to every pipeline I built afterward" vs. "we fixed the bug") would show readers what a strong answer looks like here.

**Gap 8-4 — Meta values mapping is brief and lacks concrete connection to the stories.**
Section 3 lists the three Meta values but doesn't explicitly match each archetype to the most relevant value. For example: "The failure/mistake story maps most directly to Be Bold / Ownership." Adding a table that maps each of the 5 story categories to its primary Meta value would make this immediately usable in interview prep.

**Gap 8-5 — The story bank template uses real employer names (JPMorgan, Citi, BrightSource, IMF).**
This is appropriate context for the specific reader but would be confusing to any other person picking up the guide. If this guide is ever used by others, those employer references should either be removed or clearly labeled as "replace with your own employers." Currently the template reads as if those are the expected answers, not prompts for the reader's own history.

---

## Module 9 — Apache Spark

### What works well
- The small-file/compaction section is concise and gives both the diagnosis and the code fix.
- The Spark UI skew walkthrough (ASCII art of healthy vs. skewed stage) makes a visual concept text-accessible.
- The Airflow-to-Spark DAG closes the loop between pipeline orchestration and actual Spark jobs.
- The `pandas_udf` example with a direct contrast to a plain UDF makes the performance difference concrete.

### Clarity gaps

**Gap 9-1 — "Lazy evaluation" is mentioned but the consequence is not fully explained for novices.**
Section 1 correctly states that Spark is lazy until an action fires. But a novice may not understand what goes wrong if they forget this: e.g., they might cache a DataFrame thinking it's materialized, then wonder why the cache is empty. A one-line example — "if you call `.cache()` and then `.count()`, the cache is populated by the count action; if you call `.cache()` and then `.write()`, the write action materializes and caches simultaneously" — would prevent a common confusion.

**Gap 9-2 — `spark.executor.memoryOverhead` is listed in the config table but the off-heap vs. on-heap distinction is not explained.**
A reader new to JVM-based systems won't know what "off-heap" means. A one-sentence clarification — "overhead memory is used by the Python process in PySpark, native memory for I/O buffers, and Kryo serialization; OOMs that say 'overhead limit exceeded' come from here, not the JVM heap" — would make this actionable.

**Gap 9-3 — The SCD Type-2 merge code uses `delta.tables.DeltaTable` but the Iceberg equivalent is not shown.**
Section 6.1 shows a Delta Lake merge. The module introduction says to use Iceberg. A reader using an Iceberg-based stack (which is common at Meta) will wonder how to express the same merge in Iceberg. A short note — "in Iceberg, the equivalent is a `MERGE INTO` SQL statement or the Iceberg Python API's `MergeIntoTable`" — would bridge this.

**Gap 9-4 — The Airflow-to-Spark DAG references `SparkSubmitOperator` but doesn't mention that cluster mode vs. client mode affects where the driver runs.**
This is a common interview follow-up: "what happens if the Airflow task runs in client mode?" (the driver runs on the Airflow worker and can OOM or be killed by Airflow's task timeout). A one-line note on the `deploy-mode: cluster` setting in SparkSubmitOperator would prevent this gap.

**Gap 9-5 — The `pandas_udf` example doesn't explain the `@pandas_udf(return_type, functionType)` decorator parameters.**
Section 6.6 shows a `pandas_udf` with a decorator. A reader unfamiliar with the API won't know what `PandasUDFType.SCALAR` means or what the return type parameter does. A brief annotation of the decorator parameters would make the example self-contained.

---

## Cross-Module Clarity Gaps

These are gaps that span multiple modules and require attention to the guide as a whole:

**Gap X-1 — The guide uses `ds` as a date partition key throughout without ever defining the convention.**
A reader new to data warehousing will not know why the partition key is called `ds` (short for "date string" or "datestamp" — a common Hive/Meta convention). A brief note in Module 2 or the README would prevent confusion.

**Gap X-2 — The guide references "Presto" and "Hive" interchangeably with SQL but doesn't explain the relationship.**
For readers from other backgrounds, Presto, Hive, and Spark SQL all execute SQL against the same tables, but they are different query engines with different syntax support. A one-paragraph note (possibly in the README or Module 3) explaining that the SQL examples use ANSI SQL / Presto syntax would prevent confusion when a reader runs a query that uses a Hive-specific or Snowflake-specific function.

**Gap X-3 — The guide assumes familiarity with S3/HDFS paths in code examples.**
Paths like `s3://meta-raw-events/reel_view/ds=2026-07-20/` appear in multiple modules without explanation. For a reader who hasn't worked with cloud object storage, the Hive-partition convention in the path (`ds=2026-07-20`) is non-obvious. A one-sentence note explaining "paths with `key=value` segments are Hive-style partitions that Spark can automatically discover and prune" would help.

**Gap X-4 — There is no "how to run these examples" section.**
The Python and SQL examples are self-contained but some readers will want to run them locally. There is no guidance on how to set up a local Spark environment, or even what database/schema to run the SQL against. This is likely intentional (the guide is an interview prep guide, not a tutorial), but a brief disclaimer — "these examples are interview-style pseudocode using realistic table names; they are not intended to run against a production cluster without modification" — would prevent readers from spending time trying to execute them.

**Gap X-5 — The guide's worked examples all use Reels as the primary surface.**
Modules 2, 3, and 9 all use `fact_reel_impressions` as the central table. The new Marketplace and Messenger schemas are introduced in Module 2 but not carried through into the SQL (Module 3) or Spark (Module 9) examples. A reader who practices with the Reels example will feel unprepared if an interviewer switches to Marketplace mid-question. Cross-referencing the other schemas in the SQL module ("the same query patterns apply to `fact_marketplace_transactions` — try rewriting the rolling average using that table") would help.

---

## Priority Order for Remediation

Based on the gaps above, the following are the highest-priority items to address (listed by likely reader impact):

| Priority | Gap | Reason |
|---|---|---|
| 1 | Gap 3-3 (funnel CASE WHEN pattern unexplained) | Highest-frequency query pattern; not understanding the idiom means not being able to adapt it |
| 2 | Gap X-1 (`ds` convention undefined) | Appears in every module; small fix, high payoff |
| 3 | Gap 5-2 (atomic swap not explained) | Idempotent backfill is a core interview topic; the mechanism should be fully clear |
| 4 | Gap 4-2 (sweep-line algorithm logic not explained) | Concurrent overlaps is a hard problem; the "why it works" is needed to transfer to new problems |
| 5 | Gap 2-3 (SCD Type 4 and 6 have no sample rows) | If an interviewer pushes on these, the reader needs concrete examples, not just descriptions |
| 6 | Gap 3-4 (cohort retention query has no join logic diagram) | Complex query with no narrative walkthrough; readers risk memorizing without understanding |
| 7 | Gap 8-3 (failure story "what changed" section thin) | The follow-up on failure stories is where rounds are decided |
| 8 | Gap 6-1 (ANN "why approximate" not explained) | Easy to explain, likely to be probed |
| 9 | Gap 1-4 (attribution models not demonstrated) | A/B testing is common; last-touch vs. multi-touch needs a worked example |
| 10 | Gap 9-3 (no Iceberg equivalent for SCD merge) | Meta uses Iceberg; the Delta example may mislead |

---

*This feedback document was generated by reviewing the guide as a novice reader and noting every point of genuine confusion or missing context. It is not a critique of what exists — the guide is significantly stronger than its initial version — but a map of where the next round of editing should focus.*
