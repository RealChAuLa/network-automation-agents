"""
Audit Models

Data models for audit records.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid
import json
import hashlib


class AuditRecordType(str, Enum):
    """Types of audit records."""
    INTENT = "intent"  # Before action execution
    RESULT = "result"  # After action execution
    DENIAL = "denial"  # Compliance denial
    DIAGNOSIS = "diagnosis"  # Discovery findings
    POLICY = "policy"  # Policy evaluation
    VERIFICATION = "verification"  # Post-execution verification
    SYSTEM = "system"  # System events


@dataclass
class AuditRecord:
    """Base audit record."""

    id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex}")
    record_type: AuditRecordType = AuditRecordType.SYSTEM
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Source tracking
    agent_name: str = ""
    execution_id: str = ""

    # Related IDs for traceability
    diagnosis_id: str = ""
    recommendation_id: str = ""
    compliance_id: str = ""
    action_id: str = ""

    # Content
    summary: str = ""
    details: dict = field(default_factory=dict)

    # Metadata
    metadata: dict = field(default_factory=dict)

    # Computed hash for integrity
    content_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of record content."""
        content = {
            "id": self.id,
            "record_type": self.record_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "execution_id": self.execution_id,
            "diagnosis_id": self.diagnosis_id,
            "recommendation_id": self.recommendation_id,
            "compliance_id": self.compliance_id,
            "action_id": self.action_id,
            "summary": self.summary,
            "details": self.details,
        }
        content_str = json.dumps(content, sort_keys=True)
        self.content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self.content_hash

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        if not self.content_hash:
            self.compute_hash()

        return {
            "id": self.id,
            "record_type": self.record_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "execution_id": self.execution_id,
            "diagnosis_id": self.diagnosis_id,
            "recommendation_id": self.recommendation_id,
            "compliance_id": self.compliance_id,
            "action_id": self.action_id,
            "summary": self.summary,
            "details": self.details,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "AuditRecord":
        """Create from dictionary."""
        record = cls(
            id=data.get("id", ""),
            record_type=AuditRecordType(data.get("record_type", "system")),
            agent_name=data.get("agent_name", ""),
            execution_id=data.get("execution_id", ""),
            diagnosis_id=data.get("diagnosis_id", ""),
            recommendation_id=data.get("recommendation_id", ""),
            compliance_id=data.get("compliance_id", ""),
            action_id=data.get("action_id", ""),
            summary=data.get("summary", ""),
            details=data.get("details", {}),
            metadata=data.get("metadata", {}),
            content_hash=data.get("content_hash", ""),
        )

        if data.get("timestamp"):
            record.timestamp = datetime.fromisoformat(data["timestamp"])

        return record


@dataclass
class IntentRecord(AuditRecord):
    """Record of intent before action execution."""

    record_type: AuditRecordType = field(default=AuditRecordType.INTENT)

    # Action details
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""
    target_node_type: str = ""

    # Reason and context
    reason: str = ""
    original_issue_type: str = ""
    original_issue_severity: str = ""
    original_value: Optional[float] = None

    # Approval chain
    policy_ids: list[str] = field(default_factory=list)
    compliance_status: str = ""
    approved_by: str = ""

    # Expected outcome
    expected_outcome: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "target_node_type": self.target_node_type,
            "reason": self.reason,
            "original_issue_type": self.original_issue_type,
            "original_issue_severity": self.original_issue_severity,
            "original_value": self.original_value,
            "policy_ids": self.policy_ids,
            "compliance_status": self.compliance_status,
            "approved_by": self.approved_by,
            "expected_outcome": self.expected_outcome,
        })
        return data


@dataclass
class ResultRecord(AuditRecord):
    """Record of result after action execution."""

    record_type: AuditRecordType = field(default=AuditRecordType.RESULT)

    # Execution reference
    intent_record_id: str = ""

    # Action details
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""

    # Result
    success: bool = False
    status: str = ""
    result_message: str = ""
    error_message: str = ""

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Retry info
    retry_count: int = 0

    # Verification
    verified: bool = False
    verification_status: str = ""
    metrics_before: dict = field(default_factory=dict)
    metrics_after: dict = field(default_factory=dict)
    improvement_detected: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            "intent_record_id": self.intent_record_id,
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "success": self.success,
            "status": self.status,
            "result_message": self.result_message,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "verified": self.verified,
            "verification_status": self.verification_status,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "improvement_detected": self.improvement_detected,
        })
        return data


@dataclass
class DenialRecord(AuditRecord):
    """Record of compliance denial."""

    record_type: AuditRecordType = field(default=AuditRecordType.DENIAL)

    # Action details
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""

    # Denial details
    denial_reason: str = ""
    violation_type: str = ""
    rule_id: str = ""
    rule_name: str = ""

    # Context
    original_issue_type: str = ""
    original_issue_severity: str = ""

    # Resolution
    resolution_options: list[str] = field(default_factory=list)
    can_override: bool = False
    override_requires: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = super().to_dict()
        data.update({
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "denial_reason": self.denial_reason,
            "violation_type": self.violation_type,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "original_issue_type": self.original_issue_type,
            "original_issue_severity": self.original_issue_severity,
            "resolution_options": self.resolution_options,
            "can_override": self.can_override,
            "override_requires": self.override_requires,
        })
        return data


@dataclass
class AuditQuery:
    """Query parameters for audit records."""

    record_type: Optional[AuditRecordType] = None
    agent_name: Optional[str] = None
    action_type: Optional[str] = None
    target_node_id: Optional[str] = None
    success: Optional[bool] = None

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    limit: int = 100
    offset: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "record_type": self.record_type.value if self.record_type else None,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "success": self.success,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "limit": self.limit,
            "offset": self.offset,
        }