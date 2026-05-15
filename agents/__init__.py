"""HuntFlow CrewAI agents — shared LLM factory."""

from __future__ import annotations

import os
from typing import Any

from crewai import LLM

from config.seeker_profile import SEEKER_PROFILE, seeker_agent_system_context


def get_llm() -> Any:
    """Return the configured CrewAI LLM (Groq, OpenAI, or Ollama via LiteLLM)."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    if provider == "groq":
        # Use mixtral-8x7b-32768 (stable, fast) or llama-3.1-70b-versatile (more capable)
        # llama3-8b-8192 was decommissioned; use this as fallback
        model = os.getenv("LLM_MODEL", "mixtral-8x7b-32768")
        if not model.startswith("groq/"):
            model = f"groq/{model.removeprefix('groq/')}"
        return LLM(model=model, temperature=0.3, api_key=os.getenv("GROQ_API_KEY"))
    if provider == "openai":
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        if not model.startswith("openai/"):
            model = f"openai/{model.removeprefix('openai/')}"
        return LLM(model=model, temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("LLM_MODEL", "llama3.2")
    if not model.startswith("ollama/"):
        model = f"ollama/{model.removeprefix('ollama/')}"
    return LLM(
        model=model,
        temperature=0.3,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    )


__all__ = ["get_llm", "SEEKER_PROFILE", "seeker_agent_system_context"]
