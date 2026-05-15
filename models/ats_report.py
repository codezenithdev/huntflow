"""ATS report model for resume scoring and keyword analysis."""
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class ATSReport(BaseModel):
    """ATS compatibility report for a resume against a job posting."""

    job_id: str
    job_url: str
    resume_variant: str
    score: int
    missing_keywords: List[str] = []
    present_keywords: List[str] = []
    suggestions: List[str] = []
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_url": "https://example.com/jobs/123",
                "resume_variant": "generic",
                "score": 78,
                "missing_keywords": ["Kubernetes", "microservices", "DDD"],
                "present_keywords": ["Python", "AWS", "Docker"],
                "suggestions": [
                    "Add Kubernetes experience to highlight DevOps skills",
                    "Emphasize distributed systems work",
                ],
            }
        }
