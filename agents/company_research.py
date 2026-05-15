"""Startup diligence — funding, team, tech, visa signals."""

from __future__ import annotations

from crewai import Agent
from crewai_tools import TavilySearchTool

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool, SQLiteTrackerTool


def create_company_research_agent(**kwargs) -> Agent:
    """Company dossiers with red/green flags."""
    return Agent(
        role="Startup Due Diligence Analyst",
        goal="Build a company dossier with funding, team, tech, and red/green flags",
        backstory="""You synthesize: funding stage and recency (no funding in 18+ months = red flag),
GitHub org activity (no recent commits = red flag), Glassdoor (< 3.5 = red flag),
team size (5-50 is ideal for Shylu). You explicitly look for visa sponsorship evidence —
critical for STEM OPT context.""",
        tools=[TavilySearchTool(), ChromaMemoryTool(), SQLiteTrackerTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_company_research_agent", "SEEKER_PROFILE"]
