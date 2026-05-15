"""CrewAI BaseTool wrappers for scrapers, SQLite, Chroma memory, and Telegram."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any, Coroutine, List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from models import JobListing

logger = logging.getLogger(__name__)


def _run_coro_sync(coro: Coroutine[Any, Any, Any], timeout: float = 900.0) -> Any:
    """Run async coroutine from sync context (handles nested event loops)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _in_thread() -> Any:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_in_thread)
        return fut.result(timeout=timeout)


def _jobs_payload(jobs: List[JobListing], limit: int = 50) -> str:
    slim = [
        {
            "title": j.title,
            "company": j.company,
            "url": j.url,
            "source": j.source,
            "is_remote": j.is_remote,
        }
        for j in jobs[:limit]
    ]
    return json.dumps(
        {"total_found": len(jobs), "returned": len(slim), "truncated": len(jobs) > limit, "jobs": slim},
        indent=2,
    )


class _EmptyInput(BaseModel):
    """Optional note for scraper runs (queries come from config/search_config.yaml)."""

    note: str = Field(
        default="",
        description="Optional note; scrapers use keywords from config/search_config.yaml.",
    )


class AshbyBroadScraperTool(BaseTool):
    name: str = "AshbyBroadJobSearch"
    description: str = (
        "Search Ashby HQ job postings by configured keyword queries across all companies. "
        "Returns a JSON list of engineering roles (title, company, url, source)."
    )
    args_schema: Type[BaseModel] = _EmptyInput

    def _run(self, note: str = "") -> str:
        from tools.ashby_broad_scraper import AshbyBroadScraper

        jobs = _run_coro_sync(AshbyBroadScraper().scrape())
        return _jobs_payload(jobs)


class WellfoundScraperTool(BaseTool):
    name: str = "WellfoundJobSearch"
    description: str = (
        "Scrape Wellfound (AngelList) startup jobs using configured keyword queries. "
        "Returns JSON job summaries."
    )
    args_schema: Type[BaseModel] = _EmptyInput

    def _run(self, note: str = "") -> str:
        from tools.wellfound_scraper import WellfoundScraper

        jobs = _run_coro_sync(WellfoundScraper().scrape())
        return _jobs_payload(jobs)


class YCScraperTool(BaseTool):
    name: str = "YCWorkAtAStartupSearch"
    description: str = (
        "Scrape YC Work at a Startup board with configured engineering keywords. "
        "Returns JSON job summaries."
    )
    args_schema: Type[BaseModel] = _EmptyInput

    def _run(self, note: str = "") -> str:
        from tools.yc_scraper import YCScraper

        jobs = _run_coro_sync(YCScraper().scrape())
        return _jobs_payload(jobs)


class RemotiveScraperTool(BaseTool):
    name: str = "RemotiveRemoteJobSearch"
    description: str = (
        "Scrape Remotive remote job listings for engineering roles from configured queries. "
        "Returns JSON job summaries."
    )
    args_schema: Type[BaseModel] = _EmptyInput

    def _run(self, note: str = "") -> str:
        from tools.remotive_scraper import RemotiveScraper

        jobs = _run_coro_sync(RemotiveScraper().scrape())
        return _jobs_payload(jobs)


class LinkedInScraperTool(BaseTool):
    name: str = "LinkedInJobsSearch"
    description: str = (
        "Search LinkedIn Jobs via configured mode (RSS by default for TOS safety). "
        "High-volume source; returns JSON job summaries."
    )
    args_schema: Type[BaseModel] = _EmptyInput

    def _run(self, note: str = "") -> str:
        from tools.linkedin_scraper import LinkedInScraper

        jobs = _run_coro_sync(LinkedInScraper().scrape())
        return _jobs_payload(jobs)


class ChromaMemoryActionInput(BaseModel):
    action: str = Field(
        ...,
        description="One of: store_job, is_seen, find_similar, check_outreach, get_stats",
    )
    data: str = Field(
        default="",
        description="JSON string or URL, depending on action (see VectorMemory tool docs).",
    )


class ChromaMemoryTool(BaseTool):
    name: str = "VectorMemory"
    description: str = (
        "Vector memory over job postings and outreach history. "
        "Actions: store_job (data=JobListing JSON), is_seen (data=url), "
        "find_similar (data={query,n} JSON), check_outreach (data={company,url} JSON), get_stats (data empty)."
    )
    args_schema: Type[BaseModel] = ChromaMemoryActionInput

    def _run(self, action: str, data: str = "") -> str:
        from tools.chromadb_memory import ChromaMemoryTool as _ChromaMemoryBackend

        return _ChromaMemoryBackend()._run(action, data)


class SQLiteTrackerActionInput(BaseModel):
    action: str = Field(
        ...,
        description="get_stats | get_stale | update_status | get_new_jobs | count_by_source",
    )
    params: str = Field(
        default="{}",
        description='JSON string of parameters, e.g. {"days":5} for get_stale.',
    )


class SQLiteTrackerTool(BaseTool):
    name: str = "ApplicationTracker"
    description: str = (
        "SQLite-backed job and application pipeline. "
        "Actions: get_stats, get_stale (params days), update_status (url, status, notes), "
        "get_new_jobs, count_by_source."
    )
    args_schema: Type[BaseModel] = SQLiteTrackerActionInput

    def _run(self, action: str, params: str = "{}") -> str:
        from tools.sqlite_tracker import SQLiteTrackerTool as _SQLiteTrackerBackend

        return _SQLiteTrackerBackend()._run(action, params)


class TelegramNotifyInput(BaseModel):
    message: str = Field(..., description="Plain-text body to send to the configured Telegram chat.")


class TelegramNotifyTool(BaseTool):
    name: str = "TelegramNotify"
    description: str = (
        "Send a notification to the configured Telegram chat (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). "
        "Use for digests, alerts, and follow-up reminders."
    )
    args_schema: Type[BaseModel] = TelegramNotifyInput

    def _run(self, message: str) -> str:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            return json.dumps(
                {
                    "ok": False,
                    "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set",
                }
            )
        try:
            import httpx

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = httpx.post(
                url,
                json={"chat_id": chat_id, "text": message[:4096]},
                timeout=30.0,
            )
            r.raise_for_status()
            return json.dumps({"ok": True, "status_code": r.status_code})
        except Exception as exc:
            logger.warning("telegram_send_failed: %s", exc)
            return json.dumps({"ok": False, "error": str(exc)})
