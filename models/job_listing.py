"""Job listing model for structured job posting data."""
from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class JobListing(BaseModel):
    """Represents a job posting from any job source."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    company: str
    url: str
    jd_text: str
    source: str
    posted_at: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    is_remote: bool = False
    requires_sponsorship: Optional[bool] = None
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    ats_score: Optional[int] = None
    job_score: Optional[int] = None
    job_grade: Optional[str] = None
    visa_flag: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_duplicate: bool = False

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "url": "https://example.com/jobs/123",
                "jd_text": "We are looking for a senior backend engineer...",
                "source": "ashby",
                "posted_at": "2025-05-10",
                "location": "San Francisco, CA",
                "salary_range": "$180,000 - $220,000",
                "is_remote": True,
                "job_score": 85,
            }
        }

    @classmethod
    def is_relevant_title(cls, title: str) -> bool:
        """Check if job title is relevant based on keywords."""
        title_lower = title.lower()
        relevant = [
            "engineer",
            "developer",
            "backend",
            "full stack",
            "fullstack",
            "software",
            "founding",
            "staff",
            "principal",
            "lead",
            "ai",
            "ml",
            "machine learning",
            "platform",
            "infrastructure",
            "devops",
            "cloud",
            "site reliability",
            "sre",
            "data engineer",
        ]
        exclude = [
            "manager",
            "director",
            "vp",
            "president",
            "designer",
            "product manager",
            "sales",
            "marketing",
            "finance",
            "legal",
            "recruiter",
            "hr",
            "customer success",
            "support",
            "analyst",
            "data analyst",
        ]
        return any(k in title_lower for k in relevant) and not any(
            k in title_lower for k in exclude
        )
