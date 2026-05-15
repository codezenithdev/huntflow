"""Cover letter generation agent — credential matching, LLM drafting, template rendering."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from crewai import Agent
from pydantic import BaseModel

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool

logger = structlog.get_logger(__name__)

CREDENTIAL_MAP = {
    "ai": {
        "signals": ["llm", "rag", "openai", "anthropic", "langchain", "ai engineer", "ml"],
        "story": "At Suede (AI2 Incubator) I shipped AI-integrated auth flows and RBAC dashboards as one of three founding engineers. I also built a computer vision QC system with the Anthropic Vision API and FastAPI that classified manufacturing defects with high accuracy.",
    },
    "backend": {
        "signals": ["backend", "api", "microservice", "java", "spring", "python", "go"],
        "story": "As one of three engineers at Suede (AI2 Incubator-backed), I maintained a Vercel CI/CD pipeline across 50+ production deploys with zero downtime. At MQuotient I built a Python+NLP pipeline achieving 95% extraction accuracy, cutting manual processing by 40%.",
    },
    "fullstack": {
        "signals": ["react", "next.js", "typescript", "full stack", "frontend"],
        "story": "For CNTNDR (a live music competition platform), I owned the full lifecycle: competition bracket logic, track submission flows, and React UI components from scoping to production. At Suede I shipped auth, onboarding, and RBAC dashboards.",
    },
    "devops": {
        "signals": ["aws", "kubernetes", "terraform", "infrastructure", "devops", "cloud", "sre"],
        "story": "I hold the AWS Solutions Architect Associate certification and built know-my-health, a CLI tool aggregating metrics across EC2, EBS, ELB, and S3. At Suede I owned the Vercel CI/CD pipeline for 50+ zero-downtime deploys.",
    },
}

BANNED_PHRASES = [
    "i am excited to apply",
    "i am passionate about",
    "i believe i would be",
    "i am writing to express",
    "please find attached",
    "to whom it may concern",
    "synergy",
    "leverage",
    "utilize",
    "facilitate",
    "i am a quick learner",
    "team player",
    "hard worker",
    "self-starter",
    "results-driven",
]


class CoverLetterData(BaseModel):
    """Cover letter template data."""

    company: str
    job_title: str
    hiring_manager: str | None = None
    opening_paragraph: str
    technical_paragraph: str
    closing_paragraph: str
    linkedin: str = "https://www.linkedin.com/in/angushylesh"


def detect_credential_type(jd_text: str) -> str:
    """Detect best-fit credential type from job description."""
    jd_lower = jd_text.lower()
    scores = {}

    for cred_type, config in CREDENTIAL_MAP.items():
        score = sum(1 for signal in config["signals"] if signal in jd_lower)
        scores[cred_type] = score

    best_fit = max(scores, key=scores.get)
    logger.info("credential_type_detected", type=best_fit, scores=scores)
    return best_fit


def contains_banned_phrase(text: str) -> bool:
    """Check if text contains banned phrases."""
    text_lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            return True
    return False


def generate_cover_letter_content(company: str, job_title: str, jd_snippet: str, cred_type: str | None = None) -> dict:
    """Generate 3 paragraphs for cover letter via LLM."""
    llm = get_llm()

    if not cred_type:
        cred_type = detect_credential_type(jd_snippet)

    cred_config = CREDENTIAL_MAP.get(cred_type, CREDENTIAL_MAP["backend"])
    cred_story = cred_config["story"]

    prompt = f"""Generate a 3-paragraph cover letter for:
Company: {company}
Job Title: {job_title}
Job Description: {jd_snippet[:500]}

CRITICAL RULES:
1. Paragraph 1 (Opening): Start with Suede founding engineer story. Include ONE specific metric/number (e.g., "50+ deploys", "95% accuracy"). Do NOT say "I am excited" or "I am passionate".
2. Paragraph 2 (Technical): Use this credential story: {cred_story}. Must include ONE specific metric (e.g., "95% accuracy", "40% reduction", "5M users"). Connect credential type to JD requirement.
3. Paragraph 3 (Closing): Start with "On day one I will [specific action for this company]." Then say "Happy to discuss how [credential] maps to your [specific company problem/need]."

Output ONLY the 3 paragraphs separated by blank lines. No titles, no preamble. Use first person. No more than 150 words total."""

    response = llm.call(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    content = response.content if hasattr(response, "content") else str(response)

    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    if len(paras) < 3:
        paras = content.split("\n")[:3]

    opening = paras[0] if len(paras) > 0 else ""
    technical = paras[1] if len(paras) > 1 else ""
    closing = paras[2] if len(paras) > 2 else ""

    combined = f"{opening} {technical} {closing}".lower()
    if contains_banned_phrase(combined):
        logger.warning("banned_phrase_detected", company=company)
        return None

    return {
        "opening_paragraph": opening,
        "technical_paragraph": technical,
        "closing_paragraph": closing,
    }


def create_cover_letter_agent(**kwargs) -> Agent:
    """Three-paragraph, JD-calibrated cover letters."""
    return Agent(
        role="Technical Cover Letter Writer",
        goal="Write a 3-paragraph, specific, human-sounding cover letter per top job",
        backstory="""No fluff. No 'I am passionate about'. Every paragraph anchors to a
real number: 50+ deploys, 95% accuracy, 200+ users. Lead with Suede founding-team
story. Supporting credential selected by JD type: AI roles → Vision API,
full-stack → CNTNDR, backend/data → MQuotient, infra → know-my-health.
3 paragraphs, under 250 words. Would never write 'excited to apply'.""",
        tools=[ChromaMemoryTool()],
        llm=get_llm(),
        system_template=seeker_agent_system_context(),
        verbose=kwargs.pop("verbose", True),
        **kwargs,
    )


def generate_and_save_cover_letter(company: str, job_title: str, jd_snippet: str, hiring_manager: str | None = None) -> str | None:
    """Generate cover letter, validate, render template, save file.

    Args:
        company: Company name
        job_title: Job title
        jd_snippet: Job description text
        hiring_manager: Optional hiring manager name

    Returns:
        Path to saved cover letter or None if generation failed
    """
    logger.info("cover_letter_generation_started", company=company, job_title=job_title)

    cred_type = detect_credential_type(jd_snippet)
    attempt = 0
    max_attempts = 2
    content = None

    while attempt < max_attempts:
        content = generate_cover_letter_content(company, job_title, jd_snippet, cred_type)
        if content:
            break
        attempt += 1
        logger.warning("cover_letter_generation_retry", attempt=attempt, company=company)

    if not content:
        logger.error("cover_letter_generation_failed", company=company, max_attempts=max_attempts)
        return None

    env = Environment(loader=FileSystemLoader("data/templates"))
    template = env.get_template("cover_letter.jinja2")

    data = CoverLetterData(
        company=company,
        job_title=job_title,
        hiring_manager=hiring_manager,
        opening_paragraph=content["opening_paragraph"],
        technical_paragraph=content["technical_paragraph"],
        closing_paragraph=content["closing_paragraph"],
    )

    rendered = template.render(**data.model_dump())

    output_dir = Path("data/outreach")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{company.replace(' ', '_')}_cover_letter_{timestamp}.txt"
    filepath = output_dir / filename

    filepath.write_text(rendered, encoding="utf-8")
    logger.info("cover_letter_saved", path=str(filepath), company=company)

    return str(filepath)


__all__ = ["create_cover_letter_agent", "generate_and_save_cover_letter", "CREDENTIAL_MAP", "BANNED_PHRASES"]
