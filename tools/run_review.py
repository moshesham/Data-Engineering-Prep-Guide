#!/usr/bin/env python3
"""
tools/run_review.py — Multi-agent content-review CLI for Data-Engineering-Prep-Guide.

Runs the five AGENTS.md reviewer agents (infra-deploy → tech-accuracy →
sql-specialist → clarity-editor → behavioral-coach) in sequence against one
or more module files and prints findings in the agent-specific comment format.

LLM provider selection (highest priority first):
  1. --provider CLI flag
  2. OMNISCIENT_PROVIDER env var  (ollama | openai | anthropic)
  3. Config file value (omniscient_config.yaml)
  4. Auto-detect: tries Ollama first, then raises a clear error

Provider requirements:
  ollama    — Ollama running locally, plus:
              pip install langchain-community langchain-core
  openai    — OPENAI_API_KEY env var, plus:
              pip install langchain-openai langchain-core
  anthropic — ANTHROPIC_API_KEY env var, plus:
              pip install langchain-anthropic langchain-core

Usage examples:
  # Review one module with all agents
  python tools/run_review.py --module _modules/03-sql.md

  # Review multiple modules with specific agents only
  python tools/run_review.py \\
      --module _modules/03-sql.md _modules/06-aiml-infrastructure.md \\
      --agents tech-accuracy,sql-specialist

  # Review all modules, post findings as PR review comments
  python tools/run_review.py --all \\
      --agents infra-deploy,tech-accuracy \\
      --post-pr --pr-number 42

  # Use OpenAI instead of the default Ollama
  python tools/run_review.py --module _modules/03-sql.md --provider openai
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Optional

from omniscient_core import (
    AnalysisConfig,
    FileAnalysis,
    RepositoryInfo,
    get_logger,
    load_config,
    setup_logging,
)
from omniscient_core.base import AgentResponse

# Repository layout
REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "_modules"
PAGE_DIR = REPO_ROOT / "_pages"
CONFIG_PATH = REPO_ROOT / "omniscient_config.yaml"

# Agent execution order as defined by AGENTS.md
AGENT_PIPELINE = [
    "infra-deploy",
    "tech-accuracy",
    "sql-specialist",
    "clarity-editor",
    "behavioral-coach",
]

# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------


def _create_llm(provider: str, config: AnalysisConfig) -> Any:
    """Instantiate a LangChain-compatible LLM for the requested provider.

    Args:
        provider: One of "ollama", "openai", "anthropic".
        config:   Loaded AnalysisConfig (supplies model name and host).

    Returns:
        A LangChain LLM instance that supports ``ainvoke(prompt: str)``.

    Raises:
        ImportError:  Required LangChain package is not installed.
        ValueError:   Provider name is not recognised.
        RuntimeError: LLM initialisation failed (e.g. missing API key).
    """
    if provider == "ollama":
        try:
            from langchain_community.llms import Ollama  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "Ollama provider requires: pip install langchain-community langchain-core"
            ) from exc
        return Ollama(
            model=config.ollama_model,
            base_url=config.ollama_host,
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable must be set for the openai provider."
            )
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "OpenAI provider requires: pip install langchain-openai langchain-core"
            ) from exc
        return ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable must be set for the anthropic provider."
            )
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "Anthropic provider requires: pip install langchain-anthropic langchain-core"
            ) from exc
        return ChatAnthropic(model="claude-3-haiku-20240307", api_key=api_key)

    raise ValueError(
        f"Unknown provider '{provider}'. Choose one of: ollama, openai, anthropic."
    )


def _detect_provider() -> str:
    """Return the provider name from the environment or fall back to 'ollama'."""
    return os.getenv("OMNISCIENT_PROVIDER", "ollama")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _build_file_analysis(path: Path) -> FileAnalysis:
    content = path.read_text(encoding="utf-8")
    return FileAnalysis(
        path=str(path.relative_to(REPO_ROOT)),
        size=path.stat().st_size,
        language="Markdown",
        content=content,
    )


def _resolve_module_paths(
    module_args: list[str],
    all_modules: bool,
) -> list[Path]:
    """Return absolute paths to the requested module files."""
    if all_modules:
        return sorted(MODULE_DIR.glob("*.md")) + sorted(PAGE_DIR.glob("*.md"))

    paths: list[Path] = []
    for arg in module_args:
        p = Path(arg)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            print(f"[ERROR] File not found: {p}", file=sys.stderr)
            sys.exit(1)
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# GitHub PR comment poster (optional, requires GITHUB_TOKEN)
# ---------------------------------------------------------------------------


def _post_pr_comment(
    pr_number: int,
    body: str,
    repo: str = "moshesham/Data-Engineering-Prep-Guide",
) -> None:
    """Post *body* as a PR comment via the GitHub REST API.

    Requires the GITHUB_TOKEN environment variable.
    Falls back to printing a warning if the token is absent or
    the ``requests`` package is not installed.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print(
            "[WARNING] GITHUB_TOKEN not set — skipping PR comment posting.",
            file=sys.stderr,
        )
        return

    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        print(
            "[WARNING] 'requests' package not installed — skipping PR comment posting. "
            "Install it with: pip install requests",
            file=sys.stderr,
        )
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, json={"body": body}, headers=headers, timeout=30)
    if resp.status_code == 201:
        print(f"[INFO] PR comment posted to #{pr_number}.")
    else:
        print(
            f"[WARNING] Failed to post PR comment: {resp.status_code} {resp.text}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------


async def _run_agents(
    agent_ids: list[str],
    files: list[FileAnalysis],
    repo_info: RepositoryInfo,
    llm: Any,
    logger: Any,
) -> dict[str, AgentResponse]:
    """Run agents in pipeline order and return {agent_id: AgentResponse}."""
    # Import here so the script can still run validate_content.py without agents
    from tools.agents import ALL_AGENTS, create_agent  # noqa: PLC0415

    results: dict[str, AgentResponse] = {}
    for agent_id in agent_ids:
        if agent_id not in ALL_AGENTS:
            logger.warning("Unknown agent '%s' — skipping.", agent_id)
            continue

        # sql-specialist only runs when SQL blocks are present
        if agent_id == "sql-specialist":
            has_sql = any(
                "```sql" in (fa.content or "").lower() for fa in files
            )
            if not has_sql:
                logger.info(
                    "sql-specialist skipped — no SQL blocks found in the selected files."
                )
                continue

        # behavioral-coach only runs on module 8 or files with STAR framing
        if agent_id == "behavioral-coach":
            relevant = any(
                "behavioral" in fa.path or "star" in (fa.content or "").lower()
                for fa in files
            )
            if not relevant:
                logger.info(
                    "behavioral-coach skipped — no behavioral/STAR content in selected files."
                )
                continue

        logger.info("Running agent: %s …", agent_id)
        agent = create_agent(agent_id, llm=llm)
        response = await agent.analyze(files, repo_info)
        results[agent_id] = response
        logger.info(
            "Agent %s complete — %d finding(s), confidence=%.2f.",
            agent_id,
            len(response.findings),
            response.confidence,
        )

    return results


def _format_report(results: dict[str, AgentResponse]) -> str:
    """Format agent results into a human-readable Markdown report."""
    lines: list[str] = ["# Content Review Report\n"]
    for agent_id, response in results.items():
        lines.append(f"## Agent: `{agent_id}`\n")
        if response.reasoning:
            lines.append(f"**Reasoning:** {response.reasoning}\n")
        if response.findings:
            lines.append("**Findings:**\n")
            for i, finding in enumerate(response.findings, start=1):
                lines.append(f"{i}. {finding}")
        else:
            lines.append("_No findings._")
        if response.recommendations:
            lines.append("\n**Recommendations:**\n")
            for rec in response.recommendations:
                lines.append(f"- {rec}")
        lines.append("")  # blank line between agents
    return "\n".join(lines)


async def _async_main(args: argparse.Namespace) -> int:
    setup_logging(level="INFO")
    logger = get_logger(__name__)

    # Load config
    config = load_config(config_path=CONFIG_PATH)

    # Resolve provider
    provider = args.provider or _detect_provider()
    logger.info("LLM provider: %s", provider)

    # Build LLM
    try:
        llm = _create_llm(provider, config)
    except (ImportError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    # Resolve files
    module_paths = _resolve_module_paths(
        module_args=args.module or [],
        all_modules=args.all,
    )
    if not module_paths:
        print(
            "[ERROR] No files specified.  Use --module <path> or --all.",
            file=sys.stderr,
        )
        return 1

    files = [_build_file_analysis(p) for p in module_paths]
    logger.info("Files selected for review: %s", [fa.path for fa in files])

    # Resolve agent list
    if args.agents:
        agent_ids = [a.strip() for a in args.agents.split(",")]
    else:
        agent_ids = list(AGENT_PIPELINE)

    repo_info = RepositoryInfo(
        path=REPO_ROOT,
        name="Data-Engineering-Prep-Guide",
        owner="moshesham",
        branch="main",
        project_objective=(
            "Data Engineering Interview Study Guide — reviewed by content agents"
        ),
    )

    results = await _run_agents(agent_ids, files, repo_info, llm, logger)

    report = _format_report(results)
    print(report)

    if args.post_pr:
        if not args.pr_number:
            print(
                "[ERROR] --pr-number is required when --post-pr is set.",
                file=sys.stderr,
            )
            return 1
        _post_pr_comment(pr_number=args.pr_number, body=report)

    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AGENTS.md-defined content reviewers against study-guide modules."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--module",
        nargs="+",
        metavar="PATH",
        help="One or more module file paths to review (relative to repo root).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Review all files in _modules/ and _pages/.",
    )
    parser.add_argument(
        "--agents",
        metavar="AGENT_IDS",
        help=(
            "Comma-separated list of agent IDs to run.  "
            f"Available: {', '.join(AGENT_PIPELINE)}.  "
            "Defaults to all agents in pipeline order."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "anthropic"],
        default=None,
        help="LLM provider to use.  Defaults to OMNISCIENT_PROVIDER env var or 'ollama'.",
    )
    parser.add_argument(
        "--post-pr",
        action="store_true",
        default=False,
        help="Post the review report as a PR comment (requires GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        metavar="N",
        help="Pull-request number for --post-pr.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_async_main(_parse_args())))
