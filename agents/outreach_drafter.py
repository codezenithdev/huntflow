"""Founder-grade cold outreach drafts (never auto-send)."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader
from crewai import Agent
from pydantic import BaseModel

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

from agents import get_llm
from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context
from tools.crewai_wrappers import ChromaMemoryTool

logger = structlog.get_logger(__name__)

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

KNOWN_FOUNDERS = {
    "anthropic": "Dario Amodei",
    "openai": "Sam Altman",
    "perplexity": "Aravind Srinivas",
    "hugging face": "Clement Delangue",
    "databricks": "Matei Zaharia",
}


class ColdEmailData(BaseModel):
    """Cold email template data."""

    company: str
    title: str
    first_name: str | None = None
    role_title: str | None = None
    subject_line: str
    hook_line: str
    credential_line: str
    connection_line: str
    ask_line: str
    linkedin: str = "https://www.linkedin.com/in/angushylesh"
    github: str = "https://github.com/angushylesh"
    generated_at: str | None = None


class OutreachResult(BaseModel):
    """Result of outreach email generation."""

    company: str
    subject: str
    body: str
    saved_path: str | None = None
    is_duplicate: bool = False
    error: str | None = None


def get_chromadb_client():
    """Get ChromaDB client for deduplication."""
    try:
        import chromadb
        from chromadb.config import Settings

        settings = Settings(allow_reset=True, anonymized_telemetry=False)
        client = chromadb.Client(settings)
        return client.get_or_create_collection(name="outreach_sent")
    except Exception as e:
        logger.warning("chromadb_init_failed", error=str(e))
        return None


def check_outreach_duplicate(company: str) -> bool:
    """Check if outreach already sent to company."""
    try:
        collection = get_chromadb_client()
        if not collection:
            return False
        results = collection.get(where={"company": company})
        return len(results.get("ids", [])) > 0
    except Exception as e:
        logger.warning("chromadb_duplicate_check_failed", company=company, error=str(e))
        return False


def store_outreach_hash(company: str, subject: str, body: str) -> None:
    """Store outreach hash in ChromaDB."""
    try:
        collection = get_chromadb_client()
        if not collection:
            return
        content_hash = hashlib.sha256(f"{company}{subject}{body}".encode()).hexdigest()
        collection.upsert(
            ids=[content_hash],
            documents=[f"{subject}\n{body}"],
            metadatas=[{"company": company, "sent_at": datetime.now().isoformat()}],
        )
    except Exception as e:
        logger.warning("chromadb_store_failed", company=company, error=str(e))


def search_company_news(company: str) -> str:
    """Search for recent company news via Tavily."""
    try:
        if not TavilyClient:
            logger.warning("tavily_not_installed")
            return ""

        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("tavily_api_key_missing")
            return ""

        client = TavilyClient(api_key=api_key)
        query = f'"{company}" site:techcrunch.com OR "{company}" launch OR "{company}" site:github.com 2024 2025'
        response = client.search(query, max_results=3)

        results = response.get("results", [])
        if results:
            news = " ".join([r.get("content", "") for r in results[:2]])
            logger.info("company_news_found", company=company, result_count=len(results))
            return news[:500]
        return ""
    except Exception as e:
        logger.warning("tavily_search_failed", company=company, error=str(e))
        return ""


def extract_hook(company: str, news: str, jd_snippet: str) -> str:
    """Extract a specific, factual hook from news or JD."""
    if not news:
        return f"{company} is doing interesting work in their domain."

    sentences = re.split(r"[.!?]+", news)
    for sentence in sentences:
        if company.lower() in sentence.lower() and len(sentence) > 30:
            return sentence.strip() + "."

    return f"{company} recently made headlines for their innovation."


def generate_subject_line(company: str, job_title: str) -> str:
    """Generate subject line — different for known founders."""
    founder = KNOWN_FOUNDERS.get(company.lower())

    if founder:
        first_name = founder.split()[0]
        return f"Hi {first_name} — {job_title} at {company}"

    return f"{company}: {job_title} — founding team background"


def generate_email_body(company: str, job_title: str, hook: str, first_name: str | None = None) -> dict | None:
    """Generate 4-line cold email via LLM."""
    llm = get_llm()

    prompt = f"""Generate a 4-sentence cold email for outreach to {company} ({job_title} role).

