"""
tools/agents/infra_deploy_agent.py — InfraDeployAgent

Role (from AGENTS.md):
    DevOps / platform engineer specializing in GitHub Actions, Jekyll, and
    GitHub Pages.  Ensures the site builds cleanly and content renders
    correctly on every push to main.

Output format:
    Ordered list of findings tagged [BLOCKER], [WARNING], or [INFO] with the
    exact file and line number.

Note on LLM usage:
    This agent is the first in the pipeline and acts as a build-viability
    gate.  The LLM is asked to reason about Jekyll front-matter constraints,
    permalink consistency, and GitHub Actions workflow correctness — checks
    that go beyond what the static validate_content.py can catch.
"""
from __future__ import annotations

from typing import Any, List

from omniscient_core import FileAnalysis, RepositoryInfo
from omniscient_core.base import AgentResponse, BaseAIAgent


class InfraDeployAgent(BaseAIAgent):
    """LLM-powered reviewer for Jekyll infrastructure and deployment concerns."""

    #: AGENTS.md agent identifier
    AGENT_ID = "infra-deploy"

    def __init__(self, llm: Any) -> None:
        super().__init__(
            llm=llm,
            name="infra-deploy",
            description=(
                "Validates front matter, Jekyll build viability, permalink "
                "consistency, and GitHub Actions workflow correctness."
            ),
            analysis_focus="infrastructure and deployment",
        )

    # ------------------------------------------------------------------
    # Required abstract implementation
    # ------------------------------------------------------------------

    def get_prompt_template(self) -> str:
        return (
            "You are a senior DevOps engineer specialising in Jekyll, GitHub Actions, "
            "and GitHub Pages.\n\n"
            "Repository context:\n{context}\n\n"
            "Analysis objective:\n{objective}\n\n"
            "Files under review:\n{files_info}\n\n"
            "Review checklist (from AGENTS.md):\n"
            "1. Every .md file under _modules/ and _pages/ has valid YAML front matter "
            "   with layout, title, and permalink fields.\n"
            "2. _config.yml collections config matches the directory structure.\n"
            "3. All internal links use the correct permalink format — no raw file-path links.\n"
            "4. The Jekyll workflow uses stable pinned action versions.\n"
            "5. The workflow concurrency block prevents duplicate deployments.\n"
            "6. No Jekyll plugins are used that are not on the GitHub Pages allowlist.\n"
            "7. Mermaid/code fence blocks render correctly.\n"
            "8. baseurl in _config.yml matches the repository name exactly.\n\n"
            "For each finding output a single line starting with one of:\n"
            "  [BLOCKER] — blocks merge\n"
            "  [WARNING] — should be fixed before release\n"
            "  [INFO]    — advisory\n\n"
            "Include the filename and line number where relevant.\n\n"
            "{format_instructions}"
        )

    # ------------------------------------------------------------------
    # Override analyze() to add structured output formatting
    # ------------------------------------------------------------------

    async def analyze(
        self,
        files: List[FileAnalysis],
        repo_info: RepositoryInfo,
    ) -> AgentResponse:
        response = await super().analyze(files, repo_info)
        response.agent_name = self.AGENT_ID
        # Prefix each finding with the agent's comment marker
        response.findings = [
            f"<!-- INFRA-DEPLOY: {f} -->" if not f.startswith("<!--") else f
            for f in response.findings
        ]
        return response
