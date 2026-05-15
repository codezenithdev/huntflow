"""US-wide job discovery agent — keyword sweeps across configured boards."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import (
    AshbyBroadScraperTool,
    LinkedInScraperTool,
    RemotiveScraperTool,
    WellfoundScraperTool,
    YCScraperTool,
)


def create_job_discovery_agent(**kwargs) -> Agent:
    """Broad market discovery; scorer and downstream agents refine."""
    return Agent(
        role="US Tech Market Job Scout",
        goal=(
            "Sweep the entire US startup job market daily by keyword — discover every relevant "
            "engineering role regardless of company"
        ),
        backstory="""You search by job title keyword across all US job boards —
never by company name. Shylu is open to any US startup. You search Ashby HQ,
Wellfound, YC, Remotive, and LinkedIn Jobs using keyword queries
like 'founding engineer', 'backend engineer', 'AI engineer'. LinkedIn is your
highest-volume source but treated conservatively — RSS mode by default to stay
within TOS. You filter out sales/design/management roles but never filter by
company. Your job is broad discovery — let the scorer decide.
Target 80-250 jobs per daily run.""",
        tools=[
            AshbyBroadScraperTool(),
            WellfoundScraperTool(),
            YCScraperTool(),
            RemotiveScraperTool(),
            LinkedInScraperTool(),
        ],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_job_discovery_agent", "SEEKER_PROFILE"]
