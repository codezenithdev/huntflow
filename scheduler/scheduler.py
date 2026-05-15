"""HuntFlow Scheduler — daily discovery, outreach, digest, stale app checks."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from cli import run_daily, run_outreach, digest
from tools.sqlite_tracker import DatabaseManager
from tools.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)
notifier = TelegramNotifier()


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""

    def do_get(self) -> None:
        """Return health status."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: any) -> None:
        """Suppress HTTP logging."""
        pass


def start_health_check_server(port: int = 8080) -> None:
    """Start HTTP health check server on separate thread."""
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    thread = Thread(daemon=True, target=server.serve_forever)
    thread.start()
    logger.info(f"Health check server started on port {port}")


def job_wrapper(job_name: str, job_func: callable) -> callable:
    """Wrap job with logging, error handling, and Telegram alerts."""

    def wrapper() -> None:
        start = datetime.now()
        try:
            logger.info(f"Starting job: {job_name}")
            job_func()
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Job {job_name} completed in {duration:.1f}s")
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            logger.error(f"Job {job_name} failed after {duration:.1f}s: {e}", exc_info=True)
            notifier.send(f"[bold red]HuntFlow Job Failed[/bold red]\n{job_name}\n{str(e)}")

    return wrapper


def check_stale_applications() -> None:
    """Flag stale applications and send reminders."""
    try:
        db = DatabaseManager()
        stale = db.get_stale_applications(days=5)
        if stale:
            logger.info(f"Found {len(stale)} stale applications")
            notifier.send(f"[bold yellow]Stale Applications: {len(stale)}[/bold yellow]")
    except Exception as e:
        logger.error(f"Stale app check failed: {e}")


def create_scheduler(once: bool = False, job_name: str | None = None) -> BlockingScheduler | BackgroundScheduler:
    """Create and configure APScheduler."""
    scheduler_class = BlockingScheduler if not once else BackgroundScheduler
    scheduler = scheduler_class(timezone="America/Chicago")

    # Define jobs
    jobs = {
        "daily": (job_wrapper("daily_discovery", run_daily), CronTrigger(hour=8, minute=0)),
        "digest": (job_wrapper("digest", digest), CronTrigger(hour=18, minute=0)),
        "outreach": (job_wrapper("outreach", run_outreach), CronTrigger(hour=9, minute=0, day_of_week="0,2,4")),
        "stale": (job_wrapper("stale_check", check_stale_applications), CronTrigger(minute=0)),
    }

    if once:
        # Run single job once
        if not job_name or job_name not in jobs:
            raise ValueError(f"Invalid job: {job_name}. Valid: {', '.join(jobs.keys())}")
        job_func, _ = jobs[job_name]
        logger.info(f"Running job once: {job_name}")
        job_func()
        return scheduler

    # Schedule all jobs
    for job_id, (job_func, trigger) in jobs.items():
        scheduler.add_job(job_func, trigger, id=job_id, replace_existing=True)
        logger.info(f"Scheduled job: {job_id}")

    return scheduler


def main() -> None:
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="HuntFlow Scheduler")
    parser.add_argument("--once", action="store_true", help="Run job once and exit")
    parser.add_argument("--job", default="daily", choices=["daily", "digest", "outreach", "stale"], help="Job to run")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/scheduler.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger.info("HuntFlow Scheduler starting...")

    # Start health check server (unless --once)
    if not args.once:
        start_health_check_server(8080)

    # Create and start scheduler
    scheduler = create_scheduler(once=args.once, job_name=args.job)

    if args.once:
        logger.info(f"Job {args.job} completed. Exiting.")
        sys.exit(0)

    # Graceful shutdown handlers
    def shutdown(signum: int, frame: any) -> None:
        logger.info("Shutdown signal received, stopping scheduler...")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        logger.info("Scheduler starting (blocking mode)...")
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
