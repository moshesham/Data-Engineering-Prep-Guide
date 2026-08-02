"""
tools/agents/clarity_editor_agent.py — ClarityEditorAgent

Role (from AGENTS.md):
    Senior technical writer with data engineering background.  Ensures every
    explanation is accessible to a candidate with 3–5 years of experience but
    possibly unfamiliar with Meta-specific framing.

Skill profile:
    Writes at graduate-level technical register: precise but not
    jargon-heavy.  Structures explanations as:
        concept → why it matters in an interview → concrete example
        → common mistake to avoid

Output format:
    Rewrite unclear passages in git-diff style code blocks with a one-sentence
    rationale for each change.  Flag (but do not rewrite) passages where
    technical accuracy is uncertain — hand those to tech-accuracy.
"""
from __future__ import annotations

from typing import Any, List

from omniscient_core import FileAnalysis, RepositoryInfo
from omniscient_core.base import AgentResponse, BaseAIAgent


class ClarityEditorAgent(BaseAIAgent):
    """LLM-powered prose-clarity and pedagogical-structure reviewer."""

    AGENT_ID = "clarity-editor"

    def __init__(self, llm: Any) -> None:
        super().__init__(
            llm=llm,
            name="clarity-editor",
            description=(
                "Reviews prose clarity, pedagogical structure, acronym definitions, "
                "and section transitions across all modules and reference pages."
            ),
            analysis_focus="prose clarity and pedagogical structure",
        )

    def get_prompt_template(self) -> str:
        return (
            "You are a senior technical writer with a data engineering background.\n\n"
            "Repository context:\n{context}\n\n"
            "Analysis objective:\n{objective}\n\n"
            "Files under review:\n{files_info}\n\n"
            "Review checklist (from AGENTS.md):\n"
            "1. Every concept introduced is defined before it is used.\n"
            "2. Each module opens with a 'Core job:' statement (one sentence on what "
            "   the interviewer is grading).\n"
            "3. Examples use the same running schema throughout a module.\n"
            "4. Transitions between sub-sections are explicit — the reader is told "
            "   what they just learned and what comes next.\n"
            "5. Acronyms (DAU, CTR, SCD, RCA, ETL, DAG) are spelled out on first "
            "   use within each module.\n"
            "6. The 4-week study plan maps to module numbers that actually exist.\n"
            "7. The recall sheet is scannable in under two minutes.\n\n"
            "Output format:\n"
            "- Rewrite unclear passages in git-diff style:\n"
            "    - original line\n"
            "    + improved line\n"
            "  followed by a one-sentence rationale.\n"
            "- For passages where technical accuracy is uncertain, write:\n"
            "  <!-- CLARITY-EDITOR: [needs tech-accuracy review] <description> -->\n"
            "  Do NOT rewrite those passages.\n\n"
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
            f"<!-- CLARITY-EDITOR: {f} -->" if not f.startswith("<!--") else f
            for f in response.findings
        ]
        return response
