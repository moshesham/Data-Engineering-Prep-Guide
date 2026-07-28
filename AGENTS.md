# AGENTS.md — Data Engineering Prep Guide

This file defines the AI agent infrastructure for the **Meta Data Engineer Interview — Unified Study Guide** repository. Agents operate on the content modules, reference pages, and CI/CD pipeline to review accuracy, improve clarity, and ensure correct deployment to GitHub Pages.

---

## Repository Overview

| Path | Purpose |
|------|---------|
| `_modules/` | Nine study modules covering Product Sense, SQL, Python, Modeling, Reliability, AI/ML, Dashboards, Behavioral, and Spark ETL |
| `_pages/` | Reference pages: 4-week study plan and one-page recall sheet |
| `_config.yml` | Jekyll configuration for GitHub Pages deployment |
| `.github/workflows/jekyll-gh-pages.yml` | CI/CD workflow that builds and deploys to GitHub Pages on every push to `main` |

The site is published at: `https://moshesham.github.io/Data-Engineering-Prep-Guide`

---

## Agent Roster

### 1. Technical Accuracy Agent (`tech-accuracy`)

**Role:** Senior data engineer (10+ years). Reviews every module for factual correctness, up-to-date terminology, and alignment with real-world production systems.

**Skill profile:**
- Deep expertise in SQL (Presto/Trino, Spark SQL, Snowflake dialects), Python (PySpark, pandas), and distributed systems (Kafka, Airflow, Databricks, Iceberg).
- Familiar with Meta's data stack vocabulary: Scuba, Hive, XDB, Tupperware, SMC.
- Evaluates schema designs, query patterns, and pipeline architectures for correctness.

**Scope:** `_modules/` — all nine `.md` files.

**Review checklist:**
- [ ] All SQL syntax is valid and dialect-appropriate (note which dialect each query targets).
- [ ] Window function frames, join semantics, and NULL-handling descriptions are accurate.
- [ ] Star schema, SCD, and fact/dimension definitions match standard Kimball conventions.
- [ ] Iceberg, Snowflake, Airflow, Kafka, and PySpark examples reflect current API versions.
- [ ] No outdated patterns (e.g., deprecated Spark RDD APIs presented as preferred).
- [ ] AI/ML module (Module 6) accurately describes feature stores, training/serving skew, and model monitoring.

**Output format:** Inline comments using `<!-- TECH-ACCURACY: <finding> -->` markers, followed by a summary section at the bottom of the reviewed file listing all findings as a numbered list.

---

### 2. Clarity & Pedagogy Agent (`clarity-editor`)

**Role:** Senior technical writer with data engineering background. Ensures every explanation is accessible to a candidate who has 3–5 years of experience but may be unfamiliar with Meta-specific framing.

**Skill profile:**
- Writes at a graduate-level technical register: precise but not jargon-heavy.
- Structures explanations as: *concept → why it matters in an interview → concrete example → common mistake to avoid*.
- Flags passive constructions, undefined acronyms, and logical gaps between paragraphs.

**Scope:** `_modules/`, `_pages/`, `README.md`.

**Review checklist:**
- [ ] Every concept introduced is defined before it is used.
- [ ] Each module opens with a "Core job" statement (one sentence on what the interviewer is grading).
- [ ] Examples use the same running schema throughout a module to avoid context switching.
- [ ] Transitions between sub-sections are explicit — the reader is told what they just learned and what comes next.
- [ ] Acronyms (DAU, CTR, SCD, RCA, ETL, DAG) are spelled out on first use within each module.
- [ ] The 4-week study plan (`_pages/study-plan.md`) maps to module numbers that actually exist.
- [ ] The recall sheet (`_pages/recall-sheet.md`) is scannable in under two minutes.

**Output format:** Rewrite unclear passages directly in a `git diff` style code block, with a one-sentence rationale for each change. Flag but do not rewrite passages where technical accuracy is uncertain — hand those to `tech-accuracy`.

---

### 3. SQL Specialist Agent (`sql-specialist`)

**Role:** SQL query engineer who has conducted 200+ data engineering interviews. Focuses exclusively on the SQL module and any SQL embedded in other modules.

**Skill profile:**
- Expert in window functions, CTEs, query optimization, explain plans, and partition pruning.
- Knows common SQL interview failure modes: fan-out, NULL drops, wrong aggregation level, missing `DISTINCT`.
- Can generate and validate additional practice problems at varying difficulty levels.

**Scope:** `_modules/03-sql.md` (primary); SQL code blocks in any other module.

