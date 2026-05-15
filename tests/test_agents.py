"""Smoke tests for CrewAI agent setup (light imports only)."""

import pytest

from agents import get_llm
from config.seeker_profile import seeker_agent_system_context


def test_seeker_agent_system_context_contains_going_by():
    text = seeker_agent_system_context()
    assert "Shylu" in text
    assert "Angushylesh" in text


def test_get_llm_default_groq_prefix(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "llama3-8b-8192")
    llm = get_llm()
    assert "groq" in llm.model.lower()


@pytest.mark.integration
def test_job_discovery_agent_factory():
    """Loads scrapers → chromadb / embeddings; run with ``pytest -m integration``."""
    from agents.job_discovery import create_job_discovery_agent

    agent = create_job_discovery_agent(verbose=False)
    assert agent.role == "US Tech Market Job Scout"
    assert len(agent.tools) == 5


@pytest.mark.integration
def test_resume_optimizer_agent_factory():
    """Imports sentence-transformers / sklearn stack — optional in CI."""
    from agents.resume_optimizer import create_resume_optimizer_agent

    agent = create_resume_optimizer_agent(verbose=False)
    assert "ATS" in agent.role
