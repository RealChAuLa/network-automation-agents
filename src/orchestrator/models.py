"""
Orchestrator Models

Data models for pipeline runs and orchestrator state.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid

from dotenv import load_dotenv

load_dotenv()


class PipelineStatus(str, Enum):
    """Status of a pipeline run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"  # Some steps succeeded
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class StepStatus(str, Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step_name: str = ""
    status: StepStatus = StepStatus.PENDING

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Result data
    result: Any = None
    error: Optional[str] = None

    # Counts (step-specific)
    items_processed: int = 0
    items_passed: int = 0
    items_failed: int = 0

    def start(self):
        """Mark step as started."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete_success(self, result: Any = None, items_processed: int = 0, items_passed: int = 0):
        """Mark step as successful."""
        self.status = StepStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        self.result = result
        self.items_processed = items_processed
        self.items_passed = items_passed
        self._calculate_duration()

    def complete_failure(self, error: str, result: Any = None):
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error
        self.result = result
        self._calculate_duration()

    def skip(self, reason: str = ""):
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.error = reason

    def _calculate_duration(self):
        """Calculate step duration."""
        if self.started_at and self.completed_at:
            self.duration_ms = int(
                (self.completed_at - self.started_at).total_seconds() * 1000
            )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "items_processed": self.items_processed,
            "items_passed": self.items_passed,
            "items_failed": self.items_failed,
        }


@dataclass
class PipelineRun:
    """Record of a complete pipeline run."""

    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Status
    status: PipelineStatus = PipelineStatus.PENDING

    # Steps
    steps: dict[str, StepResult] = field(default_factory=dict)

    # Configuration used
    config: dict = field(default_factory=dict)

    # Trigger info
    trigger: str = "manual"  # manual, scheduled, api
    triggered_by: str = "system"

    # Summary
    summary: str = ""

    # Counts
    issues_found: int = 0
    actions_recommended: int = 0
    actions_approved: int = 0
    actions_executed: int = 0
    actions_successful: int = 0

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_step(self, step_name: str) -> StepResult:
        """Add a new step."""
        step = StepResult(step_name=step_name)
        self.steps[step_name] = step
        return step

    def get_step(self, step_name: str) -> Optional[StepResult]:
        """Get a step by name."""
        return self.steps.get(step_name)

    def start(self):
        """Mark run as started."""
        self.status = PipelineStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self):
        """Mark run as completed and calculate status."""
        self.completed_at = datetime.utcnow()
        self._calculate_duration()
        self._calculate_status()
        self._generate_summary()

    def cancel(self, reason: str = ""):
        """Mark run as cancelled."""
        self.status = PipelineStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.summary = f"Cancelled: {reason}" if reason else "Cancelled"
        self._calculate_duration()

    def _calculate_duration(self):
        """Calculate total duration."""
        if self.started_at and self.completed_at:
            self.duration_ms = int(
                (self.completed_at - self.started_at).total_seconds() * 1000
            )

    def _calculate_status(self):
        """Calculate overall status from steps."""
        step_statuses = [s.status for s in self.steps.values()]

        if not step_statuses:
            self.status = PipelineStatus.SUCCESS
            return

        if all(s == StepStatus.SUCCESS for s in step_statuses):
            self.status = PipelineStatus.SUCCESS
        elif all(s == StepStatus.SKIPPED for s in step_statuses):
            self.status = PipelineStatus.SKIPPED
        elif any(s == StepStatus.FAILED for s in step_statuses):
            if any(s == StepStatus.SUCCESS for s in step_statuses):
                self.status = PipelineStatus.PARTIAL
            else:
                self.status = PipelineStatus.FAILED
        else:
            self.status = PipelineStatus.SUCCESS

    def _generate_summary(self):
        """Generate run summary."""
        if self.status == PipelineStatus.SUCCESS:
            self.summary = (
                f"Pipeline completed successfully.  "
                f"Found {self.issues_found} issues, "
                f"executed {self.actions_successful}/{self.actions_executed} actions."
            )
        elif self.status == PipelineStatus.PARTIAL:
            failed_steps = [s.step_name for s in self.steps.values() if s.status == StepStatus.FAILED]
            self.summary = f"Pipeline partially completed. Failed steps: {', '.join(failed_steps)}"
        elif self.status == PipelineStatus.FAILED:
            self.summary = "Pipeline failed."
        elif self.status == PipelineStatus.SKIPPED:
            self.summary = "Pipeline skipped - no issues found."

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "config": self.config,
            "trigger": self.trigger,
            "triggered_by": self.triggered_by,
            "summary": self.summary,
            "issues_found": self.issues_found,
            "actions_recommended": self.actions_recommended,
            "actions_approved": self.actions_approved,
            "actions_executed": self.actions_executed,
            "actions_successful": self.actions_successful,
            "metadata": self.metadata,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        status_emoji = {
            PipelineStatus.SUCCESS: "✅",
            PipelineStatus.PARTIAL: "⚠️",
            PipelineStatus.FAILED: "❌",
            PipelineStatus.CANCELLED: "🚫",
            PipelineStatus.SKIPPED: "⏭️",
            PipelineStatus.RUNNING: "🔄",
            PipelineStatus.PENDING: "⏳",
        }

        emoji = status_emoji.get(self.status, "❓")

        lines = [
            f"{emoji} Pipeline Run:  {self.id}",
            f"   Status: {self.status.value.upper()}",
            f"   Duration: {self.duration_ms}ms" if self.duration_ms else "   Duration: N/A",
            f"   Issues Found: {self.issues_found}",
            f"   Actions:  {self.actions_successful}/{self.actions_executed} successful",
        ]

        if self.summary:
            lines.append(f"   Summary: {self.summary[: 60]}...")

        return "\n".join(lines)


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    # Agent settings
    use_llm: bool = True
    verify_execution: bool = True
    dry_run: bool = False

    # Step control
    skip_discovery: bool = False
    skip_policy: bool = False
    skip_compliance: bool = False
    skip_execution: bool = False

    # Behavior
    stop_on_no_issues: bool = True
    stop_on_no_actions: bool = True
    stop_on_compliance_denial: bool = False

    # Limits
    max_actions_per_run: int = 10

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create config from environment."""
        return cls(
            use_llm=os.getenv("PIPELINE_USE_LLM", "true").lower() == "true",
            verify_execution=os.getenv("PIPELINE_VERIFY", "true").lower() == "true",
            dry_run=os.getenv("PIPELINE_DRY_RUN", "false").lower() == "true",
            max_actions_per_run=int(os.getenv("PIPELINE_MAX_ACTIONS", "10")),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "use_llm": self.use_llm,
            "verify_execution": self.verify_execution,
            "dry_run": self.dry_run,
            "skip_discovery": self.skip_discovery,
            "skip_policy": self.skip_policy,
            "skip_compliance": self.skip_compliance,
            "skip_execution": self.skip_execution,
            "stop_on_no_issues": self.stop_on_no_issues,
            "stop_on_no_actions": self.stop_on_no_actions,
            "stop_on_compliance_denial": self.stop_on_compliance_denial,
            "max_actions_per_run": self.max_actions_per_run,
        }


@dataclass
class OrchestratorStatus:
    """Current status of the orchestrator."""

    # State
    running: bool = False
    paused: bool = False

    # Scheduling
    interval_minutes: int = 5
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    # Statistics
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0

    # Current run
    current_run_id: Optional[str] = None

    # Uptime
    started_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "running": self.running,
            "paused": self.paused,
            "interval_minutes": self.interval_minutes,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "current_run_id": self.current_run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }