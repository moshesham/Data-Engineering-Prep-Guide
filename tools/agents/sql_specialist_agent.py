"""
tools/agents/sql_specialist_agent.py — SqlSpecialistAgent

Role (from AGENTS.md):
    SQL query engineer who has conducted 200+ data engineering interviews.
    Focuses exclusively on the SQL module and any SQL embedded in other
    modules.

Skill profile:
    Expert in window functions, CTEs, query optimisation, explain plans, and
    partition pruning.  Knows common SQL interview failure modes: fan-out,
    NULL drops, wrong aggregation level, missing DISTINCT.

Scope:
    _modules/03-sql.md (primary); SQL code blocks in any other module.

Output format:
    Annotated SQL blocks with inline -- [SQL-SPECIALIST]: comments, plus a
    "Missing Problems" section listing gaps in coverage by difficulty tier.
"""
from __future__ import annotations

from typing import Any, List

from omniscient_core import FileAnalysis, RepositoryInfo
from omniscient_core.base import AgentResponse, BaseAIAgent


class SqlSpecialistAgent(BaseAIAgent):
    """LLM-powered reviewer focused exclusively on SQL correctness and coverage."""

    AGENT_ID = "sql-specialist"

    def __init__(self, llm: Any) -> None:
        super().__init__(
            llm=llm,
            name="sql-specialist",
            description=(
                "Validates SQL query correctness, interview coverage, difficulty "
                "labelling, and common-mistake annotations in the SQL module and "
                "all other modules containing SQL blocks."
            ),
            analysis_focus="SQL query correctness and interview coverage",
        )

    def get_prompt_template(self) -> str:
        return (
            "You are a SQL expert who has conducted 200+ data engineering interviews.\n\n"
            "Repository context:\n{context}\n\n"
            "Analysis objective:\n{objective}\n\n"
            "Files under review:\n{files_info}\n\n"
            "Review checklist (from AGENTS.md):\n"
            "1. Every SQL query runs correctly against its stated schema.\n"
            "2. Each query includes a comment block explaining: (a) the business "
            "   question, (b) key clauses and why they appear, (c) the most common "
            "   mistake candidates make on this problem.\n"
            "3. At least one 'trap' variant of each problem exists — a subtly wrong "
            "   query with an explanation of why it fails.\n"
            "4. Difficulty is labelled: [Screening], [Onsite-Medium], [Onsite-Hard].\n"
            "5. Rolling window queries specify their frame clause explicitly.\n"
            "6. All JOIN examples state the expected cardinality before and after.\n\n"
            "Output format:\n"
            "- Annotate SQL blocks with inline  -- [SQL-SPECIALIST]: <finding>  comments.\n"
            "- End with a 'Missing Problems' section listing gaps by difficulty tier "
            "  ([Screening], [Onsite-Medium], [Onsite-Hard]).\n\n"
            "{format_instructions}"
        )

    async def analyze(
        self,
        files: List[FileAnalysis],
        repo_info: RepositoryInfo,
    ) -> AgentResponse:
        response = await super().analyze(files, repo_info)
        response.agent_name = self.AGENT_ID
        response.findings = [
            f"-- [SQL-SPECIALIST]: {f}" if not f.startswith("--") else f
            for f in response.findings
        ]
        return response
