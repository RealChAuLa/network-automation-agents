"""
Policy Agent Models

Data models for policy recommendations and actions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class ActionPriority(str, Enum):
    """Priority levels for recommended actions."""
    IMMEDIATE = "immediate"  # Execute now
    HIGH = "high"  # Execute soon
    NORMAL = "normal"  # Execute when convenient
    LOW = "low"  # Can wait
    DEFERRED = "deferred"  # Schedule for later


class ActionStatus(str, Enum):
    """Status of a recommended action."""
    PENDING = "pending"  # Not yet validated
    APPROVED = "approved"  # Passed compliance check
    DENIED = "denied"  # Failed compliance check
    EXECUTED = "executed"  # Already executed
    SKIPPED = "skipped"  # Skipped for some reason


@dataclass
class RecommendedAction:
    """A single recommended action from policy evaluation."""

    id: str = field(default_factory=lambda: f"action_{uuid.uuid4().hex[:8]}")

    # Action details
    action_type: str = ""
    target_node_id: str = ""
    target_node_name: str = ""
    target_node_type: str = ""

    # Parameters
    parameters: dict = field(default_factory=dict)

    # Source
    source_policy_id: str = ""
    source_policy_name: str = ""
    source_issue_id: str = ""
    source_issue_type: str = ""

    # Priority and status
    priority: ActionPriority = ActionPriority.NORMAL
    status: ActionStatus = ActionStatus.PENDING

    # Reasoning
    reason: str = ""
    expected_outcome: str = ""

    # Compliance
    requires_approval: bool = False
    approval_level: str = ""

    # Metadata
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "RecommendedAction":
        """Create from dictionary."""
        priority = data.get("priority", "normal")
        if isinstance(priority, str):
            try:
                priority = ActionPriority(priority.lower())
            except ValueError:
                priority = ActionPriority.NORMAL

        return cls(
            action_type=data.get("action_type", ""),
            target_node_id=data.get("target_node_id", ""),
            target_node_name=data.get("target_node_name", ""),
            target_node_type=data.get("target_node_type", ""),
            parameters=data.get("parameters", {}),
            source_policy_id=data.get("source_policy_id", ""),
            source_policy_name=data.get("source_policy_name", ""),
            source_issue_id=data.get("source_issue_id", ""),
            source_issue_type=data.get("source_issue_type", ""),
            priority=priority,
            reason=data.get("reason", ""),
            expected_outcome=data.get("expected_outcome", ""),
            requires_approval=data.get("requires_approval", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action_type": self.action_type,
            "target_node_id": self.target_node_id,
            "target_node_name": self.target_node_name,
            "target_node_type": self.target_node_type,
            "parameters": self.parameters,
            "source_policy_id": self.source_policy_id,
            "source_policy_name": self.source_policy_name,
            "source_issue_id": self.source_issue_id,
            "source_issue_type": self.source_issue_type,
            "priority": self.priority.value,
            "status": self.status.value,
            "reason": self.reason,
            "expected_outcome": self.expected_outcome,
            "requires_approval": self.requires_approval,
            "approval_level": self.approval_level,
            "metadata": self.metadata,
        }


@dataclass
class MatchedPolicy:
    """A policy that matched the current situation."""

    policy_id: str = ""
    policy_name: str = ""
    policy_type: str = ""
    priority: int = 0

    # Match details
    conditions_matched: list[str] = field(default_factory=list)
    match_score: float = 1.0  # How well it matched (0-1)

    # Actions from this policy
    actions: list[RecommendedAction] = field(default_factory=list)

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "policy_type": self.policy_type,
            "priority": self.priority,
            "conditions_matched": self.conditions_matched,
            "match_score": self.match_score,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": self.metadata,
        }


@dataclass
class PolicyRecommendation:
    """Complete policy recommendation from the Policy Agent."""

    id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Input reference
    diagnosis_id: str = ""
    diagnosis_summary: str = ""
    issues_evaluated: int = 0

    # Matched policies
    matched_policies: list[MatchedPolicy] = field(default_factory=list)
    total_policies_evaluated: int = 0

    # Recommended actions (consolidated and prioritized)
    recommended_actions: list[RecommendedAction] = field(default_factory=list)

    # Summary
    summary: str = ""
    overall_priority: ActionPriority = ActionPriority.NORMAL

    # Analysis metadata
    analysis_method: str = "llm-mcp"
    llm_provider: Optional[str] = None

    # Reasoning from LLM
    reasoning: str = ""

    # Performance
    analysis_duration_ms: Optional[int] = None
    tool_calls_made: int = 0

    # Raw LLM response (for debugging)
    raw_llm_response: Optional[str] = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def add_matched_policy(self, policy: MatchedPolicy):
        """Add a matched policy."""
        self.matched_policies.append(policy)
        # Add actions from the policy
        for action in policy.actions:
            action.source_policy_id = policy.policy_id
            action.source_policy_name = policy.policy_name
            self.recommended_actions.append(action)
        self._update_overall_priority()

    def _update_overall_priority(self):
        """Update overall priority based on highest action priority."""
        priority_order = [
            ActionPriority.IMMEDIATE,
            ActionPriority.HIGH,
            ActionPriority.NORMAL,
            ActionPriority.LOW,
            ActionPriority.DEFERRED,
        ]

        for priority in priority_order:
            if any(a.priority == priority for a in self.recommended_actions):
                self.overall_priority = priority
                break

    def get_actions_by_priority(self) -> dict[str, list[RecommendedAction]]:
        """Get actions grouped by priority."""
        result = {}
        for action in self.recommended_actions:
            priority = action.priority.value
            if priority not in result:
                result[priority] = []
            result[priority].append(action)
        return result

    def get_immediate_actions(self) -> list[RecommendedAction]:
        """Get actions that need immediate execution."""
        return [a for a in self.recommended_actions if a.priority == ActionPriority.IMMEDIATE]

    @classmethod
    def from_llm_response(cls, response_data: dict, **kwargs) -> "PolicyRecommendation":
        """Create from LLM response."""
        rec = cls(**kwargs)

        rec.summary = response_data.get("summary", "")
        rec.reasoning = response_data.get("reasoning", "")

        # Parse overall priority
        priority_str = response_data.get("overall_priority", "normal")
        try:
            rec.overall_priority = ActionPriority(priority_str.lower())
        except ValueError:
            rec.overall_priority = ActionPriority.NORMAL

        # Parse matched policies
        for policy_data in response_data.get("matched_policies", []):
            policy = MatchedPolicy(
                policy_id=policy_data.get("policy_id", ""),
                policy_name=policy_data.get("policy_name", ""),
                policy_type=policy_data.get("policy_type", ""),
                priority=policy_data.get("priority", 0),
                conditions_matched=policy_data.get("conditions_matched", []),
            )
            rec.matched_policies.append(policy)

        # Parse recommended actions
        for action_data in response_data.get("recommended_actions", []):
            action = RecommendedAction.from_dict(action_data)
            rec.recommended_actions.append(action)

        return rec

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "diagnosis_id": self.diagnosis_id,
            "diagnosis_summary": self.diagnosis_summary,
            "issues_evaluated": self.issues_evaluated,
            "matched_policies": [p.to_dict() for p in self.matched_policies],
            "total_policies_evaluated": self.total_policies_evaluated,
            "recommended_actions": [a.to_dict() for a in self.recommended_actions],
            "summary": self.summary,
            "overall_priority": self.overall_priority.value,
            "analysis_method": self.analysis_method,
            "llm_provider": self.llm_provider,
            "reasoning": self.reasoning,
            "analysis_duration_ms": self.analysis_duration_ms,
            "tool_calls_made": self.tool_calls_made,
            "metadata": self.metadata,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        priority_emoji = {
            ActionPriority.IMMEDIATE: "🚨",
            ActionPriority.HIGH: "⚠️",
            ActionPriority.NORMAL: "📋",
            ActionPriority.LOW: "📝",
            ActionPriority.DEFERRED: "📅",
        }

        emoji = priority_emoji.get(self.overall_priority, "❓")

        lines = [
            f"{emoji} Policy Recommendation:  {self.id}",
            f"   Priority: {self.overall_priority.value.upper()}",
            f"   Diagnosis: {self.diagnosis_id}",
            f"   Issues Evaluated: {self.issues_evaluated}",
            f"   Policies Matched: {len(self.matched_policies)}",
            f"   Actions Recommended: {len(self.recommended_actions)}",
        ]

        if self.summary:
            lines.append(f"   Summary: {self.summary[: 80]}...")

        return "\n".join(lines)