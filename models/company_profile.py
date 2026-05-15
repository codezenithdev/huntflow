"""Company profile model for storing company research and insights."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """Research profile for a company with hiring intel."""

    company_name: str
    website: Optional[str] = None
    funding_stage: Optional[str] = None
    team_size: Optional[str] = None
    tech_stack: List[str] = []
    glassdoor_rating: Optional[float] = None
    founded_year: Optional[int] = None
    hq_location: Optional[str] = None
    red_flags: List[str] = []
    green_flags: List[str] = []
    visa_sponsorship: Optional[bool] = None
    is_remote_friendly: Optional[bool] = None
    notes: Optional[str] = None
    researched_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "company_name": "Acme Corp",
                "website": "https://acme.com",
                "funding_stage": "Series B",
                "team_size": "50-100",
                "tech_stack": ["Python", "AWS", "React"],
                "glassdoor_rating": 4.2,
                "founded_year": 2018,
                "hq_location": "San Francisco, CA",
                "red_flags": ["High turnover in eng"],
                "green_flags": ["Great work-life balance", "Competitive equity"],
                "visa_sponsorship": True,
                "is_remote_friendly": True,
            }
        }
