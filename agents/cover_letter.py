"""Technical cover letter writer — metrics-led, no clichés."""

from __future__ import annotations

from crewai import Agent

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool


def create_cover_letter_agent(**kwargs) -> Agent:
    """Three-paragraph, JD-calibrated cover letters."""
    return Agent(
        role="Technical Cover Letter Writer",
        goal="Write a 3-paragraph, specific, human-sounding cover letter per top job",
        backstory="""No fluff. No 'I am passionate about'. Every paragraph anchors to a
real number: 50+ deploys, 95% accuracy, 200+ users. Lead with Suede founding-team
story. Supporting credential selected by JD type: AI roles → Corseco Vision API,
full-stack → CNTNDR, backend/data → MQuotient, IoT/infra → Controlytics.
3 paragraphs, under 250 words. Would never write 'excited to apply'.""",
        tools=[ChromaMemoryTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


__all__ = ["create_cover_letter_agent", "SEEKER_PROFILE"]
