"""Founder-grade cold outreach drafts (never auto-send)."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool


def create_outreach_drafter_agent(**kwargs) -> Agent:
    """Five-sentence drafts saved under data/outreach/."""
    return Agent(
        role="Cold Outreach Specialist",
        goal="Draft 5-sentence founder-grade cold emails for top jobs — drafts only, never auto-send",
        backstory="""Your cold emails get replies. Formula: one company-specific hook
(recent launch/GitHub/tweet), one Shylu credential with a number, one connection
to their specific problem, one ask (15 minutes). Always check for duplicate outreach.
Always save as draft. Never auto-send. Every draft gets saved to data/outreach/.""",
        tools=[ChromaMemoryTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_outreach_drafter_agent", "SEEKER_PROFILE"]
