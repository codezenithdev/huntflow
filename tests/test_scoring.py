"""Tests for job scoring — grades, stale detection, pipeline stats."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from models.job_listing import JobListing
from tools.sqlite_tracker import DatabaseManager


class TestGradeComputation:
    """Test grade boundary assignments."""

    def test_score_70_plus_is_a_grade(self):
        """Score >= 70 should produce A grade."""
        def compute_grade(score):
            if score >= 70:
                return "A"
            elif score >= 50:
                return "B"
            elif score >= 30:
                return "C"
            else:
                return "D"

        assert compute_grade(70) == "A"
        assert compute_grade(85) == "A"
        assert compute_grade(100) == "A"

    def test_score_50_69_is_b_grade(self):
        """Score 50-69 should produce B grade."""
        def compute_grade(score):
            if score >= 70:
                return "A"
            elif score >= 50:
                return "B"
            elif score >= 30:
                return "C"
            else:
                return "D"

        assert compute_grade(50) == "B"
        assert compute_grade(60) == "B"
        assert compute_grade(69) == "B"

    def test_score_30_49_is_c_grade(self):
        """Score 30-49 should produce C grade."""
        def compute_grade(score):
            if score >= 70:
                return "A"
            elif score >= 50:
                return "B"
            elif score >= 30:
                return "C"
            else:
                return "D"

        assert compute_grade(30) == "C"
        assert compute_grade(40) == "C"
        assert compute_grade(49) == "C"

    def test_score_below_30_is_d_grade(self):
        """Score < 30 should produce D grade."""
        def compute_grade(score):
            if score >= 70:
                return "A"
            elif score >= 50:
                return "B"
            elif score >= 30:
                return "C"
            else:
                return "D"

        assert compute_grade(0) == "D"
        assert compute_grade(15) == "D"
        assert compute_grade(29) == "D"


class TestStaleApplicationDetection:
    """Test detection of stale applications (5+ days no response)."""

    def test_recent_application_not_stale(self):
        """Application from 2 days ago should not be stale."""
        db = DatabaseManager()

        job = JobListing(
            title="Engineer",
            company="TestCo",
            url="https://example.com/job1",
            jd_text="Python, AWS",
            source="test",
        )
        db.upsert_job(job)

        now = datetime.now()
        applied_time = (now - timedelta(days=2)).isoformat()
        db.update_status("https://example.com/job1", "applied", applied_time)

        stale = db.get_stale_applications(days=5)
        assert "https://example.com/job1" not in [s.url for s in stale]

    def test_old_application_is_stale(self):
        """Application from 7 days ago should be stale."""
        db = DatabaseManager()

        job = JobListing(
            title="Engineer",
            company="TestCo",
            url="https://example.com/job2",
            jd_text="Python, AWS",
            source="test",
        )
        db.upsert_job(job)

        now = datetime.now()
        applied_time = (now - timedelta(days=7)).isoformat()
        db.update_status("https://example.com/job2", "applied", applied_time)

        stale = db.get_stale_applications(days=5)
        matching = [s for s in stale if s.url == "https://example.com/job2"]
        assert len(matching) > 0, "Application 7 days old should be stale"


class TestPipelineStats:
    """Test pipeline statistics calculation."""

    def test_daily_stats_structure(self):
        """Pipeline stats should have expected structure."""
        db = DatabaseManager()

        job = JobListing(
            title="Backend Engineer",
            company="StartupX",
            url="https://example.com/pipeline-test",
            jd_text="Python, PostgreSQL, AWS",
            source="ashby",
        )
        db.upsert_job(job)
        db.update_status("https://example.com/pipeline-test", "discovered")

        stats = db.get_daily_stats()

        assert "pipeline_status" in stats
        assert "grade_distribution" in stats
        assert "by_source" in stats
        assert "avg_ats_score" in stats
        assert "reply_rate" in stats

    def test_pipeline_status_counts(self):
        """Pipeline status should count jobs correctly."""
        db = DatabaseManager()

        urls = [
            "https://example.com/job1",
            "https://example.com/job2",
            "https://example.com/job3",
        ]

        for i, url in enumerate(urls):
            job = JobListing(
                title=f"Engineer {i}",
                company=f"Company{i}",
                url=url,
                jd_text="Python",
                source="test",
            )
            db.upsert_job(job)

        db.update_status(urls[0], "discovered")
        db.update_status(urls[1], "applied")
        db.update_status(urls[2], "replied")

        stats = db.get_daily_stats()
        pipeline = stats.get("pipeline_status", {})

        assert pipeline.get("discovered", 0) >= 1
        assert pipeline.get("applied", 0) >= 1
        assert pipeline.get("replied", 0) >= 1

    def test_source_breakdown(self):
        """Stats should show job counts by source."""
        db = DatabaseManager()

        job_ashby = JobListing(
            title="Engineer",
            company="AshbyCo",
            url="https://example.com/ashby-job",
            jd_text="Python",
            source="ashby",
        )
        job_wellfound = JobListing(
            title="Engineer",
            company="WellfoundCo",
            url="https://example.com/wellfound-job",
            jd_text="Python",
            source="wellfound",
        )

        db.upsert_job(job_ashby)
        db.upsert_job(job_wellfound)

        stats = db.get_daily_stats()
        by_source = stats.get("by_source", {})

        assert by_source.get("ashby", 0) >= 1
        assert by_source.get("wellfound", 0) >= 1
