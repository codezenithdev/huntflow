"""Ashby jobs scraper — keyword search across all companies."""
import asyncio
import random
import sys
import os
from typing import List

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()


class AshbyBroadScraper:
    """Scrapes Ashby HQ jobs by keyword across all companies."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.base_url = "https://jobs.ashbyhq.com/api/non-user-graphql"
        self.fallback_url = "https://jobs.ashbyhq.com"
        self.load_config()

    def load_config(self):
        """Load search config."""
        try:
            with open("./config/search_config.yaml") as f:
                config = yaml.safe_load(f)
            self.search_queries = config.get("search_queries", {}).get("primary", [])
            self.filters = config.get("filters", {})
            self.scrape_delay_min = 2.0
            self.scrape_delay_max = 5.0
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.search_queries = ["founding engineer", "backend engineer"]
            self.filters = {}
            self.scrape_delay_min = 2.0
            self.scrape_delay_max = 5.0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _fetch_graphql(self, session: httpx.AsyncClient, query: str) -> dict:
        """Fetch jobs via GraphQL API."""
        payload = {
            "query": """
            query ApiJobPostingSearchResult($query: String!) {
              searchJobPostings(query: $query, limit: 50) {
                id
                title
                location
                description
                companyName
                status
                jobUrl
                postedDate
              }
            }
            """,
            "variables": {"query": query},
        }

        response = await session.post(self.base_url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    async def scrape(self) -> List[JobListing]:
        """Scrape Ashby jobs by keyword search."""
        jobs = []

        async with httpx.AsyncClient(headers={"User-Agent": "HuntFlow/1.0"}) as session:
            for query in self.search_queries:
                try:
                    logger.info("ashby_scrape_start", query=query)
                    result = await self._fetch_graphql(session, query)

                    # Parse response
                    if "data" in result and "searchJobPostings" in result["data"]:
                        for job_data in result["data"]["searchJobPostings"]:
                            try:
                                url = job_data.get("jobUrl", "")
                                if not url:
                                    continue

                                # Check if already seen
                                if self.memory.is_job_seen(url):
                                    logger.debug("job_seen", url=url)
                                    continue

                                title = job_data.get("title", "")

                                # Filter by title relevance
                                if not JobListing.is_relevant_title(title):
                                    logger.debug("job_title_not_relevant", title=title)
                                    continue

                                # Check location
                                location = job_data.get("location", "")
                                jd_text = job_data.get("description", "")

                                if not self._is_us_location(location, jd_text):
                                    logger.debug("job_location_not_us", location=location)
                                    continue

                                # Check JD length
                                if len(jd_text) < self.filters.get("min_jd_length", 200):
                                    logger.debug("job_jd_too_short", url=url)
                                    continue

                                job = JobListing(
                                    title=title,
                                    company=job_data.get("companyName", ""),
                                    url=url,
                                    jd_text=jd_text,
                                    source="ashby",
                                    location=location,
                                    posted_at=job_data.get("postedDate"),
                                )

                                self.memory.store_job(job)
                                jobs.append(job)
                                logger.info("job_found", title=title, company=job.company, source="ashby")

                            except Exception as e:
                                logger.debug("job_parse_failed", error=str(e))
                                continue

                    # Rate limit
                    await asyncio.sleep(random.uniform(self.scrape_delay_min, self.scrape_delay_max))

                except Exception as e:
                    logger.warning("ashby_scrape_failed", query=query, error=str(e))
                    continue

        logger.info("ashby_scrape_complete", jobs_found=len(jobs))
        return jobs[:self.filters.get("max_jobs_per_source", 100)]

    def _is_us_location(self, location: str, jd_text: str) -> bool:
        """Check if job is in US."""
        combined = f"{location} {jd_text}".lower()
        us_signals = self.filters.get("us_location_signals", [])

        # If location/JD is empty, assume US
        if not location:
            return True

        return any(signal in combined for signal in us_signals)


async def main():
    """Test Ashby scraper."""
    scraper = AshbyBroadScraper()
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on Ashby")


if __name__ == "__main__":
    asyncio.run(main())
