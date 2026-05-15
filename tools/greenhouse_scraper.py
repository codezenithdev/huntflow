"""Greenhouse jobs scraper — using public API for known engineering companies."""
import asyncio
import random
import sys
import os
from pathlib import Path
from typing import List

import httpx
import structlog
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()

# Bootstrap list of engineering companies on Greenhouse
GREENHOUSE_SLUGS = [
    "stripe",
    "coinbase",
    "figma",
    "notion",
    "airtable",
    "zapier",
    "gitlab",
    "hashicorp",
    "datadog",
    "twilio",
    "segment",
    "brex",
    "plaid",
    "rippling",
    "gusto",
    "lattice",
    "gem",
    "ashby",
    "vercel",
    "linear",
    "loom",
    "miro",
    "pitch",
    "retool",
    "webflow",
]


class GreenhouseScraper:
    """Scrapes Greenhouse jobs from known engineering companies."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.base_url = "https://boards-api.greenhouse.io/v1/boards"
        self.discovered_slugs_file = Path("./data/greenhouse_discovered_slugs.txt")
        self.load_config()
        self.load_slugs()

    def load_config(self):
        """Load search config."""
        try:
            with open("./config/search_config.yaml") as f:
                config = yaml.safe_load(f)
            self.filters = config.get("filters", {})
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.filters = {}

    def load_slugs(self):
        """Load discovered slugs from file."""
        self.slugs = set(GREENHOUSE_SLUGS)
        if self.discovered_slugs_file.exists():
            try:
                with open(self.discovered_slugs_file) as f:
                    discovered = f.read().strip().split("\n")
                    self.slugs.update([s for s in discovered if s])
                logger.info("discovered_slugs_loaded", count=len(self.slugs))
            except Exception as e:
                logger.warning("discovered_slugs_load_failed", error=str(e))

    def save_discovered_slug(self, slug: str):
        """Add newly discovered slug to file."""
        try:
            self.discovered_slugs_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.discovered_slugs_file, "a") as f:
                if slug not in self.slugs:
                    f.write(f"{slug}\n")
                    self.slugs.add(slug)
        except Exception as e:
            logger.debug("slug_save_failed", slug=slug, error=str(e))

    async def scrape(self) -> List[JobListing]:
        """Scrape Greenhouse jobs from known companies."""
        jobs = []

        async with httpx.AsyncClient(timeout=10) as client:
            for slug in list(self.slugs):
                try:
                    logger.info("greenhouse_scrape_start", slug=slug)
                    url = f"{self.base_url}/{slug}/jobs"
                    response = await client.get(url)
                    response.raise_for_status()

                    data = response.json()
                    jobs_data = data.get("jobs", [])

                    logger.debug("jobs_fetched", count=len(jobs_data), slug=slug)

                    for job_data in jobs_data:
                        try:
                            job_id = job_data.get("id")
                            if not job_id:
                                continue

                            # Build URL from job ID
                            url = f"{self.base_url}/{slug}/jobs/{job_id}"

                            if self.memory.is_job_seen(url):
                                logger.debug("job_seen", url=url)
                                continue

                            title = job_data.get("title", "")

                            # Filter by title relevance
                            if not JobListing.is_relevant_title(title):
                                logger.debug("job_title_not_relevant", title=title)
                                continue

                            company = job_data.get("company", {}).get("name", "")
                            location_name = job_data.get("location", {})
                            if isinstance(location_name, dict):
                                location = location_name.get("name", "")
                            else:
                                location = location_name

                            jd_text = job_data.get("content", "")
                            if not jd_text:
                                # Use title as fallback
                                jd_text = f"{title} {company} {location}"

                            # Check JD length
                            if len(jd_text) < self.filters.get("min_jd_length", 200):
                                logger.debug("job_jd_too_short", url=url)
                                continue

                            job = JobListing(
                                title=title,
                                company=company,
                                url=url,
                                jd_text=jd_text,
                                source="greenhouse",
                                location=location,
                                posted_at=job_data.get("created_at"),
                            )

                            self.memory.store_job(job)
                            jobs.append(job)
                            logger.info("job_found", title=title, company=company, source="greenhouse")

                        except Exception as e:
                            logger.debug("job_parse_failed", error=str(e))
                            continue

                    # Rate limit
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning("greenhouse_scrape_failed", slug=slug, error=str(e))
                    continue

        logger.info("greenhouse_scrape_complete", jobs_found=len(jobs))
        return jobs[:self.filters.get("max_jobs_per_source", 100)]


async def main():
    """Test Greenhouse scraper."""
    scraper = GreenhouseScraper()
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on Greenhouse")


if __name__ == "__main__":
    asyncio.run(main())
