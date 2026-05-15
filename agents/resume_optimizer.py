"""Resume variant selection and ATS gap surfacing."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool
from tools.keyword_extractor import ATSKeywordTool


def create_resume_optimizer_agent(**kwargs) -> Agent:
    """ATS-aware resume variant advisor for Shylu."""
    return Agent(
        role="ATS Optimization Specialist",
        goal="Select the best resume variant for each job and surface keyword gaps",
        backstory="""6 years as a FAANG recruiter, now independent. You know how ATS parses resumes.
For Shylu, you choose between: AI resume (Java/Spring/LangChain/RAG-heavy) and FS resume
(full-stack/React/Next.js inclusive). You pick based on what the JD rewards most.
You surface the top 5 missing keywords Shylu could add without fabricating experience.""",
        tools=[ATSKeywordTool(), ChromaMemoryTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_resume_optimizer_agent", "SEEKER_PROFILE"]
