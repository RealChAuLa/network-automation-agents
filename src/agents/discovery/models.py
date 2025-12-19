"""
Discovery Agent Models

Data models for diagnosis reports and detected issues.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid
import json


class IssueSeverity(str, Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    HEALTHY = "healthy"
    INFO = "info"


class IssueType(str, Enum):
    """Types of issues that can be detected."""
    HIGH_CPU = "HIGH_CPU"
    MEMORY_LEAK = "MEMORY_LEAK"
    INTERFACE_DOWN = "INTERFACE_DOWN"
    PACKET_LOSS = "PACKET_LOSS"
    HIGH_LATENCY = "HIGH_LATENCY"
    HIGH_ERROR_RATE = "HIGH_ERROR_RATE"
    AUTH_FAILURE = "AUTH_FAILURE"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    SERVICE_DEGRADATION = "SERVICE_DEGRADATION"
    TEMPERATURE_HIGH = "TEMPERATURE_HIGH"
    CONNECTIVITY_ISSUE = "CONNECTIVITY_ISSUE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectedIssue:
    """A single detected issue."""

    id: str = field(default_factory=lambda: f"issue_{uuid. uuid4().hex[:8]}")
    issue_type: IssueType = IssueType. UNKNOWN
    severity: IssueSeverity = IssueSeverity.MEDIUM
    node_id: str = ""
    node_name: str = ""
    node_type: str = ""

    # Issue details
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    unit: Optional[str] = None

    # Analysis
    description: str = ""
    potential_causes: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    # Related data
    related_logs: list[str] = field(default_factory=list)
    affected_downstream_nodes: list[str] = field(default_factory=list)

    # Timestamps
    detected_at: datetime = field(default_factory=datetime.utcnow)

    # Metadata
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "DetectedIssue":
        """Create from dictionary (e.g., from LLM response)."""
        issue_type = data.get("issue_type", "UNKNOWN")
        if isinstance(issue_type, str):
            try:
                issue_type = IssueType(issue_type)
            except ValueError:
                issue_type = IssueType.UNKNOWN

        severity = data.get("severity", "medium")
        if isinstance(severity, str):
            try:
                severity = IssueSeverity(severity. lower())
            except ValueError:
                severity = IssueSeverity.MEDIUM

        return cls(
            issue_type=issue_type,
            severity=severity,
            node_id=data.get("node_id", ""),
            node_name=data.get("node_name", ""),
            node_type=data.get("node_type", ""),
            current_value=data. get("current_value"),
            threshold_value=data.get("threshold_value"),
            unit=data.get("unit"),
            description=data.get("description", ""),
            potential_causes=data. get("potential_causes", []),
            recommended_actions=data.get("recommended_actions", []),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "issue_type": self.issue_type.value,
            "severity": self. severity.value,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "metric_name": self. metric_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "unit": self.unit,
            "description": self.description,
            "potential_causes": self.potential_causes,
            "recommended_actions": self. recommended_actions,
            "related_logs": self. related_logs,
            "affected_downstream_nodes": self. affected_downstream_nodes,
            "detected_at": self. detected_at.isoformat(),
            "metadata": self. metadata,
        }


@dataclass
class DiagnosisReport:
    """Complete diagnosis report from the Discovery Agent."""

    id: str = field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Scope
    scope: str = "network-wide"
    nodes_analyzed: int = 0

    # Overall status
    overall_status: IssueSeverity = IssueSeverity.HEALTHY
    summary: str = ""

    # Issues
    issues: list[DetectedIssue] = field(default_factory=list)

    # Summary counts
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    # Analysis metadata
    analysis_method: str = "llm-mcp"
    llm_provider: Optional[str] = None

    # Root cause analysis
    root_cause_analysis: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)

    # Performance
    analysis_duration_ms: Optional[int] = None
    tool_calls_made: int = 0

    # Raw data (for debugging)
    raw_llm_response: Optional[str] = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_issue(self, issue: DetectedIssue):
        """Add an issue and update counts."""
        self. issues.append(issue)
        self._update_counts()
        self._update_overall_status()

    def _update_counts(self):
        """Update issue counts by severity."""
        self.critical_count = len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL])
        self.high_count = len([i for i in self.issues if i. severity == IssueSeverity.HIGH])
        self.medium_count = len([i for i in self.issues if i. severity == IssueSeverity.MEDIUM])
        self. low_count = len([i for i in self.issues if i.severity == IssueSeverity.LOW])

    def _update_overall_status(self):
        """Update overall status based on highest severity issue."""
        if self.critical_count > 0:
            self.overall_status = IssueSeverity. CRITICAL
        elif self.high_count > 0:
            self.overall_status = IssueSeverity.HIGH
        elif self.medium_count > 0:
            self.overall_status = IssueSeverity. MEDIUM
        elif self.low_count > 0:
            self.overall_status = IssueSeverity.LOW
        else:
            self.overall_status = IssueSeverity.HEALTHY

    @classmethod
    def from_llm_response(cls, response_data: dict, **kwargs) -> "DiagnosisReport":
        """Create report from LLM response."""
        report = cls(**kwargs)

        # Parse overall status
        status_str = response_data. get("overall_status", "healthy")
        try:
            report. overall_status = IssueSeverity(status_str. lower())
        except ValueError:
            report. overall_status = IssueSeverity. HEALTHY

        report.summary = response_data.get("summary", "")
        report.root_cause_analysis = response_data.get("root_cause_analysis")
        report.recommendations = response_data.get("recommendations", [])

        # Parse issues
        for issue_data in response_data.get("issues", []):
            issue = DetectedIssue.from_dict(issue_data)
            report.add_issue(issue)

        return report

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "scope": self. scope,
            "nodes_analyzed": self.nodes_analyzed,
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "total_issues": len(self.issues),
            "issues_by_severity": {
                "critical": self.critical_count,
                "high": self. high_count,
                "medium": self.medium_count,
                "low": self.low_count,
            },
            "issues": [i.to_dict() for i in self. issues],
            "analysis_method": self.analysis_method,
            "llm_provider": self. llm_provider,
            "root_cause_analysis": self.root_cause_analysis,
            "recommendations": self. recommendations,
            "analysis_duration_ms": self.analysis_duration_ms,
            "tool_calls_made": self. tool_calls_made,
            "metadata": self.metadata,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        status_emoji = {
            IssueSeverity.CRITICAL: "🔴",
            IssueSeverity. HIGH: "🟠",
            IssueSeverity. MEDIUM: "🟡",
            IssueSeverity. LOW: "🟢",
            IssueSeverity. HEALTHY: "✅",
        }

        emoji = status_emoji. get(self.overall_status, "❓")

        lines = [
            f"{emoji} Diagnosis Report: {self.id}",
            f"   Status: {self.overall_status.value. upper()}",
            f"   Scope: {self.scope}",
            f"   Nodes Analyzed: {self. nodes_analyzed}",
            f"   Issues Found: {len(self.issues)}",
            f"   Tool Calls: {self.tool_calls_made}",
        ]

        if self. issues:
            lines. append(f"   - Critical: {self. critical_count}")
            lines.append(f"   - High: {self.high_count}")
            lines.append(f"   - Medium: {self.medium_count}")
            lines.append(f"   - Low: {self.low_count}")

        if self.summary:
            lines. append(f"   Summary: {self. summary[:100]}...")

        return "\n". join(lines)