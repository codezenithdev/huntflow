"""SQLite database layer for job tracking and application management."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Float,
    JSON,
    Index,
    UniqueConstraint,
    create_engine,
    select,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, Session
import structlog

from models import JobListing, Application, CompanyProfile, ATSReport

logger = structlog.get_logger()
Base = declarative_base()


class JobListingDB(Base):
    """SQLAlchemy ORM model for job listings."""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    jd_text = Column(String, nullable=False)
    source = Column(String, nullable=False)
    posted_at = Column(String)
    location = Column(String)
    salary_range = Column(String)
    is_remote = Column(Boolean, default=False)
    requires_sponsorship = Column(Boolean)
    employment_type = Column(String)
    seniority = Column(String)
    ats_score = Column(Integer)
    job_score = Column(Integer, index=True)
    job_grade = Column(String)
    visa_flag = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_duplicate = Column(Boolean, default=False)

    def to_pydantic(self) -> JobListing:
        """Convert ORM to Pydantic model."""
        return JobListing(
            id=self.id,
            title=self.title,
            company=self.company,
            url=self.url,
            jd_text=self.jd_text,
            source=self.source,
            posted_at=self.posted_at,
            location=self.location,
            salary_range=self.salary_range,
            is_remote=self.is_remote,
            requires_sponsorship=self.requires_sponsorship,
            employment_type=self.employment_type,
            seniority=self.seniority,
            ats_score=self.ats_score,
            job_score=self.job_score,
            job_grade=self.job_grade,
            visa_flag=self.visa_flag,
            created_at=self.created_at,
            is_duplicate=self.is_duplicate,
        )


class ApplicationDB(Base):
    """SQLAlchemy ORM model for job applications."""

    __tablename__ = "applications"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    applied_at = Column(DateTime)
    outreach_sent_at = Column(DateTime)
    last_activity_at = Column(DateTime, default=datetime.utcnow, index=True)
    follow_up_due_at = Column(DateTime)
    notes = Column(String)
    resume_variant = Column(String)
    ats_score = Column(Integer)
    job_score = Column(Integer)
    cover_letter_path = Column(String)
    outreach_email_path = Column(String)
    salary_offered = Column(String)
    rejection_reason = Column(String)

    def to_pydantic(self) -> Application:
        """Convert ORM to Pydantic model."""
        return Application(
            id=self.id,
            job_id=self.job_id,
            company=self.company,
            title=self.title,
            url=self.url,
            status=self.status,
            source=self.source,
            applied_at=self.applied_at,
            outreach_sent_at=self.outreach_sent_at,
            last_activity_at=self.last_activity_at,
            follow_up_due_at=self.follow_up_due_at,
            notes=self.notes,
            resume_variant=self.resume_variant,
            ats_score=self.ats_score,
            job_score=self.job_score,
            cover_letter_path=self.cover_letter_path,
            outreach_email_path=self.outreach_email_path,
            salary_offered=self.salary_offered,
            rejection_reason=self.rejection_reason,
        )


class CompanyProfileDB(Base):
    """SQLAlchemy ORM model for company profiles."""

    __tablename__ = "companies"

    company_name = Column(String, primary_key=True, unique=True, index=True)
    website = Column(String)
    funding_stage = Column(String)
    team_size = Column(String)
    tech_stack = Column(JSON, default=[])
    glassdoor_rating = Column(Float)
    founded_year = Column(Integer)
    hq_location = Column(String)
    red_flags = Column(JSON, default=[])
    green_flags = Column(JSON, default=[])
    visa_sponsorship = Column(Boolean)
    is_remote_friendly = Column(Boolean)
    notes = Column(String)
    researched_at = Column(DateTime, default=datetime.utcnow)

    def to_pydantic(self) -> CompanyProfile:
        """Convert ORM to Pydantic model."""
        return CompanyProfile(
            company_name=self.company_name,
            website=self.website,
            funding_stage=self.funding_stage,
            team_size=self.team_size,
            tech_stack=self.tech_stack or [],
            glassdoor_rating=self.glassdoor_rating,
            founded_year=self.founded_year,
            hq_location=self.hq_location,
            red_flags=self.red_flags or [],
            green_flags=self.green_flags or [],
            visa_sponsorship=self.visa_sponsorship,
            is_remote_friendly=self.is_remote_friendly,
            notes=self.notes,
            researched_at=self.researched_at,
        )


class ATSReportDB(Base):
    """SQLAlchemy ORM model for ATS reports."""

    __tablename__ = "ats_reports"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False)
    job_url = Column(String, nullable=False, index=True)
    resume_variant = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    missing_keywords = Column(JSON, default=[])
    present_keywords = Column(JSON, default=[])
    suggestions = Column(JSON, default=[])
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    def to_pydantic(self) -> ATSReport:
        """Convert ORM to Pydantic model."""
        return ATSReport(
            job_id=self.job_id,
            job_url=self.job_url,
            resume_variant=self.resume_variant,
            score=self.score,
            missing_keywords=self.missing_keywords or [],
            present_keywords=self.present_keywords or [],
            suggestions=self.suggestions or [],
            analyzed_at=self.analyzed_at,
        )


class DatabaseManager:
    """Manages SQLite database operations for HuntFlow."""

    def __init__(self, db_path: str = "./data/huntflow.db"):
        """Initialize database with WAL mode."""
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._enable_wal_mode()
        logger.info("database_initialized", path=db_path)

    def _enable_wal_mode(self):
        """Enable WAL (Write-Ahead Logging) mode for better concurrency."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

    # ============ Jobs ============

    def upsert_job(self, job: JobListing) -> bool:
        """Upsert a job listing. Returns True if NEW job, False if duplicate."""
        with Session(self.engine) as session:
            existing = session.query(JobListingDB).filter_by(url=job.url).first()
            if existing:
                logger.debug("job_duplicate", url=job.url)
                return False

            db_job = JobListingDB(
                id=job.id,
                title=job.title,
                company=job.company,
                url=job.url,
                jd_text=job.jd_text,
                source=job.source,
                posted_at=job.posted_at,
                location=job.location,
                salary_range=job.salary_range,
                is_remote=job.is_remote,
                requires_sponsorship=job.requires_sponsorship,
                employment_type=job.employment_type,
                seniority=job.seniority,
                ats_score=job.ats_score,
                job_score=job.job_score,
                job_grade=job.job_grade,
                visa_flag=job.visa_flag,
                created_at=job.created_at,
                is_duplicate=job.is_duplicate,
            )
            session.add(db_job)
            session.commit()
            logger.info("job_created", title=job.title, company=job.company)
            return True

    def get_job_by_url(self, url: str) -> Optional[JobListing]:
        """Get a job by URL."""
        with Session(self.engine) as session:
            result = session.query(JobListingDB).filter_by(url=url).first()
            if result:
                return result.to_pydantic()
            return None

    def get_jobs(
        self, min_score: int = 0, grade: Optional[str] = None, source: Optional[str] = None, limit: int = 100
    ) -> List[JobListing]:
        """Get filtered jobs."""
        with Session(self.engine) as session:
            query = session.query(JobListingDB)

            if min_score > 0:
                query = query.filter(JobListingDB.job_score >= min_score)
            if grade:
                query = query.filter(JobListingDB.job_grade == grade)
            if source:
                query = query.filter(JobListingDB.source == source)

            results = query.order_by(JobListingDB.created_at.desc()).limit(limit).all()
            return [job.to_pydantic() for job in results]

    def get_new_jobs_today(self) -> List[JobListing]:
        """Get jobs created today."""
        now = datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with Session(self.engine) as session:
            results = (
                session.query(JobListingDB)
                .filter(JobListingDB.created_at >= start_of_day)
                .order_by(JobListingDB.created_at.desc())
                .all()
            )
            return [job.to_pydantic() for job in results]

    def count_jobs_by_source(self) -> Dict[str, int]:
        """Get count of jobs by source."""
        with Session(self.engine) as session:
            results = (
                session.query(JobListingDB.source, func.count(JobListingDB.id).label("count"))
                .group_by(JobListingDB.source)
                .all()
            )
            return {source: count for source, count in results}

    # ============ Applications ============

    def upsert_application(self, app: Application) -> bool:
        """Upsert an application. Returns True if NEW, False if duplicate."""
        with Session(self.engine) as session:
            existing = session.query(ApplicationDB).filter_by(url=app.url).first()
            if existing:
                logger.debug("application_duplicate", url=app.url)
                return False

            db_app = ApplicationDB(
                id=app.id,
                job_id=app.job_id,
                company=app.company,
                title=app.title,
                url=app.url,
                status=app.status,
                source=app.source,
                applied_at=app.applied_at,
                outreach_sent_at=app.outreach_sent_at,
                last_activity_at=app.last_activity_at,
                follow_up_due_at=app.follow_up_due_at,
                notes=app.notes,
                resume_variant=app.resume_variant,
                ats_score=app.ats_score,
                job_score=app.job_score,
                cover_letter_path=app.cover_letter_path,
                outreach_email_path=app.outreach_email_path,
                salary_offered=app.salary_offered,
                rejection_reason=app.rejection_reason,
            )
            session.add(db_app)
            session.commit()
            logger.info("application_created", title=app.title, company=app.company, status=app.status)
            return True

    def update_status(self, job_url: str, new_status: str, notes: Optional[str] = None):
        """Update application status by job URL."""
        with Session(self.engine) as session:
            app = session.query(ApplicationDB).filter_by(url=job_url).first()
            if app:
                app.status = new_status
                app.last_activity_at = datetime.utcnow()
                if notes:
                    app.notes = notes
                session.commit()
                logger.info("application_status_updated", url=job_url, status=new_status)
            else:
                logger.warning("application_not_found", url=job_url)

    def get_stale_applications(self, days: int = 5) -> List[Application]:
        """Get applications with no recent activity."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with Session(self.engine) as session:
            results = (
                session.query(ApplicationDB)
                .filter(ApplicationDB.last_activity_at < cutoff)
                .filter(ApplicationDB.status.in_(["discovered", "applied", "outreach_sent"]))
                .order_by(ApplicationDB.last_activity_at)
                .all()
            )
            return [app.to_pydantic() for app in results]

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get application pipeline statistics."""
        with Session(self.engine) as session:
            # Counts by status
            status_counts = (
                session.query(ApplicationDB.status, func.count(ApplicationDB.id).label("count"))
                .group_by(ApplicationDB.status)
                .all()
            )

            # Average ATS score
            avg_ats = session.query(func.avg(ApplicationDB.ats_score)).scalar() or 0

            # Top sources
            sources = (
                session.query(ApplicationDB.source, func.count(ApplicationDB.id).label("count"))
                .group_by(ApplicationDB.source)
                .order_by(func.count(ApplicationDB.id).desc())
                .limit(5)
                .all()
            )

            return {
                "by_status": {status: count for status, count in status_counts},
                "avg_ats_score": round(avg_ats, 1),
                "top_sources": {source: count for source, count in sources},
            }

    # ============ Companies ============

    def upsert_company(self, profile: CompanyProfile):
        """Upsert a company profile."""
        with Session(self.engine) as session:
            existing = session.query(CompanyProfileDB).filter_by(company_name=profile.company_name).first()

            if existing:
                existing.website = profile.website
                existing.funding_stage = profile.funding_stage
                existing.team_size = profile.team_size
                existing.tech_stack = profile.tech_stack
                existing.glassdoor_rating = profile.glassdoor_rating
                existing.founded_year = profile.founded_year
                existing.hq_location = profile.hq_location
                existing.red_flags = profile.red_flags
                existing.green_flags = profile.green_flags
                existing.visa_sponsorship = profile.visa_sponsorship
                existing.is_remote_friendly = profile.is_remote_friendly
                existing.notes = profile.notes
                existing.researched_at = profile.researched_at
            else:
                db_company = CompanyProfileDB(
                    company_name=profile.company_name,
                    website=profile.website,
                    funding_stage=profile.funding_stage,
                    team_size=profile.team_size,
                    tech_stack=profile.tech_stack,
                    glassdoor_rating=profile.glassdoor_rating,
                    founded_year=profile.founded_year,
                    hq_location=profile.hq_location,
                    red_flags=profile.red_flags,
                    green_flags=profile.green_flags,
                    visa_sponsorship=profile.visa_sponsorship,
                    is_remote_friendly=profile.is_remote_friendly,
                    notes=profile.notes,
                    researched_at=profile.researched_at,
                )
                session.add(db_company)

            session.commit()
            logger.info("company_upserted", name=profile.company_name)

    def get_company(self, name: str) -> Optional[CompanyProfile]:
        """Get company profile by name."""
        with Session(self.engine) as session:
            result = session.query(CompanyProfileDB).filter_by(company_name=name).first()
            if result:
                return result.to_pydantic()
            return None

    # ============ ATS Reports ============

    def save_ats_report(self, report: ATSReport):
        """Save an ATS report."""
        with Session(self.engine) as session:
            db_report = ATSReportDB(
                id=f"{report.job_id}_{report.resume_variant}",
                job_id=report.job_id,
                job_url=report.job_url,
                resume_variant=report.resume_variant,
                score=report.score,
                missing_keywords=report.missing_keywords,
                present_keywords=report.present_keywords,
                suggestions=report.suggestions,
                analyzed_at=report.analyzed_at,
            )
            session.merge(db_report)
            session.commit()
            logger.info("ats_report_saved", job_url=report.job_url, score=report.score)

    def get_ats_report(self, job_url: str, resume_variant: str = "generic") -> Optional[ATSReport]:
        """Get ATS report for a job."""
        with Session(self.engine) as session:
            # Try to find by job_url and resume_variant
            result = (
                session.query(ATSReportDB)
                .filter_by(job_url=job_url, resume_variant=resume_variant)
                .order_by(ATSReportDB.analyzed_at.desc())
                .first()
            )
            if result:
                return result.to_pydantic()
            return None

    # ============ Analytics ============

    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily statistics for the past N days."""
        stats = []
        for i in range(days, 0, -1):
            day = datetime.utcnow() - timedelta(days=i)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

            with Session(self.engine) as session:
                discovered = session.query(func.count(JobListingDB.id)).filter(
                    JobListingDB.created_at >= start, JobListingDB.created_at < end
                ).scalar() or 0

                applied = session.query(func.count(ApplicationDB.id)).filter(
                    ApplicationDB.applied_at >= start, ApplicationDB.applied_at < end
                ).scalar() or 0

                grade_a = session.query(func.count(JobListingDB.id)).filter(
                    JobListingDB.created_at >= start,
                    JobListingDB.created_at < end,
                    JobListingDB.job_grade == "A",
                ).scalar() or 0

                stats.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "discovered": discovered,
                    "applied": applied,
                    "grade_a": grade_a,
                })

        return stats


class SQLiteTrackerTool:
    """CrewAI tool for tracking job applications."""

    name: str = "ApplicationTracker"
    description: str = (
        "Track job applications and get statistics. "
        "Actions: get_stats, get_stale, update_status, get_new_jobs, count_by_source"
    )

    def __init__(self, db_path: str = "./data/huntflow.db"):
        """Initialize the tracker tool."""
        self.db = DatabaseManager(db_path)

    def _run(self, action: str, params: str = "{}") -> str:
        """Execute tracker actions."""
        try:
            params_dict = json.loads(params) if params else {}

            if action == "get_stats":
                stats = self.db.get_pipeline_stats()
                return json.dumps(stats, indent=2)

            elif action == "get_stale":
                days = params_dict.get("days", 5)
                apps = self.db.get_stale_applications(days)
                return json.dumps([app.model_dump(mode="json") for app in apps], indent=2)

            elif action == "update_status":
                url = params_dict.get("url")
                status = params_dict.get("status")
                notes = params_dict.get("notes")
                self.db.update_status(url, status, notes)
                return f"Updated {url} to {status}"

            elif action == "get_new_jobs":
                jobs = self.db.get_new_jobs_today()
                return json.dumps([job.model_dump(mode="json") for job in jobs], indent=2)

            elif action == "count_by_source":
                counts = self.db.count_jobs_by_source()
                return json.dumps(counts, indent=2)

            else:
                return f"Unknown action: {action}"

        except Exception as e:
            logger.error("tracker_tool_error", action=action, error=str(e))
            return f"Error: {str(e)}"


if __name__ == "__main__":
    # Test database layer
    db = DatabaseManager("./data/test.db")

    # Test job upsert
    job = JobListing(
        title="Backend Engineer",
        company="TestCo",
        url="https://test.com/1",
        jd_text="Java Spring Boot AWS",
        source="test",
    )
    assert db.upsert_job(job) == True  # new
    assert db.upsert_job(job) == False  # duplicate
    assert db.get_job_by_url("https://test.com/1").company == "TestCo"

    # Test application
    app = Application(
        job_id=job.id,
        company="TestCo",
        title="Backend Engineer",
        url="https://test.com/1",
        status="discovered",
        source="test",
    )
    assert db.upsert_application(app) == True  # new
    assert db.upsert_application(app) == False  # duplicate

    # Test status update
    db.update_status("https://test.com/1", "applied", "Applied via HuntFlow")

    # Test pipeline stats
    stats = db.get_pipeline_stats()
    assert "by_status" in stats

    # Test company profile
    company = CompanyProfile(
        company_name="TestCo",
        funding_stage="Series A",
        visa_sponsorship=True,
    )
    db.upsert_company(company)
    assert db.get_company("TestCo").company_name == "TestCo"

    # Test ATS report
    ats = ATSReport(
        job_id=job.id,
        job_url=job.url,
        resume_variant="generic",
        score=85,
        missing_keywords=["Kubernetes"],
    )
    db.save_ats_report(ats)
    assert db.get_ats_report(job.url).score == 85

    # Cleanup
    print("All database tests passed!")
    import shutil
    shutil.rmtree("./data", ignore_errors=True)
