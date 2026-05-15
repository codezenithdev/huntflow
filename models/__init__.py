"""Data models for HuntFlow."""
from models.application import Application, SalaryRange
from models.ats_report import ATSReport
from models.company_profile import CompanyProfile
from models.job_listing import JobListing

__all__ = [
    "JobListing",
    "ATSReport",
    "CompanyProfile",
    "Application",
    "SalaryRange",
]
