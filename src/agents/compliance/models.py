"""
Compliance Agent Models

Data models for compliance validation results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class ValidationStatus(str, Enum):
    """Status of action validation."""
    APPROVED = "approved"
    DENIED = "denied"
    PENDING_APPROVAL = "pending_approval"
    DEFERRED = "deferred"


class ViolationType(str, Enum):
    """Types of compliance violations."""
    MAINTENANCE_WINDOW = "maintenance_window"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    REGULATORY_VIOLATION = "regulatory_violation"
    NODE_CRITICALITY = "node_criticality"
    TIME_RESTRICTION = "time_restriction"
    DUAL_AUTHORIZATION = "dual_authorization"
    CHANGE_FREEZE = "change_freeze"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"


@dataclass
class ComplianceViolation:
    """A single compliance violation."""

    id: str = field(default_factory=lambda: f"violation_{uuid.uuid4().hex[:8]}")

    # Violation details
    violation_type: ViolationType = ViolationType.REGULATORY_VIOLATION
    rule_id: str = ""
    rule_name: str = ""

    # Severity
    severity: str = "high"  # critical, high, medium, low
    blocking: bool = True  # If True, action cannot proceed

    # Description
    description: str = ""
    reason: str = ""

    # Resolution
    resolution_options: list[str] = field(default_factory=list)
    can_override: bool = False
    override_requires: str = ""  # e.g., "manager_approval"

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "violation_type": self.violation_type.value,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "blocking": self.blocking,
            "description": self.description,
            "reason": self.reason,
            "resolution_options": self.resolution_options,
            "can_override": self.can_override,
            "override_requires": self.override_requires,
            "metadata": self.metadata,
        }


@dataclass
class ActionValidation:
    """Validation result for a single action."""

    id: str = field(default_factory=lambda: f"val_{uuid.uuid4().hex[:8]}")

    # Action reference
    action_id: str = ""
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""

    # Validation result
    status: ValidationStatus = ValidationStatus.PENDING_APPROVAL

    # Violations found
    violations: list[ComplianceViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Timing
    validated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None  # Approval expiry

    # If approved
    approved_by: str = "system"  # or user name
    approval_notes: str = ""

    # If denied
    denial_reason: str = ""

    # If deferred
    deferred_until: Optional[datetime] = None
    defer_reason: str = ""

    # Metadata
    metadata: dict = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """Check if action is approved."""
        return self.status == ValidationStatus.APPROVED

    @property
    def is_denied(self) -> bool:
        """Check if action is denied."""
        return self.status == ValidationStatus.DENIED

    @property
    def has_blocking_violations(self) -> bool:
        """Check if there are blocking violations."""
        return any(v.blocking for v in self.violations)

    def add_violation(self, violation: ComplianceViolation):
        """Add a violation and update status."""
        self.violations.append(violation)
        if violation.blocking:
            self.status = ValidationStatus.DENIED
            self.denial_reason = violation.description

    def add_warning(self, warning: str):
        """Add a non-blocking warning."""
        self.warnings.append(warning)

    def approve(self, approved_by: str = "system", notes: str = ""):
        """Mark action as approved."""
        self.status = ValidationStatus.APPROVED
        self.approved_by = approved_by
        self.approval_notes = notes

    def deny(self, reason: str):
        """Mark action as denied."""
        self.status = ValidationStatus.DENIED
        self.denial_reason = reason

    def defer(self, until: datetime, reason: str):
        """Defer action to a later time."""
        self.status = ValidationStatus.DEFERRED
        self.deferred_until = until
        self.defer_reason = reason

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "validated_at": self.validated_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "approved_by": self.approved_by,
            "approval_notes": self.approval_notes,
            "denial_reason": self.denial_reason,
            "deferred_until": self.deferred_until.isoformat() if self.deferred_until else None,
            "defer_reason": self.defer_reason,
            "metadata": self.metadata,
        }


@dataclass
class ComplianceResult:
    """Complete compliance validation result from the Compliance Agent."""

    id: str = field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Input reference
    recommendation_id: str = ""
    diagnosis_id: str = ""

    # Validation results
    validations: list[ActionValidation] = field(default_factory=list)

    # Summary counts
    total_actions: int = 0
    approved_count: int = 0
    denied_count: int = 0
    pending_count: int = 0
    deferred_count: int = 0

    # Overall result
    all_approved: bool = False
    has_violations: bool = False

    # Analysis metadata
    analysis_method: str = "llm-mcp"
    llm_provider: Optional[str] = None

    # Summary
    summary: str = ""
    reasoning: str = ""

    # Compliance rules evaluated
    rules_evaluated: list[str] = field(default_factory=list)

    # Performance
    analysis_duration_ms: Optional[int] = None
    tool_calls_made: int = 0

    # Raw LLM response
    raw_llm_response: Optional[str] = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_validation(self, validation: ActionValidation):
        """Add a validation result and update counts."""
        self.validations.append(validation)
        self._update_counts()

    def _update_counts(self):
        """Update summary counts."""
        self.total_actions = len(self.validations)
        self.approved_count = len([v for v in self.validations if v.status == ValidationStatus.APPROVED])
        self.denied_count = len([v for v in self.validations if v.status == ValidationStatus.DENIED])
        self.pending_count = len([v for v in self.validations if v.status == ValidationStatus.PENDING_APPROVAL])
        self.deferred_count = len([v for v in self.validations if v.status == ValidationStatus.DEFERRED])

        self.all_approved = self.approved_count == self.total_actions and self.total_actions > 0
        self.has_violations = any(v.violations for v in self.validations)

    def get_approved_actions(self) -> list[ActionValidation]:
        """Get list of approved actions."""
        return [v for v in self.validations if v.status == ValidationStatus.APPROVED]

    def get_denied_actions(self) -> list[ActionValidation]:
        """Get list of denied actions."""
        return [v for v in self.validations if v.status == ValidationStatus.DENIED]

    def get_pending_actions(self) -> list[ActionValidation]:
        """Get list of actions pending approval."""
        return [v for v in self.validations if v.status == ValidationStatus.PENDING_APPROVAL]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "recommendation_id": self.recommendation_id,
            "diagnosis_id": self.diagnosis_id,
            "total_actions": self.total_actions,
            "approved_count": self.approved_count,
            "denied_count": self.denied_count,
            "pending_count": self.pending_count,
            "deferred_count": self.deferred_count,
            "all_approved": self.all_approved,
            "has_violations": self.has_violations,
            "validations": [v.to_dict() for v in self.validations],
            "analysis_method": self.analysis_method,
            "llm_provider": self.llm_provider,
            "summary": self.summary,
            "reasoning": self.reasoning,
            "rules_evaluated": self.rules_evaluated,
            "analysis_duration_ms": self.analysis_duration_ms,
            "tool_calls_made": self.tool_calls_made,
            "metadata": self.metadata,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        if self.all_approved:
            emoji = "✅"
            status = "ALL APPROVED"
        elif self.denied_count > 0:
            emoji = "❌"
            status = "HAS DENIALS"
        elif self.pending_count > 0:
            emoji = "⏳"
            status = "PENDING APPROVAL"
        else:
            emoji = "📋"
            status = "PROCESSED"

        lines = [
            f"{emoji} Compliance Result:  {self.id}",
            f"   Status: {status}",
            f"   Recommendation: {self.recommendation_id}",
            f"   Total Actions: {self.total_actions}",
            f"   - Approved: {self.approved_count}",
            f"   - Denied: {self.denied_count}",
            f"   - Pending: {self.pending_count}",
            f"   - Deferred: {self.deferred_count}",
        ]

        if self.summary:
            lines.append(f"   Summary: {self.summary[: 80]}...")

        return "\n".join(lines)