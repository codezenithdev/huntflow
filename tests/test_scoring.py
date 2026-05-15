"""Tests for job opportunity scoring (job_score)."""
from tools.keyword_extractor import job_score
from models import JobListing


def _job(**kwargs):
    base = dict(
        title="Software Engineer",
        company="Co",
        url="https://example.com",
        jd_text="We ship software.",
        source="t",
    )
    base.update(kwargs)
    return JobListing(**base)


def test_job_score_title_tiers():
    founding = _job(title="Founding Engineer", jd_text="Build things.")
    assert job_score(founding, 0)["score"] >= job_score(_job(title="Engineer"), 0)["score"]


def test_job_score_negative_visa():
    j = _job(
        jd_text="Must be authorized to work in the US without sponsorship. Python.",
    )
    out = job_score(j, 50)
    assert out["visa_flag"] == "negative"
    assert any("sponsorship" in r.lower() for r in out["reasons"])


def test_job_score_ats_contribution():
    low = job_score(_job(jd_text="python react"), 20)
    high = job_score(_job(jd_text="python react"), 90)
    assert high["score"] >= low["score"]
