"""
Orchestrator

Main orchestrator that coordinates all agents and manages the automation pipeline.
"""

import os
import asyncio
import logging
import signal
from datetime import datetime
from typing import Optional, List

from dotenv import load_dotenv

from src.orchestrator.models import (
    PipelineRun,
    PipelineConfig,
    PipelineStatus,
    OrchestratorStatus,
)
from src.orchestrator.pipeline import Pipeline
from src.orchestrator.scheduler import Scheduler
from src.audit.logger import AuditLogger

load_dotenv()

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestrator that coordinates all agents.

    The orchestrator:
    - Manages the scheduler
    - Runs the pipeline on schedule or manually
    - Tracks run history
    - Provides status and monitoring

    Example:
         orchestrator = Orchestrator()
         await orchestrator.start()
         # ...  runs until stopped
         await orchestrator. stop()
    """

    def __init__(
            self,
            interval_minutes: int = None,
            config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            interval_minutes: Minutes between scheduled runs
            config:  Default pipeline configuration
        """
        self.interval_minutes = interval_minutes or int(os.getenv("ORCHESTRATOR_INTERVAL", "5"))
        self.config = config or PipelineConfig.from_env()

        # Initialize components
        self.pipeline = Pipeline(config=self.config)
        self.scheduler = Scheduler(interval_minutes=self.interval_minutes)
        self.audit = AuditLogger()

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Run history (in-memory, last N runs)
        self._run_history: List[PipelineRun] = []
        self._max_history = 100

        # Statistics
        self._started_at: Optional[datetime] = None
        self._total_runs = 0
        self._successful_runs = 0
        self._failed_runs = 0

        # Current run
        self._current_run: Optional[PipelineRun] = None

        logger.info(f"Orchestrator initialized.  Interval: {self.interval_minutes} minutes")

    async def start(self):
        """
        Start the orchestrator.

        This starts the scheduler and begins running the pipeline
        at the configured interval.
        """
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._started_at = datetime.utcnow()
        self._shutdown_event.clear()

        # Connect audit
        self.audit.connect()

        logger.info("Orchestrator starting...")

        # Start scheduler
        self.scheduler.start(self._run_pipeline)

        # Run immediately on start
        await self._run_pipeline()

        # Wait for shutdown
        await self._shutdown_event.wait()

        logger.info("Orchestrator stopped")

    async def stop(self):
        """Stop the orchestrator."""
        if not self._running:
            return

        logger.info("Orchestrator stopping...")
        self._running = False
        self.scheduler.stop()
        self._shutdown_event.set()

    def pause(self):
        """Pause scheduled runs."""
        self.scheduler.pause()
        logger.info("Orchestrator paused")

    def resume(self):
        """Resume scheduled runs."""
        self.scheduler.resume()
        logger.info("Orchestrator resumed")

    async def run_now(
            self,
            config: Optional[PipelineConfig] = None,
            trigger: str = "manual",
    ) -> PipelineRun:
        """
        Trigger an immediate pipeline run.

        Args:
            config: Override configuration for this run
            trigger: What triggered this run

        Returns:
            PipelineRun result
        """
        logger.info("Manual pipeline run triggered")
        return await self._run_pipeline(config=config, trigger=trigger)

    async def _run_pipeline(
            self,
            config: Optional[PipelineConfig] = None,
            trigger: str = "scheduled",
    ) -> PipelineRun:
        """
        Execute a pipeline run.

        Args:
            config: Override configuration
            trigger: What triggered the run

        Returns:
            PipelineRun result
        """
        config = config or self.config

        try:
            # Execute pipeline
            run = await self.pipeline.execute(
                config=config,
                trigger=trigger,
                triggered_by="orchestrator",
            )

            # Track current run
            self._current_run = run

            # Update statistics
            self._total_runs += 1
            if run.status == PipelineStatus.SUCCESS:
                self._successful_runs += 1
            elif run.status in [PipelineStatus.FAILED, PipelineStatus.PARTIAL]:
                self._failed_runs += 1

            # Add to history
            self._add_to_history(run)

            # Log summary
            logger.info(run.get_summary())

            self._current_run = None
            return run

        except Exception as e:
            logger.error(f"Pipeline run failed: {e}")

            # Create failed run record
            run = PipelineRun(
                status=PipelineStatus.FAILED,
                trigger=trigger,
                summary=f"Pipeline error: {str(e)}",
            )
            run.completed_at = datetime.utcnow()

            self._total_runs += 1
            self._failed_runs += 1
            self._add_to_history(run)

            return run

    def _add_to_history(self, run: PipelineRun):
        """Add a run to history."""
        self._run_history.insert(0, run)

        # Trim history
        if len(self._run_history) > self._max_history:
            self._run_history = self._run_history[: self._max_history]

    def get_status(self) -> OrchestratorStatus:
        """Get current orchestrator status."""
        scheduler_status = self.scheduler.get_status()

        return OrchestratorStatus(
            running=self._running,
            paused=scheduler_status["paused"],
            interval_minutes=self.interval_minutes,
            next_run_at=self.scheduler.next_run_at,
            last_run_at=self.scheduler.last_run_at,
            total_runs=self._total_runs,
            successful_runs=self._successful_runs,
            failed_runs=self._failed_runs,
            current_run_id=self._current_run.id if self._current_run else None,
            started_at=self._started_at,
        )

    def get_run_history(self, limit: int = 10) -> List[PipelineRun]:
        """
        Get recent run history.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of recent pipeline runs
        """
        return self._run_history[: limit]

    def get_last_run(self) -> Optional[PipelineRun]:
        """Get the most recent run."""
        if self._run_history:
            return self._run_history[0]
        return None

    def set_interval(self, minutes: int):
        """
        Update the scheduling interval.

        Args:
            minutes: New interval in minutes
        """
        self.interval_minutes = minutes
        self.scheduler.set_interval(minutes)
        logger.info(f"Interval updated to {minutes} minutes")

    def set_config(self, config: PipelineConfig):
        """
        Update the default pipeline configuration.

        Args:
            config: New pipeline configuration
        """
        self.config = config
        self.pipeline.config = config
        logger.info("Pipeline configuration updated")

    def get_statistics(self) -> dict:
        """Get orchestrator statistics."""
        uptime_seconds = None
        if self._started_at:
            uptime_seconds = int((datetime.utcnow() - self._started_at).total_seconds())

        success_rate = 0
        if self._total_runs > 0:
            success_rate = (self._successful_runs / self._total_runs) * 100

        return {
            "total_runs": self._total_runs,
            "successful_runs": self._successful_runs,
            "failed_runs": self._failed_runs,
            "success_rate": round(success_rate, 1),
            "uptime_seconds": uptime_seconds,
            "interval_minutes": self.interval_minutes,
        }

    def get_graph_visualization(self) -> str:
        """Get the LangGraph visualization."""
        return self. pipeline.get_graph_visualization()