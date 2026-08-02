"""
tools/agents — LLM-powered content-review agents for Data-Engineering-Prep-Guide.

Each agent subclasses omniscient_core.BaseAIAgent and maps to one of the five
agent roles defined in AGENTS.md:

    infra_deploy_agent    → infra-deploy
    tech_accuracy_agent   → tech-accuracy
    sql_specialist_agent  → sql-specialist
    clarity_editor_agent  → clarity-editor
    behavioral_coach_agent → behavioral-coach

Usage (via run_review.py):

    from tools.agents import ALL_AGENTS, create_agent

    agent = create_agent("tech-accuracy", llm=my_llm)
    response = await agent.analyze(files, repo_info)
"""
from __future__ import annotations

from .infra_deploy_agent import InfraDeployAgent
from .tech_accuracy_agent import TechAccuracyAgent
from .sql_specialist_agent import SqlSpecialistAgent
from .clarity_editor_agent import ClarityEditorAgent
from .behavioral_coach_agent import BehavioralCoachAgent

__all__ = [
    "InfraDeployAgent",
    "TechAccuracyAgent",
    "SqlSpecialistAgent",
    "ClarityEditorAgent",
    "BehavioralCoachAgent",
    "ALL_AGENTS",
    "create_agent",
]

# Ordered as specified by the multi-agent workflow in AGENTS.md
ALL_AGENTS: dict[str, type] = {
    "infra-deploy": InfraDeployAgent,
    "tech-accuracy": TechAccuracyAgent,
    "sql-specialist": SqlSpecialistAgent,
    "clarity-editor": ClarityEditorAgent,
    "behavioral-coach": BehavioralCoachAgent,
}


def create_agent(agent_id: str, llm: object) -> object:
    """Instantiate an agent by its AGENTS.md identifier.

    Args:
        agent_id: One of the keys in ALL_AGENTS.
        llm:      A LangChain-compatible LLM instance (supports ``ainvoke``).

    Returns:
        Configured agent instance ready for ``await agent.analyze(files, repo)``.

    Raises:
        KeyError: If agent_id is not recognised.
    """
    cls = ALL_AGENTS[agent_id]
    return cls(llm=llm)
