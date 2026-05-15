"""Daily job discovery crew — broad sweep, scoring, research, pipeline update."""

from __future__ import annotations

import yaml
from crewai import Agent, Crew, Process, Task

from agents import get_llm
from agents.application_tracker import create_application_tracker_agent
from agents.company_research import create_company_research_agent
from agents.digest import create_digest_agent
from agents.job_discovery import create_job_discovery_agent
from agents.ats_keyword import create_ats_keyword_agent
from config.seeker_profile import SEEKER_PROFILE


# Load search config at module level
with open("config/search_config.yaml", "r") as f:
    SEARCH_CONFIG = yaml.safe_load(f)


def create_daily_discovery_crew() -> Crew:
    """
    Orchestrate daily job discovery workflow:
    1. Broad discovery across all sources (80-250 jobs)
    2. ATS scoring + keyword matching
    3. Company research (funding, team, signals)
    4. Pipeline state update (stale apps, stats)
    5. Generate digest (top 3, pipeline health, insights)
    """
    # Agents
    discovery_agent = create_job_discovery_agent(verbose=False)
    ats_agent = create_ats_keyword_agent(verbose=False)
    research_agent = create_company_research_agent(verbose=False)
    tracker_agent = create_application_tracker_agent(verbose=False)
    digest_agent = create_digest_agent(verbose=False)

    # Tasks
    broad_discovery_task = Task(
        description="""Search keyword-wide across ALL US job sources:
        Ashby HQ, Wellfound, YC, Remotive, LinkedIn.
        Queries: {search_queries}
        Filters: US location, engineering roles only (no sales/design/management).
        Dedup by URL. Target 80-250 unique jobs per run.
        Return structured list: title | company | source | url | JD snippet.""".format(
            search_queries=SEARCH_CONFIG["search_queries"]["primary"]
        ),
        agent=discovery_agent,
        expected_output=(
            "List of 80-250 unique job listings with title, company, "
            "source (ashby/wellfound/yc/remotive/linkedin), url, jd_snippet"
        ),
    )

    ats_and_score_task = Task(
        description="""For each discovered job, compute:
        1. ATS score (0-100) against Shylu's resume
        2. Missing keywords (top 5 critical terms not in resume)
        3. Job fit grade (A+, A, B+, B, C+, C)
        Grade = combine ATS score, keyword gaps, visa signals.
        Save scores to database for ranking.""",
        agent=ats_agent,
        expected_output=(
            "Job list with ATS scores (0-100), missing_keywords, grade, fit_explanation"
        ),
        context=[broad_discovery_task],
    )

    company_research_task = Task(
        description="""For top 20 jobs (by ATS score):
        1. Company dossier: funding stage, last funding date, team size
        2. Tech stack signals from GitHub/public repos
        3. Visa sponsorship signals (LinkedIn job descriptions, Glassdoor)
        4. Red flags: stale funding (18+ months), low Glassdoor, no activity
        5. Green flags: recent seed/Series A, strong GitHub activity, visa proof
        Save profiles to database for pipeline.""",
        agent=research_agent,
        expected_output=(
            "Company profiles with funding, team_size, tech_stack, "
            "visa_sponsorship_evidence, red_flags, green_flags"
        ),
        context=[ats_and_score_task],
    )

    pipeline_update_task = Task(
        description="""Update application pipeline:
        1. Upsert top 20 jobs (by score) into pipeline as 'discovered' status
        2. Flag stale applications (applied/outreach 5+ days, no response)
        3. Compute daily stats: new jobs by source, avg ATS, reply rate
        4. Update follow-up reminders for warm opportunities
        Return: X new jobs added, Y stale apps flagged, daily stats.""",
        agent=tracker_agent,
        expected_output=(
            "Pipeline update summary: new_jobs_added, stale_apps_flagged, "
            "daily_stats (by_source, avg_ats, reply_rate)"
        ),
        context=[company_research_task],
    )

    daily_digest_task = Task(
        description="""Compile 60-second-readable daily digest:
        1. Top 3 A/B jobs (by score + company quality)
        2. Pipeline snapshot: applied/interviewing/offer counts
        3. Follow-up reminders (overdue + upcoming)
        4. One tactical insight (e.g., 'Remotive has 5x visa-sponsored roles today')
        5. Send via Telegram to Shylu
        Keep to one paragraph + bullet list.""",
        agent=digest_agent,
        expected_output=("Telegram message: top 3 jobs, pipeline stats, insight, follow-ups"),
        context=[pipeline_update_task],
    )

    # Crew
    crew = Crew(
        agents=[discovery_agent, ats_agent, research_agent, tracker_agent, digest_agent],
        tasks=[
            broad_discovery_task,
            ats_and_score_task,
            company_research_task,
            pipeline_update_task,
            daily_digest_task,
        ],
        process=Process.sequential,
        memory=True,
        embedder={"provider": "huggingface", "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}},
        verbose=True,
    )

    return crew


if __name__ == "__main__":
    crew = create_daily_discovery_crew()
    crew.kickoff()
