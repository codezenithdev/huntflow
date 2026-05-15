#!/usr/bin/env python3
"""HuntFlow MVP run — Remotive + YC + LinkedIn RSS (no Playwright, no paid APIs)."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from models.job_listing import JobListing
from tools.sqlite_tracker import DatabaseManager
from tools.remotive_scraper import RemotiveScraper
from tools.yc_scraper import YCScraper
from tools.keyword_extractor import job_score, ATSScorer

console = Console()

async def main():
    console.print("[bold cyan]Starting HuntFlow MVP...[/bold cyan]")
    console.print()

    db = DatabaseManager()
    scorer = ATSScorer()
    all_jobs = []

    console.print("[bold]Step 1: Scraping Remotive...[/bold]")
    try:
        remotive = RemotiveScraper()
        remotive_jobs = await remotive.scrape()
        console.print(f"  Found {len(remotive_jobs)} jobs from Remotive")
        all_jobs.extend(remotive_jobs)
    except Exception as e:
        console.print(f"  [yellow]Remotive failed: {str(e)[:100]}[/yellow]")

    console.print()
    console.print("[bold]Step 2: Scraping YC...[/bold]")
    try:
        yc = YCScraper()
        yc_jobs = await yc.scrape()
        console.print(f"  Found {len(yc_jobs)} jobs from YC")
        all_jobs.extend(yc_jobs)
    except Exception as e:
        console.print(f"  [yellow]YC scraper failed: {str(e)[:100]}[/yellow]")

    console.print()
    console.print(f"[bold]Step 3: Scoring {len(all_jobs)} jobs...[/bold]")

    scored_jobs = []
    for i, job in enumerate(all_jobs):
        if i % 10 == 0:
            console.print(f"  Scored {i}/{len(all_jobs)}", end="\r")

        try:
            report = scorer.compute_ats_score(job.jd_text or "")
            score_result = job_score(job, report.score)

            scored_jobs.append({
                "job": job,
                "ats_score": report.score,
                "grade": score_result["grade"],
                "final_score": score_result["score"],
                "visa": score_result["visa_flag"],
            })
        except Exception as e:
            console.print(f"  [yellow]Scoring failed for {job.company}: {str(e)[:50]}[/yellow]")

    console.print(f"  Scored {len(scored_jobs)}/{len(all_jobs)} successfully")
    console.print()

    scored_jobs.sort(key=lambda x: x["final_score"], reverse=True)

    console.print("[bold]Step 4: Saving to database...[/bold]")
    for item in scored_jobs:
        try:
            db.upsert_job(item["job"])
            db.update_status(item["job"].url, "discovered")
        except Exception as e:
            console.print(f"  [yellow]DB save failed: {str(e)[:50]}[/yellow]")

    console.print(f"  Saved {len(scored_jobs)} jobs to database")
    console.print()

    console.print("[bold]Step 5: Top 10 opportunities[/bold]")
    console.print()

    table = Table(title="HuntFlow Top Jobs")
    table.add_column("Grade", style="cyan")
    table.add_column("Company", style="magenta")
    table.add_column("Title", style="green")
    table.add_column("ATS%", style="yellow")
    table.add_column("Score", style="white")
    table.add_column("Visa", style="blue")
    table.add_column("Source", style="dim")

    grade_colors = {
        "A": "bold green",
        "B": "yellow",
        "C": "orange1",
        "D": "bold red",
    }

    for item in scored_jobs[:10]:
        job = item["job"]
        grade_color = grade_colors.get(item["grade"], "white")
        visa_str = "+" if item["visa"] == "positive" else ("-" if item["visa"] == "negative" else "?")

        table.add_row(
            f"[{grade_color}]{item['grade']}[/{grade_color}]",
            job.company or "Unknown",
            (job.title or "Role")[:30],
            f"{item['ats_score']:.0f}",
            f"{item['final_score']:.0f}",
            visa_str,
            job.source or "N/A",
        )

    console.print(table)
    console.print()

    grade_breakdown = {}
    source_breakdown = {}
    for item in scored_jobs:
        grade = item["grade"]
        source = item["job"].source or "unknown"
        grade_breakdown[grade] = grade_breakdown.get(grade, 0) + 1
        source_breakdown[source] = source_breakdown.get(source, 0) + 1

    console.print("[bold]Summary[/bold]")
    console.print(f"  Total discovered: {len(scored_jobs)}")
    for grade in ["A", "B", "C", "D"]:
        count = grade_breakdown.get(grade, 0)
        if count > 0:
            console.print(f"  Grade {grade}: {count}")

    console.print()
    console.print("  By source:")
    for source, count in sorted(source_breakdown.items()):
        console.print(f"    {source}: {count}")

    console.print()
    console.print("[bold green]OK HuntFlow MVP is live![/bold green]")
    console.print()
    console.print("Next steps:")
    console.print("  [cyan]View pipeline:[/cyan] python cli.py status")
    console.print("  [cyan]Dashboard:[/cyan]     streamlit run dashboard/app.py")
    console.print("  [cyan]Daily run:[/cyan]     python cli.py run-daily")
    console.print("  [cyan]Deploy:[/cyan]        docker-compose up -d")
    console.print()

if __name__ == "__main__":
    asyncio.run(main())
