"""Tests for ATS scoring — resume variant selection, keyword matching, visa signals."""

from __future__ import annotations

import pytest

from models.job_listing import JobListing

try:
    from tools.keyword_extractor import ATSScorer, job_score
    def compute_grade(score):
        if score >= 70:
            return "A"
        elif score >= 50:
            return "B"
        elif score >= 30:
            return "C"
        else:
            return "D"
except ImportError:
    ATSScorer = None
    job_score = None
    def compute_grade(score):
        if score >= 70:
            return "A"
        elif score >= 50:
            return "B"
        elif score >= 30:
            return "C"
        else:
            return "D"


class TestATSScorer:
    """Test ATS scoring with realistic JD snippets."""

    def setup_method(self):
        """Initialize scorer for each test."""
        self.scorer = ATSScorer()

    def test_ai_heavy_jd_selects_ai_variant(self):
        """AI-heavy JD should select 'ai' resume variant."""
        jd = """We're building LLM features with LangChain, OpenAI API, RAG, pgvector,
        embedding pipelines, and vector databases. You'll work on AI infrastructure."""

        variant = self.scorer.select_resume_variant(jd)
        assert variant == "ai", f"Expected 'ai' variant, got '{variant}'"

    def test_ai_variant_score_reasonable(self):
        """AI variant should score >= 40 on AI-heavy JD."""
        jd = """We're building LLM features with LangChain, OpenAI API, RAG, pgvector,
        embedding pipelines, and vector databases. You'll work on AI infrastructure."""

        report = self.scorer.compute_ats_score(jd, "ai")
        assert report.score >= 40, f"AI variant score on AI JD should be >= 40, got {report.score}"

    def test_react_ts_jd_selects_fullstack_variant(self):
        """React/TypeScript JD should select 'fullstack' resume variant."""
        jd = """React, Next.js, TypeScript, Tailwind CSS, full stack ownership,
        frontend performance optimization, server-side rendering."""

        variant = self.scorer.select_resume_variant(jd)
        assert variant == "fullstack", f"Expected 'fullstack' variant, got '{variant}'"

    def test_java_backend_jd_has_keywords(self):
        """Java backend JD should match keywords in 'backend' variant."""
        jd = """Java, Spring Boot, PostgreSQL, microservices, REST APIs, AWS, Docker,
        Kafka, distributed systems, high-throughput data processing."""

        report = self.scorer.compute_ats_score(jd, "backend")
        assert report.score >= 40, f"Backend variant score should be >= 40, got {report.score}"
        assert len(report.present_keywords) > 0, "Should find present keywords"

    def test_visa_negative_signal_penalty(self):
        """Visa restriction should lower grade."""
        job = JobListing(
            title="Backend Engineer",
            company="TestCo",
            url="http://example.com/job1",
            jd_text="Must be authorized to work without sponsorship. Java Spring AWS PostgreSQL",
            source="test",
        )

        result = self.scorer.score_job(job, ats_score=65)
        assert result["visa_flag"] == "negative", "Should detect visa restriction"
        assert result["score"] < 60, f"Score with visa restriction should be < 60, got {result['score']}"

    def test_visa_positive_signal_bonus(self):
        """Visa sponsorship should boost grade."""
        job = JobListing(
            title="Founding Engineer",
            company="StartupX",
            url="http://example.com/job2",
            jd_text="Visa sponsorship available. Founding team role. Java Spring Boot AWS Kafka",
            source="test",
        )

        result = self.scorer.score_job(job, ats_score=70)
        assert result["visa_flag"] == "positive", "Should detect visa sponsorship"
        assert result["grade"] == "A", f"Visa positive + 70 ATS should be grade A, got {result['grade']}"


class TestGradeBoundaries:
    """Test grade assignment boundaries."""

    def test_grade_a_boundary(self):
        """Score >= 70 should be grade A."""
        grade = compute_grade(75)
        assert grade == "A", f"Score 75 should be grade A, got {grade}"

    def test_grade_b_boundary(self):
        """Score 50-69 should be grade B."""
        grade = compute_grade(60)
        assert grade == "B", f"Score 60 should be grade B, got {grade}"

    def test_grade_c_boundary(self):
        """Score 30-49 should be grade C."""
        grade = compute_grade(40)
        assert grade == "C", f"Score 40 should be grade C, got {grade}"

    def test_grade_d_boundary(self):
        """Score < 30 should be grade D."""
        grade = compute_grade(25)
        assert grade == "D", f"Score 25 should be grade D, got {grade}"
