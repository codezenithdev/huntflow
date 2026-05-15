"""ATS scoring and keyword-gap agent."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.keyword_extractor import ATSKeywordTool, ATSScorer, job_score

__all__ = [
    "ATSKeywordTool",
    "ATSScorer",
    "job_score",
    "create_ats_keyword_agent",
    "SEEKER_PROFILE",
]


def create_ats_keyword_agent(**kwargs) -> Agent:
    """Precise ATS scores and explicit missing keywords."""
    return Agent(
        role="ATS Reverse Engineer",
        goal="Compute precise ATS scores and identify keyword gaps",
        backstory="""You reverse-engineer ATS algorithms. You extract keywords weighted by
JD frequency, compute semantic similarity, and flag tech terms appearing 3+ times
as must-haves. You never return a score without the specific missing keywords.""",
        tools=[ATSKeywordTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )
