"""Role- and company-specific interview prep."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool, SQLiteTrackerTool


def create_interview_prep_agent(**kwargs) -> Agent:
    """Markdown prep artifacts under data/prep/."""
    return Agent(
        role="Technical Interview Coach",
        goal="Generate hyper-specific interview prep — not generic, calibrated to company + role",
        backstory="""You interviewed 500+ engineers. For Shylu, you know strengths:
Java internals, Spring Boot, LangChain4j/Spring AI, AWS, Docker/K8s.
Prep areas: system design depth, distributed systems breadth.
5 STAR behavioral answers using Shylu's real projects. Output markdown to data/prep/.""",
        tools=[ChromaMemoryTool(), SQLiteTrackerTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_interview_prep_agent", "SEEKER_PROFILE"]
