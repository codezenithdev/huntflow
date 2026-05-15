"""Interview prep crew — behavioral, technical, system design."""

from __future__ import annotations

from datetime import datetime

from crewai import Agent, Crew, Process, Task

from agents.interview_prep import create_interview_prep_agent
from config.seeker_profile import SEEKER_PROFILE


def create_interview_prep_crew(company_name: str, job_title: str) -> Crew:
    """
    Generate comprehensive interview prep for a specific company + role:
    1. Fetch company context (stage, culture, recent moves, tech stack)
    2. Behavioral prep (STAR stories matched to their hiring themes)
    3. Technical prep (problem domains likely in their interviews)
    4. System design prep (scope based on role level + company scale)
    5. Compile into markdown artifact
    6. Save to data/prep/{company}_{date}.md

    Args:
        company_name: e.g., "Stripe" or "Early-stage startup XYZ"
        job_title: e.g., "Backend Engineer" or "Founding Engineer"
    """
    # Agent
    coach_agent = create_interview_prep_agent(verbose=False)

    # Tasks
    fetch_context_task = Task(
        description=f"""Gather context for {company_name} + {job_title}:
        1. Company stage (seed/Series A/B/C/public), funding, growth rate
        2. Tech stack (infer from job posting + public signals)
        3. Hiring themes (from job description + recent hires on LinkedIn)
        4. Shylu's fit (which of Shylu's projects/skills directly apply)
        Return: 2-3 paragraph context blob.""",
        agent=coach_agent,
        expected_output=(
            "Company context: stage, tech_stack, hiring_themes, shylu_fit_match"
        ),
    )

    behavioral_task = Task(
        description=f"""Generate 5 STAR stories for {company_name} interview:
        Stories must come from Shylu's real projects (Java/Spring/LangChain/AWS/Docker/Kubernetes).
        Themes: (1) shipping under pressure, (2) debugging complex systems,
        (3) technical leadership, (4) learning quickly, (5) cross-team collaboration.
        Each story: Situation (1 sentence) | Task (1 sentence) | Action (2-3 sentences) |
        Result (quantified, e.g., "50% faster", "5M users").
        No fabrication. No generic examples.""",
        agent=coach_agent,
        expected_output=(
            "5 STAR stories, each with Situation | Task | Action | Result. "
            "One per theme. Real projects only."
        ),
        context=[fetch_context_task],
    )

    technical_task = Task(
        description=f"""Technical interview prep for {company_name} ({job_title}):
        1. Identify 3-5 likely problem domains (from company tech stack + role)
        2. For each domain: 2-3 representative LC-style problems + solutions
        3. Data structure focus: what matters (e.g., hash maps for rate limiting, heaps for priority queues)
        4. Complexity analysis: know big O for all solutions
        5. Edge cases: off-by-one, null checks, concurrency gotchas
        Format: Problem name | Approach | Complexity | Code sketch + explanation.""",
        agent=coach_agent,
        expected_output=(
            "List of 3-5 problem domains with 2-3 representative problems each. "
            "Format: domain | problem_name | approach | O(n) complexity | code_sketch"
        ),
        context=[fetch_context_task],
    )

    system_design_task = Task(
        description=f"""System design prep for {company_name} ({job_title}):
        Scope based on: company stage (startup vs. scale-up) + role level.
        Assume you're designing for their actual product scope.
        Outline:
        1. Clarifying questions (latency, throughput, consistency, scale)
        2. High-level architecture (services, databases, caches)
        3. Data model (tables/schemas if applicable)
        4. Scaling bottlenecks (CPU, memory, network, storage)
        5. Failure modes + resilience (retries, circuit breakers, rate limits)
        6. Estimate server/storage needs
        Keep to 1 page. Focus on reasoning, not perfection.""",
        agent=coach_agent,
        expected_output=(
            "System design outline: 1-page architecture with clarifying questions, "
            "high-level design, data model, scaling plan, failure modes, estimates"
        ),
        context=[fetch_context_task],
    )

    compile_task = Task(
        description=f"""Compile interview prep markdown for {company_name}:
        Output file: data/prep/{company_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md
        Structure:
        ```
        # Interview Prep: {company_name} — {job_title}

        ## Company Context
        [from fetch_context_task]

        ## Behavioral (STAR Stories)
        [5 stories from behavioral_task]

        ## Technical Interview
        ### Problem Domain 1
        - Problem 1: [name] | Approach: [desc] | O(?) | [code]
        - Problem 2: ...
        ### Problem Domain 2
        [similar]

        ## System Design
        [1-page outline from system_design_task]

        ## Closing Notes
        - Key talking points: [list 3-5 unique things Shylu brings]
        - Weakness prep: [preempt objections, e.g., "my full-stack breadth vs. deep backend"]
        - Questions to ask: [2-3 thoughtful questions about role/team/tech]

        ---
        Generated: {datetime.now().isoformat()}
        ```
        Return: confirmation that file was saved + file path.""",
        agent=coach_agent,
        expected_output=(
            f"Markdown file saved to data/prep/{company_name.replace(' ', '_')}_YYYYMMDD.md. "
            "File ready for review."
        ),
        context=[behavioral_task, technical_task, system_design_task],
    )

    notify_task = Task(
        description=f"""Notify Shylu that interview prep for {company_name} is ready:
        Send Telegram message: "{company_name} interview prep ready. Review at data/prep/[filename]"
        Also save a desktop reminder file for tomorrow morning.""",
        agent=coach_agent,
        expected_output=(
            "Telegram notification sent + reminder file created. "
            "Prep is live and visible."
        ),
        context=[compile_task],
    )

    # Crew
    crew = Crew(
        agents=[coach_agent],
        tasks=[
            fetch_context_task,
            behavioral_task,
            technical_task,
            system_design_task,
            compile_task,
            notify_task,
        ],
        process=Process.sequential,
        memory=True,
        verbose=True,
    )

    return crew


if __name__ == "__main__":
    # Example usage
    company = "Stripe"
    role = "Backend Engineer, Payments"
    crew = create_interview_prep_crew(company, role)
    crew.kickoff()
