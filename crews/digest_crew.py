"""Lightweight digest crew — single task, read DB, format, send Telegram."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from agents.digest import create_digest_agent
from config.seeker_profile import SEEKER_PROFILE


def create_digest_crew() -> Crew:
    """
    Lightweight standalone crew for end-of-day digest:
    Single task: read database stats → format readable summary → send Telegram.
    Runs independently or as the final step of daily_discovery_crew.
    """
    # Agent
    digest_agent = create_digest_agent(verbose=False)

    # Single task
    digest_task = Task(
        description="""Compile a 60-second daily digest and send via Telegram:
        1. Query database: today's new jobs (count by source), top 3 by score
        2. Pipeline snapshot: discovered | applied | interviewing | offer (counts)
        3. Follow-up reminders: overdue (applied 5+ days) + upcoming (in 2-3 days)
        4. One insight: e.g., "Remotive had 8 visa-sponsored roles today",
           "Avg ATS score up 5% week-over-week", "Reply rate from Ashby is 18%"
        5. Format: Telegram message (markdown-lite), max 4-5 short paragraphs
        6. Send to Shylu's Telegram channel
        Tone: quick, actionable, no fluff.""",
        agent=digest_agent,
        expected_output=(
            "Telegram message sent with: top 3 jobs, pipeline stats, "
            "follow-up list, one tactical insight"
        ),
    )

    # Crew
    crew = Crew(
        agents=[digest_agent],
        tasks=[digest_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )

    return crew


if __name__ == "__main__":
    crew = create_digest_crew()
    crew.kickoff()