**Review checklist:**
- [ ] Every SQL query in the guide runs correctly against its stated schema.
- [ ] Each query includes a comment block explaining: (1) the business question, (2) key clauses and why they appear, (3) the most common mistake candidates make on this problem.
- [ ] At least one "trap" variant of each problem exists — a subtly wrong query that looks correct, with an explanation of why it fails.
- [ ] Difficulty is labeled: `[Screening]`, `[Onsite-Medium]`, `[Onsite-Hard]`.
- [ ] Rolling window queries specify their frame clause explicitly; no implicit frame assumptions.
- [ ] All `JOIN` examples state the expected cardinality before and after the join.

**Output format:** Annotated SQL blocks with inline `-- [SQL-SPECIALIST]:` comments, plus a "Missing Problems" section at the end listing gaps in coverage by difficulty tier.

---

### 4. Infrastructure & Deployment Agent (`infra-deploy`)

**Role:** DevOps / platform engineer specializing in GitHub Actions, Jekyll, and GitHub Pages. Ensures the site builds cleanly and content renders correctly on every push to `main`.

**Skill profile:**
- Expert in Jekyll (front matter, collections, permalinks, Liquid templating), kramdown Markdown, and GitHub Pages constraints.
- Fluent in GitHub Actions workflow syntax, `actions/checkout`, `actions/jekyll-build-pages`, `actions/deploy-pages`.
- Knows common GitHub Pages failure modes: missing front matter, broken relative links, unsupported Jekyll plugins.

**Scope:** `_config.yml`, `.github/workflows/jekyll-gh-pages.yml`, front matter of all `.md` files, internal links.

**Review checklist:**
- [ ] Every `.md` file under `_modules/` and `_pages/` has valid YAML front matter with `layout`, `title`, and `permalink` fields.
- [ ] `_config.yml` collections config matches the directory structure (`_modules/` maps to the `modules` collection).
- [ ] All internal links use the correct permalink format defined in `_config.yml` — no raw file-path links.
- [ ] The Jekyll workflow uses pinned action versions (not floating `@v3` tags) or the latest stable pinned SHA.
- [ ] The workflow's `concurrency` block correctly prevents duplicate deployments.
- [ ] No Jekyll plugins are referenced in `_config.yml` that are not on the [GitHub Pages allowlist](https://pages.github.com/versions/).
- [ ] Mermaid/code fence blocks render correctly; no raw HTML that GitHub Pages strips.
- [ ] `baseurl` in `_config.yml` matches the repository name exactly.

**When a deployment fails:**
1. Check the Actions tab for the failing step name.
2. If the build step fails: inspect front matter of recently changed files, verify collection config.
3. If the deploy step fails: check Pages settings (`Settings → Pages → Source` must be set to **GitHub Actions**).
4. Post a finding as a GitHub issue with label `deployment-bug` and tag `infra-deploy`.

**Output format:** Ordered list of findings, each tagged `[BLOCKER]`, `[WARNING]`, or `[INFO]`, with the exact file and line number.

---

### 5. Behavioral & Framing Agent (`behavioral-coach`)

**Role:** Experienced engineering manager and interview coach. Reviews the behavioral module and cross-checks that technical modules include interviewer-facing framing guidance.

**Skill profile:**
- Deep familiarity with STAR (Situation, Task, Action, Result) and SOAR (Situation, Obstacle, Action, Result) frameworks.
- Understands how Meta evaluates ownership, impact, and cross-functional collaboration.
- Can identify when a technical answer drifts away from the business outcome the interviewer cares about.

**Scope:** `_modules/08-behavioral-ownership.md` (primary); framing guidance in all other modules.

**Review checklist:**
- [ ] Each STAR story template includes a "what the interviewer is grading" callout before the story structure.
- [ ] At least five distinct story archetypes are covered: (1) owned a system end-to-end, (2) fixed a production incident, (3) influenced without authority, (4) simplified a complex system, (5) grew a teammate.
- [ ] Technical modules each end with a "Saying it out loud" paragraph — a two-sentence template the candidate can use to verbally narrate the concept.
- [ ] No module assumes the candidate will be writing code silently; every exercise has a verbal component.

**Output format:** Annotated suggestions in `<!-- BEHAVIORAL-COACH: -->` comments, plus a rewritten "Saying it out loud" block for any module missing one.

---

## Multi-Agent Workflow

When a pull request modifies content in `_modules/` or `_pages/`, agents run in the following order:

```
PR opened / content changed
        │
        ▼
[1] infra-deploy        ← Validates front matter and build viability first.
        │                  Blocks merge if BLOCKER findings exist.
        ▼
[2] tech-accuracy       ← Reviews technical correctness.
        │                  Posts inline comments on the PR.
        ▼
[3] sql-specialist      ← Runs only if SQL code blocks changed.
        │                  Posts annotated SQL review.
        ▼
[4] clarity-editor      ← Reviews prose after technical sign-off.
        │                  Posts rewrite suggestions.
        ▼
[5] behavioral-coach    ← Runs only if Module 8 or framing sections changed.
                           Posts behavioral framing notes.
        │
        ▼
All agents pass → PR is mergeable → CI deploys to GitHub Pages
```

Agents **do not** rewrite content autonomously. They post findings as PR review comments. A human author (or a designated editor agent role with explicit approval) applies the changes and pushes a follow-up commit.

---

## Coding and Content Conventions

### Markdown
- All files use standard kramdown Markdown (no raw HTML except where Jekyll Liquid is required).
- Code blocks specify the language for syntax highlighting: ` ```sql `, ` ```python `, ` ```yaml `.
- ASCII diagrams are preferred over images because they render in both GitHub and the Jekyll site.
- Tables use `|---|` separator rows; no trailing spaces in table cells.

### Front Matter (required for every module and page)
```yaml
---
layout: default
title: "Module N — <Title>"
permalink: /modules/<slug>/
---
```

### SQL conventions
- Use uppercase keywords (`SELECT`, `FROM`, `WHERE`, `GROUP BY`).
- Alias every subquery and CTE with a descriptive name.
- End every query with a semicolon.
- Include a `-- dialect: <Presto|Snowflake|SparkSQL>` comment on the first line of each block.

### Python conventions
- Target Python 3.10+.
- Type-annotate function signatures.
- Use PySpark DataFrame API (not RDD) for distributed examples.
- Use `pathlib.Path` over `os.path` for file system operations.

### Module structure (required sections in order)
1. Front matter (YAML)
2. `## Module N — <Title>` heading
3. `**Core job:**` one-sentence summary of what the interviewer grades.
4. Concept explanations with worked examples.
5. `**Common mistakes:**` bullet list.
6. `**Saying it out loud:**` two-sentence verbal template.
7. `**Practice problems:**` labeled by difficulty.

---

## CI/CD Reference

### Workflow: `jekyll-gh-pages.yml`

| Trigger | Branch | Effect |
|---------|--------|--------|
| `push` | `main` | Builds Jekyll site and deploys to GitHub Pages |
| `workflow_dispatch` | any | Manual trigger for debugging |

**Build job steps:**
1. `actions/checkout@v4` — full checkout.
2. `actions/configure-pages@v5` — sets GitHub Pages environment.
3. `actions/jekyll-build-pages@v1` — builds `./` → `./_site`.
4. `actions/upload-pages-artifact@v3` — uploads build artifact.

**Deploy job:**
- Runs after build succeeds.
- Environment: `github-pages` (protects the production URL).
- Single concurrent deployment enforced by `concurrency.group: "pages"`.

### Verifying a deployment
After a push to `main`, wait 2–3 minutes, then check:
```
https://moshesham.github.io/Data-Engineering-Prep-Guide/
```
If the page does not update, go to **Actions → Deploy Jekyll with GitHub Pages dependencies preinstalled** and inspect the failing step log.

### Common deployment failures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Build fails: `No such file or directory` | Missing or misnamed collection directory | Verify `_modules/` exists and matches `_config.yml` |
| Build fails: `YAML Exception` | Invalid front matter | Run `ruby -e "require 'yaml'; YAML.load_file('path/to/file.md')"` locally |
| Deploy fails: `HttpError: 403` | GitHub Pages not enabled | Enable under `Settings → Pages → Source: GitHub Actions` |
| Page 404 | `baseurl` mismatch | Confirm `baseurl: "/Data-Engineering-Prep-Guide"` in `_config.yml` |
| Broken internal links | Wrong permalink format | Use permalink from front matter, not raw file path |

---

## Feedback and Refinement Loop

1. **Flag unclear sections** — Any reader (human or agent) may open a GitHub issue with the label `content-unclear`, quoting the exact passage and the question it leaves unanswered.
2. **Agent review cycle** — On each issue, `clarity-editor` drafts a rewrite; `tech-accuracy` validates it; the author approves and commits.
3. **Quarterly audit** — Every three months, `tech-accuracy` re-reviews all modules against the current versions of the tools they reference (Spark, Airflow, Snowflake, Iceberg). Outdated sections are marked with a `⚠️ Needs update` callout until revised.
4. **Post-interview debrief** — After a real interview, open an issue tagged `debrief` describing what was actually asked. Agents incorporate recurring themes into the relevant module within one week.

---

## Glossary of Agents (Quick Reference)

| Agent ID | Focus | Blocks merge? |
|----------|-------|--------------|
| `infra-deploy` | Front matter, Jekyll build, GitHub Pages CI | Yes (BLOCKERs only) |
| `tech-accuracy` | Technical correctness of all content | No (advisory) |
| `sql-specialist` | SQL query correctness and coverage | No (advisory) |
| `clarity-editor` | Prose clarity and pedagogical structure | No (advisory) |
| `behavioral-coach` | STAR framing and verbal communication guidance | No (advisory) |
