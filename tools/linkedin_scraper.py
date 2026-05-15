"""
LinkedIn Jobs scraper with THREE modes (RSS/Cookie/RapidAPI).

MODE 2 WARNING: Cookie-based authentication violates LinkedIn's TOS.
Your account could be restricted if detected. Use a secondary account.
The li_at cookie expires periodically — update LINKEDIN_LI_AT_COOKIE in .env when it does.
"""
import asyncio
import hashlib
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote
from datetime import datetime, timedelta

import httpx
import structlog
import yaml

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()

# User-Agent rotation for detection avoidance
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36",
]


class LinkedInScraper:
    """LinkedIn jobs scraper with three modes: RSS, Cookie, RapidAPI."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.load_config()
        self.mode = os.getenv("LINKEDIN_MODE", "rss").lower()
        self.validate_mode()
        self.circuit_breaker_file = Path("./data/.linkedin_circuit_breaker")
        self._requests_count = 0
        logger.info("linkedin_scraper_init", mode=self.mode)

    def load_config(self):
        """Load search config."""
        try:
            with open("./config/search_config.yaml") as f:
                config = yaml.safe_load(f)
            self.search_queries = config.get("search_queries", {}).get("primary", [])
            self.filters = config.get("filters", {})
            self.linkedin_config = config.get("linkedin", {})
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.search_queries = ["founding engineer", "backend engineer"]
            self.filters = {}
            self.linkedin_config = {}

    def validate_mode(self):
        """Validate that required API keys exist for selected mode."""
        if self.mode == "cookie":
            if not os.getenv("LINKEDIN_LI_AT_COOKIE"):
                logger.warning("linkedin_cookie_mode_no_key", fallback="rss")
                self.mode = "rss"
        elif self.mode == "rapidapi":
            if not os.getenv("RAPIDAPI_KEY"):
                logger.warning("linkedin_rapidapi_mode_no_key", fallback="rss")
                self.mode = "rss"
        elif self.mode not in ["rss", "cookie", "rapidapi"]:
            logger.warning("linkedin_invalid_mode", mode=self.mode, fallback="rss")
            self.mode = "rss"

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is active."""
        if self.circuit_breaker_file.exists():
            try:
                mtime = self.circuit_breaker_file.stat().st_mtime
                age_seconds = time.time() - mtime
                if age_seconds < 7200:  # 2 hours
                    logger.warning("linkedin_circuit_breaker_active", minutes_remaining=int((7200 - age_seconds) / 60))
                    return True
                else:
                    self.circuit_breaker_file.unlink()
            except Exception:
                pass
        return False

    def _trigger_circuit_breaker(self):
        """Trigger circuit breaker."""
        try:
            self.circuit_breaker_file.parent.mkdir(parents=True, exist_ok=True)
            self.circuit_breaker_file.touch()
            logger.error("linkedin_circuit_breaker_triggered", cooldown_hours=2)
        except Exception as e:
            logger.warning("circuit_breaker_trigger_failed", error=str(e))

    def _get_random_user_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(USER_AGENTS)

    def _normalize_linkedin_url(self, url: str) -> str:
        """Normalize LinkedIn job URL to prevent duplicates."""
        match = re.search(r"linkedin\.com/jobs/view/(\d+)", url)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
        return url

    async def _rate_limit(self):
        """Apply LinkedIn-specific rate limiting."""
        base_delay = float(os.getenv("LINKEDIN_SCRAPE_DELAY", "8.0"))
        jitter = random.uniform(0, 4)
        delay = base_delay + jitter

        # Longer pause every 10 requests
        if self._requests_count > 0 and self._requests_count % 10 == 0:
            delay += random.uniform(30, 60)
            logger.debug("linkedin_pause", reason="every_10_requests", seconds=delay)

        await asyncio.sleep(delay)
        self._requests_count += 1

    async def scrape(self) -> List[JobListing]:
        """Scrape LinkedIn jobs using configured mode."""
        if self._check_circuit_breaker():
            return []

        try:
            if self.mode == "rss":
                return await self._scrape_rss()
            elif self.mode == "cookie":
                results = await self._scrape_cookie()
                if not results:
                    logger.info("cookie_mode_failed_fallback_to_rss")
                    return await self._scrape_rss()
                return results
            elif self.mode == "rapidapi":
                results = await self._scrape_rapidapi()
                if not results:
                    logger.info("rapidapi_mode_failed_fallback_to_rss")
                    return await self._scrape_rss()
                return results
        except Exception as e:
            logger.error("linkedin_scrape_failed", mode=self.mode, error=str(e))
            if self.mode != "rss":
                return await self._scrape_rss()
            return []

    # ============ MODE 1: RSS ============

    async def _scrape_rss(self) -> List[JobListing]:
        """Scrape LinkedIn via public RSS feed (safest mode)."""
        if not feedparser:
            logger.warning("feedparser_not_installed", mode="rss")
            return []

        jobs = []
        max_jobs = int(os.getenv("LINKEDIN_MAX_JOBS_PER_RUN", "50"))
        rss_pages = self.linkedin_config.get("rss_pages", 3)

        async with httpx.AsyncClient(timeout=15) as client:
            for query in self.search_queries:
                if len(jobs) >= max_jobs:
                    break

                for page in range(rss_pages):
                    try:
                        # LinkedIn RSS pagination uses 'start' parameter (0, 25, 50...)
                        start = page * 25
                        url = (
                            f"https://www.linkedin.com/jobs/search/rss?"
                            f"keywords={quote(query)}"
                            f"&location=United+States"
                            f"&f_TPR=r86400"  # Posted in last 24 hours
                            f"&f_JT=F"  # Full-time only
                            f"&start={start}"
                        )

                        headers = {"User-Agent": self._get_random_user_agent()}
                        logger.debug("linkedin_rss_fetch", query=query, page=page)

                        response = await client.get(url, headers=headers)
                        response.raise_for_status()

                        # Parse RSS feed
                        feed = feedparser.parse(response.text)
                        if not feed.entries:
                            break  # No more results

                        for entry in feed.entries:
                            if len(jobs) >= max_jobs:
                                break

                            job = self._parse_rss_item(entry)
                            if job and not self.memory.is_job_seen(job.url):
                                # Optionally fetch full JD from public page
                                if self.linkedin_config.get("fetch_full_jd", True):
                                    full_jd = await self._fetch_full_jd(job.url)
                                    if full_jd:
                                        job.jd_text = full_jd

                                self.memory.store_job(job)
                                jobs.append(job)
                                logger.info(
                                    "linkedin_job_found",
                                    title=job.title,
                                    company=job.company,
                                    source="linkedin_rss",
                                )

                        await self._rate_limit()

                    except Exception as e:
                        logger.warning("linkedin_rss_page_failed", page=page, error=str(e))
                        continue

        logger.info("linkedin_rss_complete", jobs_found=len(jobs))
        return jobs

    def _parse_rss_item(self, entry) -> Optional[JobListing]:
        """Parse a single RSS item into a JobListing."""
        try:
            # RSS title format: "Software Engineer at Stripe"
            title_raw = entry.get("title", "")
            parts = title_raw.split(" at ", 1)
            title = parts[0].strip() if len(parts) == 2 else title_raw
            company = parts[1].strip() if len(parts) == 2 else "Unknown"

            if not JobListing.is_relevant_title(title):
                return None

            url = self._normalize_linkedin_url(entry.get("link", ""))
            if not url:
                return None

            # Parse description (HTML)
            description_html = entry.get("summary", "")
            jd_text = description_html
            if BeautifulSoup:
                try:
                    soup = BeautifulSoup(description_html, "lxml")
                    jd_text = soup.get_text(separator=" ").strip()
                except Exception:
                    pass

            if len(jd_text) < 50:
                return None

            is_remote = "remote" in jd_text.lower() or "remote" in title.lower()

            return JobListing(
                title=title,
                company=company,
                url=url,
                jd_text=jd_text,
                source="linkedin_rss",
                posted_at=entry.get("published", ""),
                is_remote=is_remote,
            )

        except Exception as e:
            logger.debug("linkedin_rss_parse_failed", error=str(e))
            return None

    # ============ MODE 2: Cookie (Authenticated) ============

    async def _scrape_cookie(self) -> List[JobListing]:
        """Scrape LinkedIn via authenticated session (TOS violation risk)."""
        li_at = os.getenv("LINKEDIN_LI_AT_COOKIE")
        if not li_at:
            logger.warning("linkedin_cookie_not_configured")
            return []

        jobs = []
        max_jobs = int(os.getenv("LINKEDIN_MAX_JOBS_PER_RUN", "50"))

        async with httpx.AsyncClient(timeout=15) as client:
            for query in self.search_queries:
                if len(jobs) >= max_jobs:
                    break

                try:
                    logger.debug("linkedin_cookie_query", query=query)

                    # Use LinkedIn's internal Voyager API
                    url = "https://www.linkedin.com/voyager/api/jobs/jobPostings"
                    params = {
                        "keywords": query,
                        "location": "United States",
                        "count": 25,
                        "start": 0,
                    }

                    headers = {
                        "User-Agent": self._get_random_user_agent(),
                        "Cookie": f"li_at={li_at}",
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/vnd.linkedin.normalized+json+2.1",
                    }

                    response = await client.get(url, params=params, headers=headers, follow_redirects=True)

                    # Check for auth wall
                    if response.status_code == 401 or "authwall" in str(response.url):
                        logger.warning("linkedin_cookie_auth_failed")
                        return []

                    if response.status_code == 429:
                        logger.warning("linkedin_cookie_rate_limited")
                        self._trigger_circuit_breaker()
                        return []

                    response.raise_for_status()

                    # Parse JSON response (simplified — actual API response is complex)
                    try:
                        data = response.json()
                        jobs_data = data.get("elements", [])

                        for job_data in jobs_data:
                            if len(jobs) >= max_jobs:
                                break

                            job = self._parse_cookie_job(job_data)
                            if job and not self.memory.is_job_seen(job.url):
                                self.memory.store_job(job)
                                jobs.append(job)
                                logger.info(
                                    "linkedin_job_found",
                                    title=job.title,
                                    company=job.company,
                                    source="linkedin_cookie",
                                )

                    except Exception as e:
                        logger.warning("linkedin_cookie_parse_failed", error=str(e))
                        continue

                    await self._rate_limit()

                except Exception as e:
                    logger.warning("linkedin_cookie_query_failed", query=query, error=str(e))
                    if "401" in str(e) or "authwall" in str(e):
                        return []
                    continue

        logger.info("linkedin_cookie_complete", jobs_found=len(jobs))
        return jobs

    def _parse_cookie_job(self, job_data: dict) -> Optional[JobListing]:
        """Parse a job from LinkedIn Voyager API response."""
        try:
            job_id = job_data.get("jobPostingId")
            if not job_id:
                return None

            title = job_data.get("title", "")
            company = job_data.get("companyName", "")
            url = f"https://www.linkedin.com/jobs/view/{job_id}/"

            if not JobListing.is_relevant_title(title):
                return None

            jd_text = job_data.get("description", "")
            if len(jd_text) < 50:
                return None

            location = job_data.get("location", "")
            is_remote = job_data.get("workplaceType") == "Remote"

            return JobListing(
                title=title,
                company=company,
                url=url,
                jd_text=jd_text,
                source="linkedin_cookie",
                location=location,
                is_remote=is_remote,
            )

        except Exception as e:
            logger.debug("linkedin_cookie_parse_failed", error=str(e))
            return None

    # ============ MODE 3: RapidAPI ============

    async def _scrape_rapidapi(self) -> List[JobListing]:
        """Scrape LinkedIn via RapidAPI (third-party API)."""
        api_key = os.getenv("RAPIDAPI_KEY")
        if not api_key:
            logger.warning("linkedin_rapidapi_key_not_configured")
            return []

        jobs = []
        max_jobs = int(os.getenv("LINKEDIN_MAX_JOBS_PER_RUN", "50"))

        async with httpx.AsyncClient(timeout=15) as client:
            for query in self.search_queries:
                if len(jobs) >= max_jobs:
                    break

                for start in [0, 10, 20]:  # 3 pages max
                    try:
                        logger.debug("linkedin_rapidapi_query", query=query, start=start)

                        url = "https://linkedin-jobs-search.p.rapidapi.com/search"
                        headers = {
                            "X-RapidAPI-Key": api_key,
                            "X-RapidAPI-Host": "linkedin-jobs-search.p.rapidapi.com",
                        }
                        params = {
                            "query": query,
                            "location": "United States",
                            "dateSincePosted": "past24Hours",
                            "jobType": "fullTime",
                            "start": str(start),
                        }

                        response = await client.get(url, headers=headers, params=params)
                        response.raise_for_status()

                        data = response.json()
                        jobs_data = data.get("jobs", [])

                        if not jobs_data:
                            break

                        for job_data in jobs_data:
                            if len(jobs) >= max_jobs:
                                break

                            job = self._parse_rapidapi_job(job_data)
                            if job and not self.memory.is_job_seen(job.url):
                                self.memory.store_job(job)
                                jobs.append(job)
                                logger.info(
                                    "linkedin_job_found",
                                    title=job.title,
                                    company=job.company,
                                    source="linkedin_api",
                                )

                        await self._rate_limit()

                    except Exception as e:
                        logger.warning("linkedin_rapidapi_query_failed", query=query, error=str(e))
                        if "429" in str(e):
                            self._trigger_circuit_breaker()
                            return jobs
                        continue

        logger.info("linkedin_rapidapi_complete", jobs_found=len(jobs))
        return jobs

    def _parse_rapidapi_job(self, job_data: dict) -> Optional[JobListing]:
        """Parse a job from RapidAPI response."""
        try:
            title = job_data.get("title", "")
            company = job_data.get("company_name", "")
            url = job_data.get("job_url", "")

            if not JobListing.is_relevant_title(title):
                return None

            if not url:
                return None

            jd_text = job_data.get("description", "")
            if len(jd_text) < 50:
                return None

            location = job_data.get("location", "")
            is_remote = job_data.get("remote", False)

            return JobListing(
                title=title,
                company=company,
                url=self._normalize_linkedin_url(url),
                jd_text=jd_text,
                source="linkedin_api",
                location=location,
                is_remote=is_remote,
                posted_at=job_data.get("posted_date"),
            )

        except Exception as e:
            logger.debug("linkedin_rapidapi_parse_failed", error=str(e))
            return None

    # ============ Utility ============

    async def _fetch_full_jd(self, linkedin_url: str) -> Optional[str]:
        """Attempt to fetch full JD from public LinkedIn job page."""
        if not BeautifulSoup:
            return None

        try:
            timeout = self.linkedin_config.get("full_jd_timeout", 10)
            headers = {"User-Agent": self._get_random_user_agent()}

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(linkedin_url, headers=headers, follow_redirects=True)

                # Check for auth wall
                if response.status_code != 200 or "authwall" in str(response.url):
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                # Try multiple selectors for job description
                jd_div = (
                    soup.find("div", class_="description__text")
                    or soup.find("div", {"class": lambda c: c and "description" in c})
                    or soup.find("section", class_="show-more-less-html")
                )

                if jd_div:
                    return jd_div.get_text(separator=" ").strip()

                return None

        except Exception as e:
            logger.debug("linkedin_full_jd_fetch_failed", url=linkedin_url, error=str(e))
            return None


async def main():
    """Test LinkedIn scraper."""
    scraper = LinkedInScraper()
    print(f"LinkedIn scraper initialized (mode: {scraper.mode})")
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on LinkedIn ({scraper.mode} mode)")
    if jobs:
        job = jobs[0]
        print(f"Example: {job.title} @ {job.company}")
        print(f"URL: {job.url}")


if __name__ == "__main__":
    asyncio.run(main())
