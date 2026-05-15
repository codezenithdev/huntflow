"""Wellfound jobs scraper — for YC startups."""
import asyncio
import random
import sys
import os
from typing import List
from urllib.parse import quote

import structlog
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import JobListing
from tools.chromadb_memory import MemoryManager

logger = structlog.get_logger()

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright_not_installed")


class WellfoundScraper:
    """Scrapes Wellfound (YC) jobs by keyword."""

    def __init__(self, memory: MemoryManager = None):
        """Initialize the scraper."""
        self.memory = memory or MemoryManager()
        self.load_config()

    def load_config(self):
        """Load search config."""
        try:
            with open("./config/search_config.yaml") as f:
                config = yaml.safe_load(f)
            self.search_queries = config.get("search_queries", {}).get("primary", [])
            self.filters = config.get("filters", {})
        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            self.search_queries = ["founding engineer", "backend engineer"]
            self.filters = {}

    async def scrape(self) -> List[JobListing]:
        """Scrape Wellfound jobs."""
        if not HAS_PLAYWRIGHT:
            logger.warning("wellfound_skipped", reason="playwright_not_installed")
            return []

        jobs = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = await context.new_page()

                for query in self.search_queries:
                    try:
                        url = f"https://wellfound.com/jobs?query={quote(query)}&locationFilter=United+States"
                        logger.info("wellfound_scrape_start", query=query)

                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(random.uniform(1.5, 2.5))

                        # Scroll to load more jobs
                        for _ in range(3):
                            await page.evaluate("window.scrollBy(0, window.innerHeight)")
                            await asyncio.sleep(random.uniform(0.5, 1.5))

                        # Extract job cards
                        job_elements = await page.query_selector_all("[data-testid='job-card']")
                        logger.debug("jobs_found", count=len(job_elements), query=query)

                        for element in job_elements:
                            try:
                                title = await element.query_selector(
                                    "[data-testid='job-title']"
                                ).inner_text() if await element.query_selector("[data-testid='job-title']") else ""

                                if not title or not JobListing.is_relevant_title(title):
                                    continue

                                company = await element.query_selector(
                                    "[data-testid='job-company']"
                                ).inner_text() if await element.query_selector("[data-testid='job-company']") else ""

                                job_url = await element.query_selector("a").get_attribute(
                                    "href"
                                ) if await element.query_selector("a") else ""

                                if not job_url or self.memory.is_job_seen(job_url):
                                    continue

                                location = await element.query_selector(
                                    "[data-testid='job-location']"
                                ).inner_text() if await element.query_selector("[data-testid='job-location']") else ""

                                # Simple JD text — use title + location as proxy
                                jd_text = f"{title} {company} {location} {query}"

                                if len(jd_text) < self.filters.get("min_jd_length", 200):
                                    continue

                                job = JobListing(
                                    title=title,
                                    company=company,
                                    url=job_url,
                                    jd_text=jd_text,
                                    source="wellfound",
                                    location=location,
                                )

                                self.memory.store_job(job)
                                jobs.append(job)
                                logger.info("job_found", title=title, company=company, source="wellfound")

                            except Exception as e:
                                logger.debug("job_extract_failed", error=str(e))
                                continue

                        await asyncio.sleep(random.uniform(2.0, 4.0))

                    except Exception as e:
                        logger.warning("wellfound_query_failed", query=query, error=str(e))
                        continue

                await browser.close()

        except Exception as e:
            logger.error("wellfound_scrape_failed", error=str(e))

        logger.info("wellfound_scrape_complete", jobs_found=len(jobs))
        return jobs[:self.filters.get("max_jobs_per_source", 100)]


async def main():
    """Test Wellfound scraper."""
    scraper = WellfoundScraper()
    jobs = await scraper.scrape()
    print(f"Found {len(jobs)} jobs on Wellfound")


if __name__ == "__main__":
    if HAS_PLAYWRIGHT:
        asyncio.run(main())
    else:
        print("Playwright not installed. Install with: pip install playwright")
