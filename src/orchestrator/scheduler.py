"""
Scheduler

Handles scheduling of pipeline runs.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Simple async scheduler for running the pipeline at intervals.

    Example:
        >>> scheduler = Scheduler(interval_minutes=5)
        >>> scheduler.start(pipeline. execute)
    """

    def __init__(self, interval_minutes: int = 5):
        """
        Initialize the scheduler.

        Args:
            interval_minutes:  Minutes between runs
        """
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60

        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._callback: Optional[Callable] = None

        self.next_run_at: Optional[datetime] = None
        self.last_run_at: Optional[datetime] = None
        self.run_count = 0

    def start(self, callback: Callable):
        """
        Start the scheduler.

        Args:
            callback:  Async function to call on each run
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._callback = callback
        self._running = True
        self._paused = False
        self._update_next_run()

        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler started.  Interval: {self.interval_minutes} minutes")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.next_run_at = None
        logger.info("Scheduler stopped")

    def pause(self):
        """Pause the scheduler."""
        self._paused = True
        logger.info("Scheduler paused")

    def resume(self):
        """Resume the scheduler."""
        self._paused = False
        self._update_next_run()
        logger.info("Scheduler resumed")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if scheduler is paused."""
        return self._paused

    def set_interval(self, minutes: int):
        """
        Update the interval.

        Args:
            minutes: New interval in minutes
        """
        self.interval_minutes = minutes
        self.interval_seconds = minutes * 60
        self._update_next_run()
        logger.info(f"Scheduler interval updated to {minutes} minutes")

    def _update_next_run(self):
        """Update the next run time."""
        if self._running and not self._paused:
            self.next_run_at = datetime.utcnow() + timedelta(seconds=self.interval_seconds)

    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Wait for the interval
                await asyncio.sleep(self.interval_seconds)

                # Check if still running and not paused
                if not self._running:
                    break

                if self._paused:
                    continue

                # Run the callback
                if self._callback:
                    self.last_run_at = datetime.utcnow()
                    self.run_count += 1

                    logger.info(f"Scheduled run #{self.run_count} starting...")

                    try:
                        await self._callback()
                    except Exception as e:
                        logger.error(f"Scheduled run error: {e}")

                    self._update_next_run()

            except asyncio.CancelledError:
                logger.info("Scheduler task cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def run_now(self) -> bool:
        """
        Trigger an immediate run.

        Returns:
            True if run was triggered
        """
        if not self._callback:
            logger.warning("No callback configured")
            return False

        self.last_run_at = datetime.utcnow()
        self.run_count += 1

        logger.info(f"Manual run #{self.run_count} starting...")

        try:
            await self._callback()
            return True
        except Exception as e:
            logger.error(f"Manual run error:  {e}")
            return False

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "paused": self._paused,
            "interval_minutes": self.interval_minutes,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "run_count": self.run_count,
        }