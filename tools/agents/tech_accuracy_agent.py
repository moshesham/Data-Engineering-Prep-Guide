"""
tools/agents/tech_accuracy_agent.py — TechAccuracyAgent

Role (from AGENTS.md):
    Senior data engineer (10+ years).  Reviews every module for factual
    correctness, up-to-date terminology, and alignment with real-world
    production systems.

Skill profile:
    Deep expertise in SQL (Presto/Trino, Spark SQL, Snowflake dialects),
    Python (PySpark, pandas), and distributed systems (Kafka, Airflow,
    Databricks, Iceberg).  Familiar with Meta's data stack vocabulary.

Output format:
    Inline comments using <!-- TECH-ACCURACY: <finding> --> markers,
    followed by a summary section listing all findings as a numbered list.
"""
from __future__ import annotations

from typing import Any, List

from omniscient_core import FileAnalysis, RepositoryInfo
from omniscient_core.base import AgentResponse, BaseAIAgent


class TechAccuracyAgent(BaseAIAgent):
    """LLM-powered reviewer for technical correctness across all modules."""

    AGENT_ID = "tech-accuracy"

    def __init__(self, llm: Any) -> None:
        super().__init__(
            llm=llm,
            name="tech-accuracy",
            description=(
                "Reviews technical correctness of SQL, Python, schema designs, "
                "and distributed-systems concepts across all study modules."
            ),
            analysis_focus="technical accuracy and correctness",
        )

    def get_prompt_template(self) -> str:
        return (
            "You are a senior data engineer with 10+ years of experience in "
            "SQL (Presto/Trino, Spark SQL, Snowflake), Python (PySpark, pandas), "
            "and distributed systems (Kafka, Airflow, Databricks, Iceberg, Hive).\n\n"
            "Repository context:\n{context}\n\n"
            "Analysis objective:\n{objective}\n\n"
            "Files under review:\n{files_info}\n\n"
            "Review checklist (from AGENTS.md):\n"
            "1. All SQL syntax is valid and dialect-appropriate.  Note which dialect "
            "   each query targets.\n"
            "2. Window function frames, join semantics, and NULL-handling descriptions "
            "   are accurate.\n"
            "3. Star schema, SCD, and fact/dimension definitions match standard Kimball "
            "   conventions.\n"
            "4. Iceberg, Snowflake, Airflow, Kafka, and PySpark examples reflect "
            "   current API versions (as of 2025).\n"
            "5. No outdated patterns (e.g. deprecated Spark RDD APIs presented as "
            "   preferred; old-style Python 2 syntax).\n"
            "6. The AI/ML module accurately describes feature stores, training/serving "
            "   skew, and model monitoring.\n\n"
            "For each finding, output a comment in the form:\n"
            "  <!-- TECH-ACCURACY: [file:line] <finding> -->\n\n"
            "At the end, output a numbered summary list of all findings.\n"
            "Mark advisory-only findings as (advisory).\n\n"
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
            f"<!-- TECH-ACCURACY: {f} -->" if not f.startswith("<!--") else f
            for f in response.findings
        ]
        return response
