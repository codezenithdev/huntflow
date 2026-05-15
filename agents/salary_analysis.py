"""Compensation benchmarking with stage and visa context."""

from __future__ import annotations

from crewai import Agent
from crewai_tools import TavilySearchTool

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context


def create_salary_analysis_agent(**kwargs) -> Agent:
    """Salary bands with cited sources."""
    return Agent(
        role="Compensation Intelligence Analyst",
        goal="Estimate realistic salary range with OPT/H1B context",
        backstory="""You cross-reference DOL H1B LCA public data, Levels.fyi patterns,
and company stage norms. Seed: $130-160K + 0.5-1.5% equity. Series A: $150-185K + 0.1-0.5%.
You flag prevailing wage data relevant to Shylu's eventual H1B transition.
Always cite sources.""",
        tools=[TavilySearchTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_salary_analysis_agent", "SEEKER_PROFILE"]
