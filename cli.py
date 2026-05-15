"""HuntFlow CLI — job discovery, outreach, interview prep, pipeline management."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from structlog import get_logger

from crews import (
    create_daily_discovery_crew,
    create_digest_crew,
    create_interview_prep_crew,
    create_outreach_crew,
)
from tools.sqlite_tracker import DatabaseManager
from tools.telegram_notifier import TelegramNotifier

logger = get_logger(__name__)
console = Console()


# Actual job implementations (no Click decorators — these are callable from scheduler.py)
def run_daily() -> None:
    """Run full daily discovery + scoring + digest."""
    console.print("[bold cyan]Starting daily discovery crew...[/bold cyan]")
    try:
        crew = create_daily_discovery_crew()
        result = crew.kickoff()
        console.print("[bold green]Daily discovery completed[/bold green]")
        if result:
            console.print(f"\n{result}")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("daily_discovery_failed", error=str(e))
        raise


def run_outreach() -> None:
    """Draft outreach emails for top A-grade jobs."""
    console.print("[bold cyan]Starting outreach crew...[/bold cyan]")
    try:
        crew = create_outreach_crew()
        result = crew.kickoff()
        console.print("[bold green]Outreach crew completed[/bold green]")
        if result:
            console.print(f"\n{result}")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("outreach_failed", error=str(e))
        raise


def digest() -> None:
    """Send Telegram digest now."""
    console.print("[bold cyan]Sending digest...[/bold cyan]")
    try:
        crew = create_digest_crew()
        result = crew.kickoff()
        console.print("[bold green]Digest sent[/bold green]")
        if result:
            console.print(f"\n{result}")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("digest_failed", error=str(e))
        raise


def prep_impl(company: str, title: str) -> None:
    """Generate interview prep for COMPANY + TITLE."""
    console.print(f"[bold cyan]Generating interview prep for {company} — {title}...[/bold cyan]")
    try:
        crew = create_interview_prep_crew(company, title)
        result = crew.kickoff()
        console.print("[bold green]Interview prep completed[/bold green]")
        if result:
            console.print(f"\n{result}")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("interview_prep_failed", error=str(e), company=company, title=title)
        raise


def status_impl() -> None:
    """Show pipeline stats in terminal."""
    try:
        db = DatabaseManager()
        stats = db.get_daily_stats()

        table = Table(title="[bold]HuntFlow Pipeline Status[/bold]")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        pipeline = stats.get("pipeline_status", {})
        table.add_row("Discovered", str(pipeline.get("discovered", 0)))
        table.add_row("Applied", str(pipeline.get("applied", 0)))
        table.add_row("Replied", str(pipeline.get("replied", 0)))
        table.add_row("Interviewing", str(pipeline.get("interviewing", 0)))
        table.add_row("Offer", str(pipeline.get("offer", 0)))

        grades = stats.get("grade_distribution", {})
        for grade, count in grades.items():
            table.add_row(f"Grade {grade}", str(count))

        sources = stats.get("by_source", {})
        for source, count in sources.items():
            table.add_row(f"Source: {source}", str(count))

        table.add_row("Avg ATS Score", f"{stats.get('avg_ats_score', 0):.0f}%")
        table.add_row("Reply Rate", f"{stats.get('reply_rate', 0):.1f}%")

        console.print(table)

        last_run = stats.get("last_run_time")
        if last_run:
            console.print(f"\n[dim]Last run: {last_run}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("status_failed", error=str(e))


def jobs_impl(grade: Optional[str] = None, source: Optional[str] = None, limit: int = 20) -> None:
    """List jobs with optional filters."""
    try:
        db = DatabaseManager()
        jobs_list = db.get_jobs(limit=limit)

        if grade:
            jobs_list = [j for j in jobs_list if j.grade == grade]

        if source:
            jobs_list = [j for j in jobs_list if j.source == source]

        table = Table(title=f"[bold]HuntFlow Jobs (top {limit})[/bold]")
        table.add_column("Grade", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Title", style="green")
        table.add_column("ATS", style="yellow")
        table.add_column("Source", style="blue")

        for job in jobs_list:
            grade_style = {"A+": "bold green", "A": "green", "B+": "yellow", "B": "yellow", "C+": "red", "C": "red", "D": "bold red"}.get(job.grade, "white")
            table.add_row(f"[{grade_style}]{job.grade}[/{grade_style}]", job.company or "Unknown", job.title or "Role", f"{job.score}%", job.source or "N/A")

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("jobs_list_failed", error=str(e))


def test_telegram_impl() -> None:
    """Verify Telegram bot connection."""
    console.print("[bold cyan]Testing Telegram connection...[/bold cyan]")
    try:
        notifier = TelegramNotifier()
        success = notifier.test_connection()
        if success:
            console.print("[bold green]Telegram connection successful![/bold green]")
        else:
            console.print("[bold red]Telegram connection failed[/bold red]")
            console.print("[yellow]Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("telegram_test_failed", error=str(e))


def update_impl(url: str, status_name: str) -> None:
    """Update application status. Valid: applied, outreach_sent, replied, interviewing, offer, rejected"""
    valid_statuses = ["applied", "outreach_sent", "replied", "interviewing", "offer", "rejected"]

    if status_name not in valid_statuses:
        console.print(f"[bold red]Invalid status: {status_name}[/bold red]\n[yellow]Valid: {', '.join(valid_statuses)}[/yellow]")
        return

    console.print(f"[bold cyan]Updating {url} → {status_name}...[/bold cyan]")
    try:
        db = DatabaseManager()
        db.update_status(url, status_name)
        console.print("[bold green]Status updated[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.error("update_status_failed", error=str(e), url=url, status=status_name)


# Click CLI group
@click.group()
def cli() -> None:
    """HuntFlow — AI Job Hunting Automation."""
    pass


# Click commands (wrappers around implementation functions)
@cli.command()
def daily_cli() -> None:
    """Run full daily discovery + scoring + digest."""
    run_daily()


@cli.command()
def outreach_cli() -> None:
    """Draft outreach emails for top A-grade jobs."""
    run_outreach()


@cli.command()
@click.argument("company")
@click.argument("title")
def prep(company: str, title: str) -> None:
    """Generate interview prep for COMPANY + TITLE."""
    prep_impl(company, title)


@cli.command()
def digest_cli() -> None:
    """Send Telegram digest now."""
    digest()


@cli.command()
def status() -> None:
    """Show pipeline stats in terminal."""
    status_impl()


@cli.command()
@click.option("--grade", default=None, help="Filter by grade (A+, A, B+, B, C+, C, D)")
@click.option("--source", default=None, help="Filter by source (ashby, wellfound, yc, etc.)")
@click.option("--limit", default=20, help="Max jobs to show")
def jobs(grade: Optional[str], source: Optional[str], limit: int) -> None:
    """List jobs with optional filters."""
    jobs_impl(grade, source, limit)


@cli.command()
def test_telegram() -> None:
    """Verify Telegram bot connection."""
    test_telegram_impl()


@cli.command()
@click.argument("url")
@click.argument("status_name")
def update(url: str, status_name: str) -> None:
    """Update application status. Valid: applied, outreach_sent, replied, interviewing, offer, rejected"""
    update_impl(url, status_name)


if __name__ == "__main__":
    cli()
