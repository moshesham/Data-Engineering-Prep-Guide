"""
tools/agents/behavioral_coach_agent.py — BehavioralCoachAgent

Role (from AGENTS.md):
    Experienced engineering manager and interview coach.  Reviews the
    behavioral module and cross-checks that technical modules include
    interviewer-facing framing guidance.

Skill profile:
    Deep familiarity with STAR (Situation, Task, Action, Result) and SOAR
    (Situation, Obstacle, Action, Result) frameworks.  Understands how Meta
    evaluates ownership, impact, and cross-functional collaboration.

Scope:
    _modules/08-behavioral-ownership.md (primary); framing guidance in all
    other modules.

Output format:
    Annotated suggestions in <!-- BEHAVIORAL-COACH: --> comments, plus a
    rewritten "Saying it out loud" block for any module missing one.
"""
from __future__ import annotations

from typing import Any, List

from omniscient_core import FileAnalysis, RepositoryInfo
from omniscient_core.base import AgentResponse, BaseAIAgent


class BehavioralCoachAgent(BaseAIAgent):
    """LLM-powered reviewer for STAR framing and verbal communication guidance."""

    AGENT_ID = "behavioral-coach"

    def __init__(self, llm: Any) -> None:
        super().__init__(
            llm=llm,
            name="behavioral-coach",
            description=(
                "Reviews STAR story templates, ownership framing, and 'Saying it "
                "out loud' verbal guidance across all modules."
            ),
            analysis_focus="behavioral framing and verbal communication",
        )

    def get_prompt_template(self) -> str:
        return (
            "You are an experienced engineering manager and interview coach familiar "
            "with how Meta evaluates ownership, impact, and cross-functional "
            "collaboration using STAR/SOAR frameworks.\n\n"
            "Repository context:\n{context}\n\n"
            "Analysis objective:\n{objective}\n\n"
            "Files under review:\n{files_info}\n\n"
            "Review checklist (from AGENTS.md):\n"
            "1. Each STAR story template includes a 'what the interviewer is grading' "
            "   callout before the story structure.\n"
            "2. At least five distinct story archetypes are covered:\n"
            "   (1) owned a system end-to-end\n"
            "   (2) fixed a production incident\n"
            "   (3) influenced without authority\n"
            "   (4) simplified a complex system\n"
            "   (5) grew a teammate\n"
            "3. Technical modules each end with a 'Saying it out loud' paragraph — "
            "   a two-sentence template the candidate can use to verbally narrate the "
            "   concept.\n"
            "4. No module assumes the candidate will write code silently; every "
            "   exercise has a verbal component.\n\n"
            "Output format:\n"
            "- Use <!-- BEHAVIORAL-COACH: <finding> --> inline comments.\n"
            "- For any module missing a 'Saying it out loud' block, provide a "
            "  rewritten two-sentence block using this template:\n"
            "    **Saying it out loud:** <sentence 1 — what the concept is>.\n"
            "    <sentence 2 — why it matters in the interview context>.\n\n"
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
            f"<!-- BEHAVIORAL-COACH: {f} -->" if not f.startswith("<!--") else f
            for f in response.findings
        ]
        return response