CRITICAL RULES:
1. Line 1 (Hook): "{hook}"
2. Line 2 (Credential): Start with "I'm Shylu, [credential]." Include ONE specific metric (e.g., "95% accuracy", "shipped 50+ features", "5M users").
3. Line 3 (Connection): Connect your credential to company's evident need from hook. Start with "That's relevant because..."
4. Line 4 (Ask): "Worth a 15-minute call this week?"

CONSTRAINTS:
- Maximum 150 words total
- NO banned phrases: "excited", "passionate", "synergy", "leverage", "I believe"
- NO generic praise ("innovative", "best-in-class", "cutting-edge")
- NO "Dear Hiring Manager" or "To Whom It May Concern"
- Use first person, conversational tone
- Numbers REQUIRED in lines 2 and/or 3

Output ONLY the 4 lines separated by single blank lines. No subject, no signature."""

    response = llm.call(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
    )
    content = response.content if hasattr(response, "content") else str(response)

    lines = [line.strip() for line in content.split("\n") if line.strip()]

    if len(lines) < 4:
        logger.warning("email_generation_incomplete", company=company, line_count=len(lines))
        return None

    hook_line = lines[0]
    credential_line = lines[1]
    connection_line = lines[2]
    ask_line = lines[3]

    combined = f"{hook_line} {credential_line} {connection_line} {ask_line}".lower()
    word_count = len(combined.split())

    for phrase in BANNED_PHRASES:
        if phrase in combined:
            logger.warning("banned_phrase_detected", company=company, phrase=phrase)
            return None

    if word_count > 150:
        logger.warning("email_too_long", company=company, word_count=word_count)
        return None

    return {
        "hook_line": hook_line,
        "credential_line": credential_line,
        "connection_line": connection_line,
        "ask_line": ask_line,
    }


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


def generate_and_save_outreach_email(company: str, job_title: str, jd_snippet: str, first_name: str | None = None) -> OutreachResult:
    """Generate cold email, validate, render template, save file, store in ChromaDB.

    Args:
        company: Company name
        job_title: Job title
        jd_snippet: Job description text
        first_name: Optional first name of recipient

    Returns:
        OutreachResult with subject, body, saved_path
    """
    logger.info("outreach_generation_started", company=company, job_title=job_title)

    if check_outreach_duplicate(company):
        logger.info("outreach_duplicate_skipped", company=company)
        return OutreachResult(
            company=company,
            subject="",
            body="",
            is_duplicate=True,
            error=f"DUPLICATE - outreach already sent to {company}",
        )

    news = search_company_news(company)
    hook = extract_hook(company, news, jd_snippet)
    subject = generate_subject_line(company, job_title)
    body_content = generate_email_body(company, job_title, hook, first_name)

    if not body_content:
        logger.error("outreach_generation_failed", company=company)
        return OutreachResult(
            company=company,
            subject=subject,
            body="",
            error="Failed to generate valid email body",
        )

    env = Environment(loader=FileSystemLoader("data/templates"))
    template = env.get_template("cold_email.jinja2")

    data = ColdEmailData(
        company=company,
        title=job_title,
        first_name=first_name,
        role_title=job_title,
        subject_line=subject,
        hook_line=body_content["hook_line"],
        credential_line=body_content["credential_line"],
        connection_line=body_content["connection_line"],
        ask_line=body_content["ask_line"],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    rendered = template.render(**data.model_dump())
    store_outreach_hash(company, subject, rendered)

    output_dir = Path("data/outreach")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{company.replace(' ', '_')}_email_{timestamp}.txt"
    filepath = output_dir / filename

    filepath.write_text(rendered, encoding="utf-8")
    logger.info("outreach_email_saved", path=str(filepath), company=company)

    return OutreachResult(
        company=company,
        subject=subject,
        body=rendered,
        saved_path=str(filepath),
    )


__all__ = ["create_outreach_drafter_agent", "generate_and_save_outreach_email", "OutreachResult", "BANNED_PHRASES"]
