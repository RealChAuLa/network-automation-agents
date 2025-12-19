"""
Compliance Checks

Implementation of various compliance checks.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.agents.compliance.models import (
    ComplianceViolation,
    ViolationType,
)
from src.agents.policy.models import RecommendedAction

logger = logging.getLogger(__name__)


class ComplianceChecker:
    """
    Performs various compliance checks on recommended actions.
    """

    def __init__(self):
        """Initialize the compliance checker."""
        # Action rate tracking (in-memory for now)
        self._action_history: list[dict] = []

        # Configuration
        self.maintenance_window_start = 2  # 2 AM UTC
        self.maintenance_window_end = 6  # 6 AM UTC
        self.rate_limit_per_hour = 10  # Max actions per hour per node
        self.critical_node_types = ["router_core", "firewall", "load_balancer"]

        # Actions requiring maintenance window
        self.maintenance_required_actions = [
            "restart_node",
            "failover",
            "update_config",
            "firmware_upgrade",
        ]

        # Actions requiring approval
        self.approval_required_actions = [
            "restart_node",
            "failover",
            "block_traffic",
            "update_config",
        ]

    def check_maintenance_window(
            self,
            action: RecommendedAction,
            current_time: Optional[datetime] = None,
    ) -> Optional[ComplianceViolation]:
        """
        Check if action requires maintenance window and if we're in one.

        Args:
            action: The action to check
            current_time:  Current time (defaults to now)

        Returns:
            ComplianceViolation if outside maintenance window, None otherwise
        """
        current_time = current_time or datetime.utcnow()
        current_hour = current_time.hour

        # Check if this action requires maintenance window
        if action.action_type not in self.maintenance_required_actions:
            return None

        # Check if we're in maintenance window
        in_window = self.maintenance_window_start <= current_hour < self.maintenance_window_end

        if not in_window:
            # Calculate next maintenance window
            if current_hour >= self.maintenance_window_end:
                next_window = current_time.replace(
                    hour=self.maintenance_window_start,
                    minute=0,
                    second=0
                ) + timedelta(days=1)
            else:
                next_window = current_time.replace(
                    hour=self.maintenance_window_start,
                    minute=0,
                    second=0
                )

            return ComplianceViolation(
                violation_type=ViolationType.MAINTENANCE_WINDOW,
                rule_id="MAINT-001",
                rule_name="Maintenance Window Required",
                severity="high",
                blocking=True,
                description=f"Action '{action.action_type}' requires maintenance window",
                reason=f"Current time ({current_hour}: 00 UTC) is outside maintenance window ({self.maintenance_window_start}:00-{self.maintenance_window_end}:00 UTC)",
                resolution_options=[
                    f"Wait until next maintenance window:  {next_window.strftime('%Y-%m-%d %H:%M UTC')}",
                    "Request emergency change approval",
                    "Defer action to maintenance window",
                ],
                can_override=True,
                override_requires="emergency_change_approval",
            )

        return None

    def check_approval_required(
            self,
            action: RecommendedAction,
            node_type: str = "",
    ) -> Optional[ComplianceViolation]:
        """
        Check if action requires human approval.

        Args:
            action: The action to check
            node_type: Type of the target node

        Returns:
            ComplianceViolation if approval required, None otherwise
        """
        needs_approval = False
        approval_level = "operator"

        # Check if action type requires approval
        if action.action_type in self.approval_required_actions:
            needs_approval = True
            approval_level = "operator"

        # Critical nodes require higher approval
        if node_type in self.critical_node_types:
            needs_approval = True
            approval_level = "manager"

        # Check if action already has approval flag
        if action.requires_approval:
            needs_approval = True

        if needs_approval:
            return ComplianceViolation(
                violation_type=ViolationType.APPROVAL_REQUIRED,
                rule_id="APPR-001",
                rule_name="Human Approval Required",
                severity="medium",
                blocking=False,  # Non-blocking, but needs tracking
                description=f"Action '{action.action_type}' requires {approval_level} approval",
                reason=f"This action type or target node requires human verification",
                resolution_options=[
                    f"Obtain {approval_level} approval",
                    "Document justification for automated execution",
                ],
                can_override=False,
                metadata={"approval_level": approval_level},
            )

        return None

    def check_rate_limit(
            self,
            action: RecommendedAction,
            recent_actions: list[dict] = None,
    ) -> Optional[ComplianceViolation]:
        """
        Check if action would exceed rate limits.

        Args:
            action: The action to check
            recent_actions: Recent actions from execution history

        Returns:
            ComplianceViolation if rate limit exceeded, None otherwise
        """
        recent_actions = recent_actions or []

        # Count actions on same node in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        node_actions = [
            a for a in recent_actions
            if a.get("target_node_id") == action.target_node_id
               and datetime.fromisoformat(a.get("completed_at", "2000-01-01")) > one_hour_ago
        ]

        if len(node_actions) >= self.rate_limit_per_hour:
            return ComplianceViolation(
                violation_type=ViolationType.RATE_LIMIT_EXCEEDED,
                rule_id="RATE-001",
                rule_name="Action Rate Limit",
                severity="medium",
                blocking=True,
                description=f"Rate limit exceeded for node '{action.target_node_id}'",
                reason=f"Node has had {len(node_actions)} actions in the last hour (limit: {self.rate_limit_per_hour})",
                resolution_options=[
                    "Wait for rate limit window to reset",
                    "Request rate limit override",
                    "Investigate why so many actions are needed",
                ],
                can_override=True,
                override_requires="operator_approval",
            )

        return None

    def check_node_criticality(
            self,
            action: RecommendedAction,
            node_type: str = "",
    ) -> Optional[ComplianceViolation]:
        """
        Check for actions on critical nodes.

        Args:
            action: The action to check
            node_type: Type of the target node

        Returns:
            ComplianceViolation if critical node rules violated, None otherwise
        """
        if node_type not in self.critical_node_types:
            return None

        # Certain actions are not allowed on critical nodes without extra approval
        high_risk_actions = ["restart_node", "failover", "block_traffic"]

        if action.action_type in high_risk_actions:
            return ComplianceViolation(
                violation_type=ViolationType.NODE_CRITICALITY,
                rule_id="CRIT-001",
                rule_name="Critical Node Protection",
                severity="high",
                blocking=False,  # Warning but allows with approval
                description=f"High-risk action on critical node type:  {node_type}",
                reason=f"Action '{action.action_type}' on '{node_type}' requires additional verification",
                resolution_options=[
                    "Verify impact assessment completed",
                    "Ensure rollback plan exists",
                    "Obtain dual authorization",
                ],
                can_override=True,
                override_requires="dual_authorization",
                metadata={"node_type": node_type, "risk_level": "high"},
            )

        return None

    def check_time_restriction(
            self,
            action: RecommendedAction,
            current_time: Optional[datetime] = None,
    ) -> Optional[ComplianceViolation]:
        """
        Check for time-based restrictions (e.g., no changes during business hours).

        Args:
            action: The action to check
            current_time: Current time (defaults to now)

        Returns:
            ComplianceViolation if time restricted, None otherwise
        """
        current_time = current_time or datetime.utcnow()
        current_hour = current_time.hour
        current_weekday = current_time.weekday()  # 0=Monday, 6=Sunday

        # Business hours:  9 AM - 5 PM UTC, Monday-Friday
        is_business_hours = (
                0 <= current_weekday <= 4 and  # Monday-Friday
                9 <= current_hour < 17  # 9 AM - 5 PM
        )

        # High-impact actions during business hours get a warning
        high_impact_actions = ["restart_node", "failover", "scale_down"]

        if is_business_hours and action.action_type in high_impact_actions:
            return ComplianceViolation(
                violation_type=ViolationType.TIME_RESTRICTION,
                rule_id="TIME-001",
                rule_name="Business Hours Restriction",
                severity="low",
                blocking=False,  # Warning only
                description=f"High-impact action during business hours",
                reason=f"Action '{action.action_type}' may impact users during peak hours",
                resolution_options=[
                    "Proceed with caution and monitoring",
                    "Defer to off-peak hours",
                    "Notify stakeholders before proceeding",
                ],
                can_override=True,
                override_requires="acknowledgment",
            )

        return None

    def check_change_freeze(
            self,
            action: RecommendedAction,
            current_time: Optional[datetime] = None,
    ) -> Optional[ComplianceViolation]:
        """
        Check for change freeze periods (e.g., end of quarter, holidays).

        Args:
            action: The action to check
            current_time: Current time (defaults to now)

        Returns:
            ComplianceViolation if in change freeze, None otherwise
        """
        current_time = current_time or datetime.utcnow()

        # Example: Change freeze during last week of each quarter
        # Q1: Mar 25-31, Q2: Jun 25-30, Q3: Sep 25-30, Q4: Dec 25-31
        freeze_periods = [
            (3, 25, 3, 31),  # End of Q1
            (6, 25, 6, 30),  # End of Q2
            (9, 25, 9, 30),  # End of Q3
            (12, 25, 12, 31),  # End of Q4 / Holidays
        ]

        current_month = current_time.month
        current_day = current_time.day

        for start_month, start_day, end_month, end_day in freeze_periods:
            if start_month == current_month and start_day <= current_day <= end_day:
                return ComplianceViolation(
                    violation_type=ViolationType.CHANGE_FREEZE,
                    rule_id="FREEZE-001",
                    rule_name="Change Freeze Period",
                    severity="high",
                    blocking=True,
                    description="System is in change freeze period",
                    reason=f"Changes are restricted from {start_month}/{start_day} to {end_month}/{end_day}",
                    resolution_options=[
                        "Wait until change freeze ends",
                        "Request emergency change exception",
                    ],
                    can_override=True,
                    override_requires="executive_approval",
                )

        return None

    def run_all_checks(
            self,
            action: RecommendedAction,
            node_type: str = "",
            recent_actions: list[dict] = None,
            current_time: Optional[datetime] = None,
    ) -> list[ComplianceViolation]:
        """
        Run all compliance checks on an action.

        Args:
            action: The action to check
            node_type: Type of the target node
            recent_actions: Recent actions for rate limiting
            current_time: Current time (defaults to now)

        Returns:
            List of violations found
        """
        violations = []

        # Run each check
        checks = [
            self.check_maintenance_window(action, current_time),
            self.check_approval_required(action, node_type),
            self.check_rate_limit(action, recent_actions),
            self.check_node_criticality(action, node_type),
            self.check_time_restriction(action, current_time),
            self.check_change_freeze(action, current_time),
        ]

        for violation in checks:
            if violation:
                violations.append(violation)

        return violations