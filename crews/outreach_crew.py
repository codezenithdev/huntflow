"""Outreach crew — research, draft, save (never auto-send)."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from agents.company_research import create_company_research_agent
from agents.outreach_drafter import create_outreach_drafter_agent
from agents.resume_optimizer import create_resume_optimizer_agent
from config.seeker_profile import SEEKER_PROFILE


def create_outreach_crew() -> Crew:
    """
    Draft founder-grade cold outreach for top jobs:
    1. Fetch top pipeline targets (A+/A jobs, no outreach yet)
    2. Research founder/hiring hook (recent launch, GitHub, blog, tweet)
    3. Tailor resume for this specific role
    4. Draft 5-sentence cold email (company hook + credential + ask)
    5. Save drafts to data/outreach/ (NEVER auto-send)
    """
    # Agents
    research_agent = create_company_research_agent(verbose=False)
    resume_agent = create_resume_optimizer_agent(verbose=False)
    drafter_agent = create_outreach_drafter_agent(verbose=False)

    # Tasks
    fetch_targets_task = Task(
        description="""Fetch the top 5 undrafted job targets from the pipeline:
        Criteria: ATS score >= 85, grade A+ or A, no prior outreach attempt.
        For each, return: job_title | company | hiring_manager_guess | url
        Sort by ATS score descending.""",
        agent=research_agent,
        expected_output=(
            "List of 5 undrafted targets with title, company, "
            "suspected hiring_manager, url, ats_score"
        ),
    )

    research_hook_task = Task(
        description="""For each target, find ONE specific, factual outreach hook:
        Examples: (1) "Your Series A announcement last month",
        (2) "Your GitHub org shipped [feature] 2 weeks ago",
        (3) "Your founder tweeted [relevant insight] last week",
        (4) "Your job posting mentions [niche tech] I specialized in".
        NO generic compliments. NO LinkedIn creeping assumptions.
        Return one hook per job with source/date if possible.""",
        agent=research_agent,
        expected_output=(
            "Hook list: one specific, dated, factual hook per target job. "
            "Format: 'Company X: [hook]. Source: [press/GitHub/tweet date]'"
        ),
        context=[fetch_targets_task],
    )

    resume_tailoring_task = Task(
        description="""For each target's JD, select the best resume variant:
        AI resume: emphasize Java, Spring Boot, LangChain, RAG, system design
        FS resume: emphasize React, Next.js, TypeScript, full-stack depth
        Decision rule: JD keyword frequency + semantic alignment.
        Return recommended variant + top 5 missing keywords for each job.""",
        agent=resume_agent,
        expected_output=(
            "Resume variant recommendation per job: "
            "'Company X: recommend [AI/FS] resume. "
            "Missing keywords: [keyword1, keyword2, ...]'"
        ),
        context=[research_hook_task],
    )

    draft_outreach_task = Task(
        description="""Draft 5-sentence cold emails for each target:
        1. Subject line (max 6 words, company-specific hook)
        2. Sentence 1: Company hook (from research_hook_task)
        3. Sentence 2: Shylu credential with number (e.g., "shipped 3 production systems")
        4. Sentence 3: Connection to their problem (e.g., "You need X, my background in Y helps")
        5. Sentence 4: The ask (15 minutes, coffee, no pressure)
        6. Sentence 5: Signature (name + role + phone)
        Tone: professional, conversational, no buzzwords. Drafts only.""",
        agent=drafter_agent,
        expected_output=(
            "Draft emails (one per target): "
            "Subject: ... | Body: ... | Sent to: [company_name]. "
            "Status: DRAFT (requires human review before sending)"
        ),
        context=[resume_tailoring_task],
    )

    save_drafts_task = Task(
        description="""Save all drafted emails to disk:
        Path: data/outreach/{company_name}_{ats_score}_{timestamp}.md
        Format:
        ```
        # {company} Cold Outreach Draft
        - Job Title: {job_title}
        - URL: {job_url}
        - ATS Score: {score}
        - Hook: {hook}
        - Resume Variant: {variant}

        **Subject:** {subject}

        {body}

        ---
        Status: DRAFT (Human review required before sending)
        Created: {timestamp}
        ```
        Return: saved file count + file paths.""",
        agent=drafter_agent,
        expected_output=(
            "Confirmation: X drafts saved to data/outreach/. "
            "File list: [file1, file2, ...]. "
            "Status: All ready for human review."
        ),
        context=[draft_outreach_task],
    )

    # Crew
    crew = Crew(
        agents=[research_agent, resume_agent, drafter_agent],
        tasks=[
            fetch_targets_task,
            research_hook_task,
            resume_tailoring_task,
            draft_outreach_task,
            save_drafts_task,
        ],
        process=Process.sequential,
        memory=True,
        verbose=True,
    )

    return crew


if __name__ == "__main__":
    crew = create_outreach_crew()
    crew.kickoff()
