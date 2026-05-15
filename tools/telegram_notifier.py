"""Telegram notification system for HuntFlow alerts and digests."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send formatted messages to Telegram."""

    def __init__(self) -> None:
        """Load token + chat_id from env. Set self.enabled flag."""
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.enabled = bool(self.token and self.chat_id)
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        if not self.enabled:
            logger.warning(
                "Telegram disabled: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
            )

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram.

        Args:
            text: Message content (truncated to 4096 chars)
            parse_mode: "HTML" or "Markdown"

        Returns:
            True if sent successfully, False otherwise.

        Setup instructions:
        1. Message @BotFather → /newbot → copy token
        2. Message your bot once
        3. GET https://api.telegram.org/bot{TOKEN}/getUpdates → copy chat_id
        4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
        """
        if not self.enabled:
            logger.debug("Telegram disabled, skipping send")
            return False

        # Truncate to Telegram's 4096-char limit
        text = text[: 4096]

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.api_url,
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
                )
                response.raise_for_status()
                logger.info("Telegram message sent successfully")
                return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_digest(
        self,
        stats: dict[str, Any],
        top_jobs: list[dict[str, Any]],
        stale: list[dict[str, Any]],
        insight: str = "",
    ) -> bool:
        """
        Send formatted daily digest to Telegram.

        Args:
            stats: Dict with keys: new_count, applied, replied, interviewing, offer,
                   a_count, b_count, best_source
            top_jobs: List of top 3 jobs (title, company, score, grade, url)
            stale: List of stale applications (company, days_stale)
            insight: One tactical insight (e.g., "Remotive had 5 visa roles today")

        Returns:
            True if sent successfully, False otherwise.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        new_count = stats.get("new_count", 0)
        applied = stats.get("applied", 0)
        replied = stats.get("replied", 0)
        interviewing = stats.get("interviewing", 0)
        offer = stats.get("offer", 0)
        a_count = stats.get("a_count", 0)
        b_count = stats.get("b_count", 0)
        best_source = stats.get("best_source", "N/A")

        # Build top jobs section
        top_jobs_text = ""
        for job in top_jobs[:3]:
            grade = job.get("grade", "?")
            emoji = self._grade_emoji(grade)
            company = job.get("company", "Unknown")
            title = job.get("title", "Role")
            score = job.get("score", 0)
            url = job.get("url", "#")
            top_jobs_text += (
                f"{emoji} <b>{company}</b> — {title}\n"
                f"   ATS: {score}% | Grade: {grade} | "
                f"<a href='{url}'>View</a>\n"
            )

        # Build follow-up section
        followup_text = ""
        for app in stale[:5]:
            company = app.get("company", "Unknown")
            days = app.get("days_stale", 0)
            followup_text += f"• {company} — {days} days no response\n"

        # Assemble digest
        digest = (
            f"🎯 <b>HuntFlow Daily — {date_str}</b>\n\n"
            f"🔥 <b>Top Jobs ({new_count} new):</b>\n"
            f"{top_jobs_text}\n"
            f"📊 <b>Pipeline:</b>\n"
            f"Applied: {applied} | Replied: {replied} | Interviewing: {interviewing} | Offer: {offer}\n\n"
        )

        if stale:
            digest += f"⏰ <b>Follow-up ({len(stale)}):</b>\n{followup_text}\n"

        digest += (
            f"📈 Found: {new_count} | A: {a_count} | B: {b_count} | "
            f"Source: {best_source}\n"
        )

        if insight:
            digest += f"💡 {insight}\n"

        digest += "<i>HuntFlow 🤖</i>"

        return self.send(digest)

    def send_alert(self, job: dict[str, Any]) -> bool:
        """
        Send immediate alert for A-grade + visa-positive jobs.

        Args:
            job: Dict with company, title, score, grade, url, visa_positive

        Returns:
            True if sent successfully, False otherwise.
        """
        company = job.get("company", "Unknown")
        title = job.get("title", "Role")
        score = job.get("score", 0)
        url = job.get("url", "#")

        alert = (
            f"🚨 <b>A-GRADE OPPORTUNITY</b>\n\n"
            f"<b>{company}</b> — {title}\n"
            f"ATS: {score}% | Visa: checkmark\n"
            f"<a href='{url}'>Apply Now</a>"
        )

        return self.send(alert)

    def test_connection(self) -> bool:
        """
        Test Telegram bot connection.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self.enabled:
            logger.error("Telegram not configured: missing token or chat_id")
            return False

        test_msg = (
            "🤖 <b>HuntFlow Test</b>\n\n"
            "Telegram bot connection successful!"
        )
        return self.send(test_msg)

    @staticmethod
    def _grade_emoji(grade: str) -> str:
        """Map grade to emoji."""
        grades = {
            "A+": "🟢",
            "A": "🟢",
            "B+": "🟡",
            "B": "🟡",
            "C+": "🟠",
            "C": "🟠",
            "D": "🔴",
        }
        return grades.get(grade, "⚪")


__all__ = ["TelegramNotifier"]
