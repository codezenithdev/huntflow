"""Orchestrates all job scrapers to discover opportunities across the entire US market."""
import asyncio
import sys
import os
from typing import List

import structlog
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager
from tools.ashby_broad_scraper import AshbyBroadScraper
from tools.wellfound_scraper import WellfoundScraper
from tools.yc_scraper import YCScraper
from tools.remotive_scraper import RemotiveScraper
from tools.greenhouse_scraper import GreenhouseScraper

logger = structlog.get_logger()


class JobScraperOrchestrator:
    """Coordinates all job scrapers."""

    def __init__(self):
        """Initialize orchestrator."""
        self.memory = MemoryManager()
        self.load_config()
        self.scrapers = {
            "ashby": AshbyBroadScraper(self.memory),
            "wellfound": WellfoundScraper(self.memory),
            "yc": YCScraper(self.memory),
            "remotive": RemotiveScraper(self.memory),
            "greenhouse": GreenhouseScraper(self.memory),
        }

    def load_config(self):
        """Load configuration."""
        try:
            with open("./config/search_config.yaml") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.config = {}

    async def run_scraper(self, name: str, enabled: bool = True) -> List[JobListing]:
        """Run a single scraper."""
        if not enabled or name not in self.scrapers:
            return []

        try:
            logger.info("scraper_starting", name=name)
            scraper = self.scrapers[name]

            if hasattr(scraper, "scrape"):
                jobs = await scraper.scrape()
            else:
                jobs = []

            logger.info("scraper_complete", name=name, jobs_found=len(jobs))
            return jobs
        except Exception as e:
            logger.error("scraper_failed", name=name, error=str(e))
            return []

    async def run_all(self) -> List[JobListing]:
        """Run all enabled scrapers in parallel."""
        logger.info("job_discovery_start")

        # Get enabled scrapers from config
        board_config = self.config.get("job_boards", {})
        tasks = [
            self.run_scraper(name, board_config.get(name, {}).get("enabled", True))
            for name in self.scrapers.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_jobs.extend(result)
            elif isinstance(result, Exception):
                logger.warning("scraper_exception", error=str(result))

        logger.info("job_discovery_complete", total_jobs=len(all_jobs))

        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)

        return unique_jobs


async def main():
    """Test job discovery."""
    orchestrator = JobScraperOrchestrator()
    jobs = await orchestrator.run_all()

    # Group by source
    by_source = {}
    for job in jobs:
        by_source.setdefault(job.source, []).append(job)

    print("\nJob Discovery Results:")
    print(f"Total jobs found: {len(jobs)}")
    for source in sorted(by_source.keys()):
        print(f"  {source}: {len(by_source[source])} jobs")


if __name__ == "__main__":
    asyncio.run(main())
