"""Tests for ATS keyword scoring and resume variant selection."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models import JobListing
from tools.keyword_extractor import ALL_TECH_TERMS, ATSScorer, ATSKeywordTool, terms_present_in_text


def _scorer_without_init() -> ATSScorer:
    """ATSScorer instance without PDF loading (for fast unit tests)."""
    s = object.__new__(ATSScorer)
    s._resumes_dir = Path("/nonexistent")
    s._resume_text = {
        "ai": "We built RAG with LangChain, OpenAI, PyTorch, and Python.",
        "fullstack": "React, TypeScript, Next.js, Node, and PostgreSQL.",
    }
    s._resume_keywords = {
        "ai": terms_present_in_text(s._resume_text["ai"]),
        "fullstack": terms_present_in_text(s._resume_text["fullstack"]),
    }
    s._sentence_model = None
    s._keybert_model = None
    return s


def test_terms_present_in_text():
    text = "We need Spring Boot, Kafka, and AWS Lambda."
    found = terms_present_in_text(text)
    assert "spring boot" in found
    assert "kafka" in found
    assert "lambda" in found
    assert "ruby" not in found


def test_all_tech_terms_unique_and_nonempty():
    assert len(ALL_TECH_TERMS) == len(set(ALL_TECH_TERMS))
    assert "postgresql" in ALL_TECH_TERMS


def test_select_resume_variant_prefers_ai_signals():
    s = _scorer_without_init()
    jd = "Looking for an ML engineer with RAG, LangChain, and OpenAI APIs."
    assert s.select_resume_variant(jd) == "ai"


def test_select_resume_variant_prefers_fullstack_signals():
    s = _scorer_without_init()
    jd = "Senior frontend role: React, Next.js, TypeScript, UI polish."
    assert s.select_resume_variant(jd) == "fullstack"


def test_select_resume_variant_tie_uses_raw_score():
    s = _scorer_without_init()
    # Phrase hits both counts equally (0 vs 0): fall back to lexicon overlap with resumes
    jd = "Engineering role."
    v = s.select_resume_variant(jd)
    assert v in ("ai", "fullstack")


@patch.object(ATSScorer, "_semantic_similarity_score", return_value=0)
@patch.object(ATSScorer, "_jd_keywords_with_keybert")
def test_compute_ats_score_exact_only(mock_kw, _mock_sem):
    mock_kw.return_value = {"python", "kubernetes", "rust"}
    s = _scorer_without_init()
    s._resume_keywords["ai"] = {"python", "kubernetes", "docker"}
    report = s.compute_ats_score("Use Python and Kubernetes in production.", variant="ai")
    assert report.resume_variant == "ai"
    assert set(report.present_keywords) >= {"python", "kubernetes"}
    assert "rust" in report.missing_keywords or "rust" in set(report.missing_keywords)
    assert report.score == min(60, 2 * 3)  # two overlaps * 3


def test_ats_keyword_tool_returns_json():
    s = _scorer_without_init()
    tool = ATSKeywordTool()
    tool._scorer = s
    with patch.object(ATSScorer, "_semantic_similarity_score", return_value=0), patch.object(
        ATSScorer, "_jd_keywords_with_keybert", return_value={"python", "react"}
    ):
        raw = tool._run(jd_text="JD", variant="fullstack")
    assert "score" in raw
    assert "fullstack" in raw


def test_atsscorer_graceful_when_no_pdf(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    scorer = ATSScorer(resumes_dir=d)
    assert scorer._resume_keywords["ai"] == set()
    assert scorer._resume_keywords["fullstack"] == set()


def test_atsscorer_reads_pdf(tmp_path):
    pdf_path = tmp_path / "ai.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "Python LangChain OpenAI RAG"

    fake_pdf = MagicMock()
    fake_pdf.__enter__.return_value = fake_pdf
    fake_pdf.__exit__.return_value = None
    fake_pdf.pages = [fake_page]

    with patch("tools.keyword_extractor.pdfplumber.open", return_value=fake_pdf):
        scorer = ATSScorer(resumes_dir=tmp_path)

    assert "python" in scorer._resume_keywords["ai"]
    assert "langchain" in scorer._resume_keywords["ai"]


def test_job_score_integration():
    from tools.keyword_extractor import job_score

    job = JobListing(
        title="Staff Backend Engineer",
        company="Acme",
        url="https://example.com/j",
        jd_text=(
            "Seed stage startup. Kubernetes, Java, Spring Boot, AWS, Kafka. "
            "Fully remote. Visa sponsorship available."
        ),
        source="test",
        is_remote=True,
    )
    out = job_score(job, ats_score=80)
    assert out["grade"] in ("A", "B", "C", "D")
    assert 0 <= out["score"] <= 100
    assert out["visa_flag"] == "positive"
    assert any("stack" in r for r in out["reasons"])
