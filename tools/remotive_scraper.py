"""Remotive jobs scraper — free remote jobs API."""
import asyncio
import random
import sys
import os
from typing import List

import httpx
import structlog
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()


class RemotiveScraper:
    """Scrapes Remotive remote jobs via free public API."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.base_url = "https://remotive.com/api/remote-jobs"
        self.load_config()

    def load_config(self):
        """Load search config."""
        try:
            with open("./config/search_config.yaml") as f:
                config = yaml.safe_load(f)
            self.filters = config.get("filters", {})
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.filters = {}

    async def scrape(self) -> List[JobListing]:
        """Scrape Remotive remote jobs."""
        jobs = []
        categories = [
            ("software-dev", "Software Development"),
            ("devops-sysadmin", "DevOps/SysAdmin"),
        ]

        async with httpx.AsyncClient(timeout=10) as client:
            for category, category_name in categories:
                try:
                    params = {
                        "category": category,
                        "limit": 100,
                    }

                    logger.info("remotive_scrape_start", category=category)
                    response = await client.get(self.base_url, params=params)
                    response.raise_for_status()

                    data = response.json()
                    jobs_data = data.get("jobs", [])

                    logger.debug("jobs_fetched", count=len(jobs_data), category=category)

                    for job_data in jobs_data:
                        try:
                            url = job_data.get("url", "")
                            if not url:
                                continue

                            if self.memory.is_job_seen(url):
                                logger.debug("job_seen", url=url)
                                continue

                            title = job_data.get("title", "")

                            # Filter by title relevance
                            if not JobListing.is_relevant_title(title):
                                logger.debug("job_title_not_relevant", title=title)
                                continue

                            company = job_data.get("company_name", "")
                            jd_text = job_data.get("description", "")

                            # Check JD length
                            if len(jd_text) < self.filters.get("min_jd_length", 200):
                                logger.debug("job_jd_too_short", url=url)
                                continue

                            job = JobListing(
                                title=title,
                                company=company,
                                url=url,
                                jd_text=jd_text,
                                source="remotive",
                                location="Remote",
                                is_remote=True,
                            )

                            self.memory.store_job(job)
                            jobs.append(job)
                            logger.info("job_found", title=title, company=company, source="remotive")

                        except Exception as e:
                            logger.debug("job_parse_failed", error=str(e))
                            continue

                    # Rate limit (Remotive has no strict rate limits, but be polite)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    logger.warning("remotive_scrape_failed", category=category, error=str(e))
                    continue

        logger.info("remotive_scrape_complete", jobs_found=len(jobs))
        return jobs[:self.filters.get("max_jobs_per_source", 100)]


async def main():
    """Test Remotive scraper."""
    scraper = RemotiveScraper()
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on Remotive")


if __name__ == "__main__":
    asyncio.run(main())
