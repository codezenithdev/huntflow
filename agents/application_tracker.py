"""Application pipeline hygiene and stale-app flags."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import SQLiteTrackerTool, TelegramNotifyTool


def create_application_tracker_agent(**kwargs) -> Agent:
    """Pipeline state and follow-up nudges."""
    return Agent(
        role="Pipeline State Manager",
        goal="Maintain pipeline state, flag stale applications, trigger follow-up nudges",
        backstory="""Obsessive pipeline hygiene. Any 'applied' or 'outreach_sent' app
with no activity in 5 days gets flagged. Weekly stats: reply rate, avg ATS score,
best source.""",
        tools=[SQLiteTrackerTool(), TelegramNotifyTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_application_tracker_agent", "SEEKER_PROFILE"]
