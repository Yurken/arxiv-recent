"""APScheduler-based daily scheduling."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from arxiv_recent.config import get_settings

logger = logging.getLogger(__name__)


def _run_daily_job() -> None:
    """Execute the full daily pipeline."""
    from datetime import date

    from arxiv_recent.cli import cmd_run

    cmd_run(date.today().isoformat())


def start_scheduler() -> None:
    """Start the blocking scheduler for daily runs."""
    cfg = get_settings()
    hour, minute = cfg.schedule_time.split(":")

    scheduler = BlockingScheduler()
    trigger = CronTrigger(
        hour=int(hour),
        minute=int(minute),
        timezone=cfg.schedule_tz,
    )

    scheduler.add_job(_run_daily_job, trigger, id="daily_digest", replace_existing=True)
    logger.info("Scheduler started: daily at %s %s", cfg.schedule_time, cfg.schedule_tz)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
