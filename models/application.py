"""Application tracking model for job application states and history."""
from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class Application(BaseModel):
    """Tracks a job application through the hiring funnel."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    company: str
    title: str
    url: str
    status: str
    source: str
    applied_at: Optional[datetime] = None
    outreach_sent_at: Optional[datetime] = None
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    follow_up_due_at: Optional[datetime] = None
    notes: Optional[str] = None
    resume_variant: Optional[str] = None
    ats_score: Optional[int] = None
    job_score: Optional[int] = None
    cover_letter_path: Optional[str] = None
    outreach_email_path: Optional[str] = None
    salary_offered: Optional[str] = None
    rejection_reason: Optional[str] = None

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "job_id": "job-123",
                "company": "Acme Corp",
                "title": "Senior Backend Engineer",
                "url": "https://example.com/jobs/123",
                "status": "interviewing",
                "source": "ashby",
                "applied_at": "2025-05-12T10:30:00",
                "ats_score": 85,
                "job_score": 82,
                "follow_up_due_at": "2025-05-19T10:30:00",
            }
        }


class SalaryRange(BaseModel):
    """Salary data for a role at a company."""

    role_title: str
    company: str
    location: Optional[str] = None
    p25: int
    p50: int
    p75: int
    equity_estimate: Optional[str] = None
    data_source: str
    opt_eligible_signal: bool = False

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "role_title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "location": "San Francisco, CA",
                "p25": 180000,
                "p50": 210000,
                "p75": 250000,
                "equity_estimate": "0.1% - 0.3%",
                "data_source": "levels.fyi",
                "opt_eligible_signal": True,
            }
        }
