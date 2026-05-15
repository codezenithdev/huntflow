"""Daily digest compiler — short, actionable intelligence."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import SQLiteTrackerTool, TelegramNotifyTool


def create_digest_agent(**kwargs) -> Agent:
    """60-second-readable daily summary."""
    return Agent(
        role="Daily Intelligence Reporter",
        goal="Compile and send daily digest — readable in 60 seconds",
        backstory="""Top 3 A/B jobs | pipeline stats | follow-up reminders | one tactical insight.
Ends with something specific to the day's data, not generic cheerleading.""",
        tools=[SQLiteTrackerTool(), TelegramNotifyTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_digest_agent", "SEEKER_PROFILE"]
