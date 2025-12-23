"""
Execution Agent Models

Data models for action execution results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class ExecutionStatus(str, Enum):
    """Status of action execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class VerificationStatus(str, Enum):
    """Status of post-execution verification."""
    NOT_VERIFIED = "not_verified"
    VERIFIED_SUCCESS = "verified_success"
    VERIFIED_FAILED = "verified_failed"
    VERIFICATION_ERROR = "verification_error"


@dataclass
class VerificationResult:
    """Result of post-execution verification."""

    status: VerificationStatus = VerificationStatus.NOT_VERIFIED

    # What was checked
    checks_performed: list[str] = field(default_factory=list)

    # Results
    metrics_before: dict = field(default_factory=dict)
    metrics_after: dict = field(default_factory=dict)

    # Analysis
    improvement_detected: bool = False
    improvement_details: str = ""

    # Issues found
    issues_found: list[str] = field(default_factory=list)

    # Timing
    verified_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "checks_performed": self.checks_performed,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "improvement_detected": self.improvement_detected,
            "improvement_details": self.improvement_details,
            "issues_found": self.issues_found,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class ActionExecution:
    """Execution record for a single action."""

    id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")

    # Action reference
    action_id: str = ""
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""
    target_node_type: str = ""

    # Parameters
    parameters: dict = field(default_factory=dict)

    # Source tracking
    source_policy_id: str = ""
    source_issue_type: str = ""
    reason: str = ""

    # Execution status
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Timing
    queued_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Result details
    success: bool = False
    result_message: str = ""
    result_details: dict = field(default_factory=dict)

    # Error handling
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3

    # Rollback info
    rollback_available: bool = False
    rollback_executed: bool = False
    rollback_result: str = ""

    # Verification
    verification: VerificationResult = field(default_factory=VerificationResult)

    # MCP execution ID (from the execute_action tool)
    mcp_execution_id: str = ""

    # Metadata
    metadata: dict = field(default_factory=dict)

    def start(self):
        """Mark execution as started."""
        self.status = ExecutionStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()

    def complete_success(self, message: str = "", details: dict = None):
        """Mark execution as successful."""
        self.status = ExecutionStatus.SUCCESS
        self.success = True
        self.completed_at = datetime.utcnow()
        self.result_message = message
        self.result_details = details or {}
        self._calculate_duration()

    def complete_failure(self, error: str, details: dict = None):
        """Mark execution as failed."""
        self.status = ExecutionStatus.FAILED
        self.success = False
        self.completed_at = datetime.utcnow()
        self.error_message = error
        self.result_details = details or {}
        self._calculate_duration()

    def mark_skipped(self, reason: str):
        """Mark execution as skipped."""
        self.status = ExecutionStatus.SKIPPED
        self.result_message = reason
        self.completed_at = datetime.utcnow()

    def mark_rolled_back(self, result: str):
        """Mark execution as rolled back."""
        self.status = ExecutionStatus.ROLLED_BACK
        self.rollback_executed = True
        self.rollback_result = result

    def _calculate_duration(self):
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            self.duration_ms = int(
                (self.completed_at - self.started_at).total_seconds() * 1000
            )

    def can_retry(self) -> bool:
        """Check if action can be retried."""
        return (
                self.status == ExecutionStatus.FAILED and
                self.retry_count < self.max_retries
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "target_node_type": self.target_node_type,
            "parameters": self.parameters,
            "source_policy_id": self.source_policy_id,
            "source_issue_type": self.source_issue_type,
            "reason": self.reason,
            "status": self.status.value,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "result_message": self.result_message,
            "result_details": self.result_details,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "rollback_available": self.rollback_available,
            "rollback_executed": self.rollback_executed,
            "rollback_result": self.rollback_result,
            "verification": self.verification.to_dict(),
            "mcp_execution_id": self.mcp_execution_id,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionResult:
    """Complete execution result from the Execution Agent."""

    id: str = field(default_factory=lambda: f"result_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Input references
    compliance_result_id: str = ""
    recommendation_id: str = ""
    diagnosis_id: str = ""

    # Execution records
    executions: list[ActionExecution] = field(default_factory=list)

    # Summary counts
    total_actions: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    rolled_back_count: int = 0

    # Overall status
    all_successful: bool = False
    has_failures: bool = False

    # Verification summary
    verification_performed: bool = False
    verification_success_count: int = 0

    # Analysis metadata
    analysis_method: str = "mcp-execution"
    llm_provider: Optional[str] = None

    # Summary
    summary: str = ""

    # Performance
    total_duration_ms: Optional[int] = None
    tool_calls_made: int = 0

    # Raw LLM response
    raw_llm_response: Optional[str] = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_execution(self, execution: ActionExecution):
        """Add an execution record and update counts."""
        self.executions.append(execution)
        self._update_counts()

    def _update_counts(self):
        """Update summary counts."""
        self.total_actions = len(self.executions)
        self.success_count = len([e for e in self.executions if e.status == ExecutionStatus.SUCCESS])
        self.failed_count = len([e for e in self.executions if e.status == ExecutionStatus.FAILED])
        self.skipped_count = len([e for e in self.executions if e.status == ExecutionStatus.SKIPPED])
        self.rolled_back_count = len([e for e in self.executions if e.status == ExecutionStatus.ROLLED_BACK])

        self.all_successful = self.success_count == self.total_actions and self.total_actions > 0
        self.has_failures = self.failed_count > 0

        # Verification counts
        self.verification_success_count = len([
            e for e in self.executions
            if e.verification.status == VerificationStatus.VERIFIED_SUCCESS
        ])
        self.verification_performed = any(
            e.verification.status != VerificationStatus.NOT_VERIFIED
            for e in self.executions
        )

    def get_successful_executions(self) -> list[ActionExecution]:
        """Get list of successful executions."""
        return [e for e in self.executions if e.status == ExecutionStatus.SUCCESS]

    def get_failed_executions(self) -> list[ActionExecution]:
        """Get list of failed executions."""
        return [e for e in self.executions if e.status == ExecutionStatus.FAILED]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "compliance_result_id": self.compliance_result_id,
            "recommendation_id": self.recommendation_id,
            "diagnosis_id": self.diagnosis_id,
            "total_actions": self.total_actions,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "rolled_back_count": self.rolled_back_count,
            "all_successful": self.all_successful,
            "has_failures": self.has_failures,
            "verification_performed": self.verification_performed,
            "verification_success_count": self.verification_success_count,
            "executions": [e.to_dict() for e in self.executions],
            "analysis_method": self.analysis_method,
            "llm_provider": self.llm_provider,
            "summary": self.summary,
            "total_duration_ms": self.total_duration_ms,
            "tool_calls_made": self.tool_calls_made,
            "metadata": self.metadata,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        if self.all_successful:
            emoji = "✅"
            status = "ALL SUCCESSFUL"
        elif self.has_failures:
            emoji = "❌"
            status = "HAS FAILURES"
        elif self.skipped_count == self.total_actions:
            emoji = "⏭️"
            status = "ALL SKIPPED"
        else:
            emoji = "📋"
            status = "COMPLETED"

        lines = [
            f"{emoji} Execution Result:  {self.id}",
            f"   Status: {status}",
            f"   Total Actions: {self.total_actions}",
            f"   - Successful: {self.success_count}",
            f"   - Failed: {self.failed_count}",
            f"   - Skipped: {self.skipped_count}",
            f"   - Rolled Back: {self.rolled_back_count}",
        ]

        if self.verification_performed:
            lines.append(f"   Verified: {self.verification_success_count}/{self.total_actions}")

        if self.total_duration_ms:
            lines.append(f"   Total Duration: {self.total_duration_ms}ms")

        if self.summary:
            lines.append(f"   Summary: {self.summary[: 80]}...")

        return "\n".join(lines)