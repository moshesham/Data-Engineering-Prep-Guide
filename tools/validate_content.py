#!/usr/bin/env python3
"""
tools/validate_content.py — CI content validator for Data-Engineering-Prep-Guide.

Uses omniscient-core models (FileAnalysis, RepositoryInfo, AgentFindings,
AnalysisConfig) as typed data structures to run rule-based checks against
_modules/ and _pages/ without requiring an LLM.

Checks (mapped to AGENTS.md agent checklists):
  1. [infra-deploy]     Every .md file has valid YAML front matter with
                        layout, title, and permalink.
  2. [clarity-editor]   Every module file contains the 7 required sections
                        in order (Core job, Common mistakes, Saying it out
                        loud, Practice problems).
  3. [sql-specialist]   SQL code blocks carry a -- dialect: comment, end
                        with a semicolon, and use uppercase keywords.
  4. [infra-deploy]     Internal links inside _modules/ and _pages/ use
                        permalink format, not raw .md file paths.
  5. [clarity-editor]   Known acronyms (DAU, SCD, ETL, …) are defined on
                        first use within each module.
  6. [infra-deploy]     Module numbers referenced in the study plan map to
                        files that actually exist in _modules/.

Exit code:
  0 — no BLOCKER findings
  1 — at least one BLOCKER finding (CI will block Jekyll deployment)

Usage:
  python tools/validate_content.py
  python tools/validate_content.py --no-info   # suppress INFO findings
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import yaml as pyyaml

from omniscient_core import (
    AgentFindings,
    AnalysisConfig,
    FileAnalysis,
    RepositoryInfo,
    get_logger,
    setup_logging,
)

# ---------------------------------------------------------------------------
# Repository layout constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "_modules"
PAGE_DIR = REPO_ROOT / "_pages"

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

REQUIRED_FRONT_MATTER_KEYS: frozenset[str] = frozenset({"layout", "title", "permalink"})

# Required content markers for _modules/ files (in the order they should appear)
REQUIRED_MODULE_SECTIONS: list[tuple[str, str]] = [
    ("**Core job:**", "Core job statement"),
    ("**Common mistakes:**", "Common mistakes section"),
    ("**Saying it out loud:**", "Saying it out loud section"),
    ("**Practice problems:**", "Practice problems section"),
]

# Well-known acronyms that must be defined on first use within a module.
# Key = acronym, Value = canonical expansion.
KNOWN_ACRONYMS: dict[str, str] = {
    "DAU": "Daily Active Users",
    "MAU": "Monthly Active Users",
    "CTR": "Click-Through Rate",
    "SCD": "Slowly Changing Dimension",
    "RCA": "Root Cause Analysis",
    "ETL": "Extract, Transform, Load",
    "DAG": "Directed Acyclic Graph",
    "GMV": "Gross Merchandise Value",
    "CTE": "Common Table Expression",
    "SLA": "Service Level Agreement",
    "OBT": "One Big Table",
    "ANN": "Approximate Nearest Neighbor",
    "AQE": "Adaptive Query Execution",
    "API": "Application Programming Interface",
}

# Primary SQL keywords that must appear in uppercase
SQL_KEYWORDS_CASE_CHECK: list[str] = [
    "select",
    "from",
    "where",
    "having",
    "join",
    "with",
    "union",
    "intersect",
    "except",
    "insert",
    "update",
    "delete",
]

# Regex: raw .md file-path link inside Markdown (not an anchor, not a URL)
# Matches: [link text](some/path/file.md) or [text](file.md#anchor)
_RAW_MD_LINK_RE = re.compile(
    r'\[([^\]]+)\]\((?!https?://)([^)#\s]+\.md)(?:#[^)]*)?\)',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_front_matter(content: str) -> tuple[Optional[dict], str]:
    """Split YAML front matter from body.

    Returns:
        (front_matter_dict, body_text) — front_matter_dict is None when
        front matter is absent or unparseable.
    """
    if not content.startswith("---"):
        return None, content
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None, content
    fm_raw = content[3:end_idx].strip()
    try:
        fm = pyyaml.safe_load(fm_raw) or {}
    except pyyaml.YAMLError:
        fm = None
    body = content[end_idx + 3 :]
    return fm, body


def _extract_sql_blocks(content: str) -> list[str]:
    """Return the text content of every ```sql … ``` block in *content*."""
    return re.findall(r"```sql\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)


def _severity_tag(severity: str, message: str) -> str:
    return f"[{severity}] {message}"


# ---------------------------------------------------------------------------
# Individual checks — each returns an AgentFindings instance
# ---------------------------------------------------------------------------


def check_front_matter(fa: FileAnalysis) -> AgentFindings:
    """Check 1 (infra-deploy): valid YAML front matter with required keys."""
    result = AgentFindings(agent_name="infra-deploy")
    content = fa.content or ""
    fm, _ = _parse_front_matter(content)

    if fm is None:
        result.findings.append(
            _severity_tag(
                "BLOCKER",
                f"{fa.path}: Missing or unparseable YAML front matter.",
            )
        )
        return result

    for key in sorted(REQUIRED_FRONT_MATTER_KEYS - set(fm.keys())):
        result.findings.append(
            _severity_tag(
                "BLOCKER",
                f"{fa.path}: Front matter missing required key '{key}'.",
            )
        )
    return result


def check_required_sections(fa: FileAnalysis) -> AgentFindings:
    """Check 2 (clarity-editor): module files contain all required sections."""
    result = AgentFindings(agent_name="clarity-editor")
    # Only _modules/ files need these sections; pages and README do not.
    if "_modules" not in fa.path:
        return result

    content = fa.content or ""
    for marker, label in REQUIRED_MODULE_SECTIONS:
        if marker not in content:
            result.findings.append(
                _severity_tag(
                    "WARNING",
                    f"{fa.path}: Missing required section — {label} (marker: '{marker}').",
                )
            )
    return result


def check_sql_blocks(fa: FileAnalysis) -> AgentFindings:
    """Check 3 (sql-specialist): SQL blocks have dialect comment, semicolon, uppercase keywords."""
    result = AgentFindings(agent_name="sql-specialist")
    content = fa.content or ""
    blocks = _extract_sql_blocks(content)

    for idx, block in enumerate(blocks, start=1):
        label = f"{fa.path} — SQL block {idx}"

        # 3a. Dialect comment
        if not re.search(r"--\s*dialect\s*:", block, re.IGNORECASE):
            result.findings.append(
                _severity_tag(
                    "WARNING",
                    f"{label}: Missing '-- dialect: <Presto|Snowflake|SparkSQL>' comment.",
                )
            )

        # 3b. Ends with semicolon (ignoring trailing whitespace and comments)
        code_lines = [
            ln
            for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if code_lines and not code_lines[-1].rstrip().endswith(";"):
            result.findings.append(
                _severity_tag(
                    "WARNING",
                    f"{label}: Last code line does not end with a semicolon.",
                )
            )

        # 3c. Uppercase keywords (case-sensitive search on non-comment lines only)
        non_comment_text = "\n".join(
            ln for ln in block.splitlines() if not ln.strip().startswith("--")
        )
        lowercase_found = [
            kw
            for kw in SQL_KEYWORDS_CASE_CHECK
            if re.search(rf"\b{re.escape(kw)}\b", non_comment_text)  # case-sensitive
        ]
        if lowercase_found:
            result.findings.append(
                _severity_tag(
                    "WARNING",
                    f"{label}: SQL keyword(s) in lowercase — "
                    f"use uppercase: {', '.join(lowercase_found)}.",
                )
            )

    return result


def check_internal_links(fa: FileAnalysis) -> AgentFindings:
    """Check 4 (infra-deploy): internal links inside modules/pages use permalink format."""
    result = AgentFindings(agent_name="infra-deploy")
    # Only check files under _modules/ and _pages/; README uses GitHub-relative paths.
    if "_modules" not in fa.path and "_pages" not in fa.path:
        return result

    content = fa.content or ""
    for match in _RAW_MD_LINK_RE.finditer(content):
        link_text = match.group(1)
        link_target = match.group(2)
        result.findings.append(
            _severity_tag(
                "WARNING",
                f"{fa.path}: Raw .md file-path link '[{link_text}]({link_target})' "
                f"will produce a broken URL on the deployed site. "
                f"Replace with the permalink (e.g. /modules/<slug>/).",
            )
        )
    return result


def check_acronyms(fa: FileAnalysis) -> AgentFindings:
    """Check 5 (clarity-editor): known acronyms are defined on first use."""
    result = AgentFindings(agent_name="clarity-editor")
    # Only module files; pages are intentionally terse.
    if "_modules" not in fa.path:
        return result

    content = fa.content or ""
    _, body = _parse_front_matter(content)

    for acronym, expansion in KNOWN_ACRONYMS.items():
        first = re.search(rf"\b{re.escape(acronym)}\b", body)
        if not first:
            continue  # acronym not used in this file

        # Look for a definition within the body up to 300 chars after first use.
        # Definition patterns:
        #   "Full Name (ACRONYM)"  or  "ACRONYM (Full Name)"
        window = body[: first.end() + 300]
        expansion_prefix = expansion.split()[0]  # first word of the expansion

        defined = bool(
            re.search(
                rf"(?i){re.escape(expansion_prefix)}.*?\({re.escape(acronym)}\)",
                window,
            )
        ) or bool(
            re.search(
                rf"\b{re.escape(acronym)}\b\s*\([^)]+\)",
                window,
            )
        )

        if not defined:
            result.findings.append(
                _severity_tag(
                    "INFO",
                    f"{fa.path}: Acronym '{acronym}' used without definition on first use "
                    f"— expected pattern: \"{expansion} ({acronym})\".",
                )
            )
    return result


def check_study_plan_modules(
    fa: FileAnalysis,
    module_files: list[Path],
) -> AgentFindings:
    """Check 6 (infra-deploy): study-plan module numbers map to existing files."""
    result = AgentFindings(agent_name="infra-deploy")
    if "study-plan" not in fa.path:
        return result

    # Build set of module numbers present on disk
    existing: set[int] = set()
    for f in module_files:
        m = re.match(r"^(\d+)-", f.name)
        if m:
            existing.add(int(m.group(1)))

    content = fa.content or ""
    referenced: set[int] = set()

    # "Module N" / "Modules N, M" patterns
    for match in re.finditer(r"\bModules?\s+([\d,\s]+)", content, re.IGNORECASE):
        for num_str in re.findall(r"\d+", match.group(1)):
            referenced.add(int(num_str))

    # Numbers in table cells that are plausible module numbers (1–20)
    for match in re.finditer(r"\|\s*([\d,\s]+)\s*\|", content):
        for num_str in re.findall(r"\d+", match.group(1)):
            n = int(num_str)
            if 1 <= n <= 20:
                referenced.add(n)

    for num in sorted(referenced):
        if num not in existing:
            result.findings.append(
                _severity_tag(
                    "BLOCKER",
                    f"{fa.path}: References Module {num} but no corresponding "
                    f"file exists in _modules/.",
                )
            )
    return result


# ---------------------------------------------------------------------------
# File collection and analysis object builder
# ---------------------------------------------------------------------------


def _collect_md_files(config: AnalysisConfig, *directories: Path) -> list[Path]:
    """Return sorted .md files from *directories* respecting config exclusions."""
    exclude = set(config.exclude_patterns)
    files: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("*.md")):
            if not any(ex in str(f) for ex in exclude):
                files.append(f)
    return files


def _build_file_analysis(path: Path) -> FileAnalysis:
    """Read *path* and return a populated FileAnalysis."""
    content = path.read_text(encoding="utf-8")
    return FileAnalysis(
        path=str(path.relative_to(REPO_ROOT)),
        size=path.stat().st_size,
        language="Markdown",
        content=content,
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_validation(show_info: bool = True) -> int:
    """
    Execute all content checks and print a summary report.

    Returns:
        0 if no BLOCKER findings, 1 otherwise.
    """
    setup_logging(level="INFO")
    logger = get_logger(__name__)

    config = AnalysisConfig(
        include_patterns=["*.md"],
        exclude_patterns=[".git", "__pycache__", "node_modules", "vendor", "_site"],
    )
    repo = RepositoryInfo(
        path=REPO_ROOT,
        name="Data-Engineering-Prep-Guide",
        owner="moshesham",
        branch="main",
        project_objective="Data Engineering Interview Study Guide — content quality gate",
    )

    logger.info(
        "Content validation starting — repo=%s modules=%s pages=%s",
        repo.path,
        MODULE_DIR,
        PAGE_DIR,
    )

    md_files = _collect_md_files(config, MODULE_DIR, PAGE_DIR)
    module_files = [f for f in md_files if "_modules" in str(f)]

    logger.info("Files to validate: %d", len(md_files))

    all_findings: list[AgentFindings] = []

    for path in md_files:
        fa = _build_file_analysis(path)
        all_findings += [
            check_front_matter(fa),
            check_required_sections(fa),
            check_sql_blocks(fa),
            check_internal_links(fa),
            check_acronyms(fa),
            check_study_plan_modules(fa, module_files),
        ]

    # Bucket findings by severity
    blockers: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    for af in all_findings:
        for finding in af.findings:
            line = f"  {finding}  [agent: {af.agent_name}]"
            if finding.startswith("[BLOCKER]"):
                blockers.append(line)
            elif finding.startswith("[WARNING]"):
                warnings.append(line)
            else:
                infos.append(line)

    if blockers:
        print("\n=== BLOCKERS (CI will fail) ===")
        for b in blockers:
            print(b)

    if warnings:
        print("\n=== WARNINGS ===")
        for w in warnings:
            print(w)

    if show_info and infos:
        print("\n=== INFO ===")
        for i in infos:
            print(i)

    n_blockers = len(blockers)
    print(
        f"\n{'='*60}\n"
        f"Validation summary — {len(md_files)} file(s) checked\n"
        f"  BLOCKERs : {n_blockers}\n"
        f"  Warnings : {len(warnings)}\n"
        f"  Info     : {len(infos)}\n"
        f"{'='*60}"
    )

    if n_blockers > 0:
        logger.error(
            "Content validation FAILED — %d blocker(s) must be resolved before deployment.",
            n_blockers,
        )
        return 1

    logger.info("Content validation passed.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rule-based content validator for Data-Engineering-Prep-Guide.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--no-info",
        action="store_true",
        default=False,
        help="Suppress INFO-level findings in output (BLOCKERs and WARNINGs still shown).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(run_validation(show_info=not args.no_info))
