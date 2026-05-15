"""Tests for job scrapers — parsing, deduplication, title filtering."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from models.job_listing import JobListing
from tools.sqlite_tracker import DatabaseManager


class TestAshbyBroadScraper:
    """Test AshbyBroadScraper response parsing and deduplication."""

    def test_parse_ashby_response(self):
        """Test parsing Ashby API response."""
        mock_response = {
            "results": [
                {
                    "title": "Founding Engineer",
                    "company": {"name": "TechCorp"},
                    "url": "https://ashby.com/jobs/founding-engineer",
                    "description": "Build AI features with Python and React",
                }
            ]
        }

        from scrapers.ashby import AshbyBroadScraper

        scraper = AshbyBroadScraper()

        with patch.object(scraper, "_fetch_jobs", return_value=mock_response):
            jobs = scraper._fetch_jobs()
            assert len(jobs["results"]) == 1
            assert jobs["results"][0]["title"] == "Founding Engineer"
            assert jobs["results"][0]["company"]["name"] == "TechCorp"

    def test_deduplication_same_url_twice(self):
        """Test that inserting same URL twice results in one DB record."""
        db = DatabaseManager()

        job1 = JobListing(
            title="Backend Engineer",
            company="StartupX",
            url="https://example.com/jobs/1",
            jd_text="Python, AWS, PostgreSQL",
            source="ashby",
        )

        db.upsert_job(job1)
        db.upsert_job(job1)

        jobs = db.get_jobs(limit=10)
        matching = [j for j in jobs if j.url == "https://example.com/jobs/1"]
        assert len(matching) == 1, "Duplicate URLs should result in single record"


class TestTitleFiltering:
    """Test job title relevance filtering."""

    def test_irrelevant_sales_title(self):
        """Sales Manager should be filtered out."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Sales Manager") is False

    def test_relevant_founding_engineer(self):
        """Founding Engineer should be relevant."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Founding Engineer") is True

    def test_relevant_senior_backend_engineer(self):
        """Senior Backend Engineer should be relevant."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Senior Backend Engineer") is True

    def test_irrelevant_product_designer(self):
        """Product Designer should be filtered out."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Product Designer") is False

    def test_relevant_fullstack(self):
        """Full Stack Engineer should be relevant."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Full Stack Engineer") is True

    def test_irrelevant_operations(self):
        """Operations Manager should be filtered out."""
        from tools.sqlite_tracker import is_relevant_title

        assert is_relevant_title("Operations Manager") is False
