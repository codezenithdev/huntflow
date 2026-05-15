"""YC (Y Combinator) jobs scraper using public API."""
import asyncio
import random
import sys
import os
from typing import List
from urllib.parse import quote

import httpx
import structlog
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()


class YCScraper:
    """Scrapes Y Combinator jobs via public API."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.base_url = "https://www.workatastartup.com/jobs"
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

    async def scrape(self) -> List[JobListing]:
        """Scrape YC jobs by keyword."""
        jobs = []

        async with httpx.AsyncClient(timeout=10) as client:
            for query in self.search_queries:
                try:
                    params = {
                        "query": query,
                        "usJobsOnly": "true",
                        "jobType": "fulltime",
                    }

                    logger.info("yc_scrape_start", query=query)
                    response = await client.get(self.base_url, params=params)
                    response.raise_for_status()

                    # Parse JSON response
                    data = response.json()
                    jobs_data = data.get("jobs", [])

                    logger.debug("jobs_fetched", count=len(jobs_data), query=query)

                    for job_data in jobs_data:
                        try:
                            url = job_data.get("id", "")
                            if not url:
                                continue

                            # Build full URL
                            if not url.startswith("http"):
                                url = f"https://www.workatastartup.com/jobs/{url}"

                            if self.memory.is_job_seen(url):
                                logger.debug("job_seen", url=url)
                                continue

                            title = job_data.get("title", "")

                            # Filter by title relevance
                            if not JobListing.is_relevant_title(title):
                                logger.debug("job_title_not_relevant", title=title)
                                continue

                            company = job_data.get("company_name", "")
                            location = job_data.get("location", "")
                            jd_text = job_data.get("description", "")

                            # Check JD length
                            if len(jd_text) < self.filters.get("min_jd_length", 200):
                                logger.debug("job_jd_too_short", url=url)
                                continue

                            # Extract equity if available
                            equity = job_data.get("equity_max")
                            salary_range = None
                            if job_data.get("salary_min") and job_data.get("salary_max"):
                                salary_range = f"${job_data.get('salary_min'):,} - ${job_data.get('salary_max'):,}"

                            job = JobListing(
                                title=title,
                                company=company,
                                url=url,
                                jd_text=jd_text,
                                source="yc",
                                location=location,
                                salary_range=salary_range,
                                is_remote=job_data.get("remote", False),
                            )

                            self.memory.store_job(job)
                            jobs.append(job)
                            logger.info("job_found", title=title, company=company, source="yc")

                        except Exception as e:
                            logger.debug("job_parse_failed", error=str(e))
                            continue

                    # Rate limit
                    await asyncio.sleep(random.uniform(self.scrape_delay_min, self.scrape_delay_max))

                except Exception as e:
                    logger.warning("yc_scrape_failed", query=query, error=str(e))
                    continue

        logger.info("yc_scrape_complete", jobs_found=len(jobs))
        return jobs[:self.filters.get("max_jobs_per_source", 100)]


async def main():
    """Test YC scraper."""
    scraper = YCScraper()
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on YC")


if __name__ == "__main__":
    asyncio.run(main())
