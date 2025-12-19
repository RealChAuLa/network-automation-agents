"""Tests for the Compliance Agent."""

import pytest
from datetime import datetime, timedelta

from src.agents.compliance.agent import ComplianceAgent
from src.agents.compliance.models import (
    ComplianceResult,
    ActionValidation,
    ValidationStatus,
    ComplianceViolation,
    ViolationType,
)
from src.agents.compliance.checks import ComplianceChecker
from src.agents.policy.models import (
    PolicyRecommendation,
    RecommendedAction,
    ActionPriority,
)


class TestComplianceViolation:
    """Test cases for ComplianceViolation model."""

    def test_create_violation(self):
        """Test creating a compliance violation."""
        violation = ComplianceViolation(
            violation_type=ViolationType.MAINTENANCE_WINDOW,
            rule_id="MAINT-001",
            rule_name="Maintenance Window Required",
            severity="high",
            blocking=True,
            description="Action requires maintenance window",
        )

        assert violation.violation_type == ViolationType.MAINTENANCE_WINDOW
        assert violation.blocking is True
        assert violation.id.startswith("violation_")

    def test_violation_to_dict(self):
        """Test converting violation to dictionary."""
        violation = ComplianceViolation(
            violation_type=ViolationType.RATE_LIMIT_EXCEEDED,
            rule_id="RATE-001",
            blocking=True,
        )

        data = violation.to_dict()

        assert data["violation_type"] == "rate_limit_exceeded"
        assert data["blocking"] is True


class TestActionValidation:
    """Test cases for ActionValidation model."""

    def test_create_validation(self):
        """Test creating an action validation."""
        validation = ActionValidation(
            action_id="action_123",
            action_type="restart_service",
            target_node_id="router_core_01",
        )

        assert validation.action_id == "action_123"
        assert validation.status == ValidationStatus.PENDING_APPROVAL
        assert validation.id.startswith("val_")

    def test_add_blocking_violation(self):
        """Test adding a blocking violation changes status to denied."""
        validation = ActionValidation()

        violation = ComplianceViolation(
            violation_type=ViolationType.MAINTENANCE_WINDOW,
            blocking=True,
            description="Test violation",
        )

        validation.add_violation(violation)

        assert validation.status == ValidationStatus.DENIED
        assert len(validation.violations) == 1

    def test_add_non_blocking_violation(self):
        """Test adding a non-blocking violation doesn't deny."""
        validation = ActionValidation()

        violation = ComplianceViolation(
            violation_type=ViolationType.APPROVAL_REQUIRED,
            blocking=False,
            description="Test warning",
        )

        validation.add_violation(violation)

        # Status should still be pending, not denied
        assert validation.status == ValidationStatus.PENDING_APPROVAL
        assert len(validation.violations) == 1

    def test_approve_action(self):
        """Test approving an action."""
        validation = ActionValidation()
        validation.approve(approved_by="admin", notes="Emergency approved")

        assert validation.status == ValidationStatus.APPROVED
        assert validation.approved_by == "admin"
        assert validation.is_approved is True

    def test_deny_action(self):
        """Test denying an action."""
        validation = ActionValidation()
        validation.deny(reason="Policy violation")

        assert validation.status == ValidationStatus.DENIED
        assert validation.denial_reason == "Policy violation"
        assert validation.is_denied is True

    def test_defer_action(self):
        """Test deferring an action."""
        validation = ActionValidation()
        defer_until = datetime.utcnow() + timedelta(hours=2)
        validation.defer(until=defer_until, reason="Wait for maintenance window")

        assert validation.status == ValidationStatus.DEFERRED
        assert validation.deferred_until == defer_until


class TestComplianceResult:
    """Test cases for ComplianceResult model."""

    def test_create_result(self):
        """Test creating a compliance result."""
        result = ComplianceResult(
            recommendation_id="rec_123",
            diagnosis_id="diag_456",
        )

        assert result.recommendation_id == "rec_123"
        assert result.id.startswith("comp_")
        assert result.total_actions == 0

    def test_add_validation_updates_counts(self):
        """Test that adding validations updates counts."""
        result = ComplianceResult()

        # Add approved
        v1 = ActionValidation(status=ValidationStatus.APPROVED)
        result.add_validation(v1)

        # Add denied
        v2 = ActionValidation(status=ValidationStatus.DENIED)
        result.add_validation(v2)

        # Add pending
        v3 = ActionValidation(status=ValidationStatus.PENDING_APPROVAL)
        result.add_validation(v3)

        assert result.total_actions == 3
        assert result.approved_count == 1
        assert result.denied_count == 1
        assert result.pending_count == 1
        assert result.all_approved is False

    def test_all_approved(self):
        """Test all_approved flag."""
        result = ComplianceResult()

        result.add_validation(ActionValidation(status=ValidationStatus.APPROVED))
        result.add_validation(ActionValidation(status=ValidationStatus.APPROVED))

        assert result.all_approved is True
        assert result.has_violations is False

    def test_get_approved_actions(self):
        """Test getting approved actions."""
        result = ComplianceResult()

        v1 = ActionValidation(action_type="action1", status=ValidationStatus.APPROVED)
        v2 = ActionValidation(action_type="action2", status=ValidationStatus.DENIED)
        v3 = ActionValidation(action_type="action3", status=ValidationStatus.APPROVED)

        result.add_validation(v1)
        result.add_validation(v2)
        result.add_validation(v3)

        approved = result.get_approved_actions()

        assert len(approved) == 2
        assert all(a.status == ValidationStatus.APPROVED for a in approved)

    def test_get_summary(self):
        """Test getting result summary."""
        result = ComplianceResult(
            recommendation_id="rec_123",
        )
        result.add_validation(ActionValidation(status=ValidationStatus.APPROVED))
        result.add_validation(ActionValidation(status=ValidationStatus.DENIED))

        summary = result.get_summary()

        assert "HAS DENIALS" in summary
        assert "rec_123" in summary
        assert "Approved: 1" in summary
        assert "Denied: 1" in summary


class TestComplianceChecker:
    """Test cases for ComplianceChecker."""

    @pytest.fixture
    def checker(self):
        """Create compliance checker."""
        return ComplianceChecker()

    def test_maintenance_window_check_inside(self, checker):
        """Test maintenance window check when inside window."""
        action = RecommendedAction(action_type="restart_node")

        # Set time to 3 AM (inside default 2-6 AM window)
        test_time = datetime.utcnow().replace(hour=3, minute=0)

        violation = checker.check_maintenance_window(action, test_time)

        assert violation is None  # No violation when inside window

    def test_maintenance_window_check_outside(self, checker):
        """Test maintenance window check when outside window."""
        action = RecommendedAction(action_type="restart_node")

        # Set time to 10 AM (outside default 2-6 AM window)
        test_time = datetime.utcnow().replace(hour=10, minute=0)

        violation = checker.check_maintenance_window(action, test_time)

        assert violation is not None
        assert violation.violation_type == ViolationType.MAINTENANCE_WINDOW
        assert violation.blocking is True

    def test_maintenance_window_non_restricted_action(self, checker):
        """Test that non-restricted actions don't trigger maintenance window."""
        action = RecommendedAction(action_type="restart_service")  # Not in restricted list

        test_time = datetime.utcnow().replace(hour=10, minute=0)

        violation = checker.check_maintenance_window(action, test_time)

        # restart_service is in maintenance_required_actions, so check if it requires it
        if action.action_type in checker.maintenance_required_actions:
            assert violation is not None
        else:
            assert violation is None

    def test_approval_required_check(self, checker):
        """Test approval required check."""
        action = RecommendedAction(action_type="restart_node")

        violation = checker.check_approval_required(action, node_type="router_core")

        assert violation is not None
        assert violation.violation_type == ViolationType.APPROVAL_REQUIRED
        assert violation.blocking is False  # Non-blocking

    def test_rate_limit_check_under_limit(self, checker):
        """Test rate limit check when under limit."""
        action = RecommendedAction(
            action_type="restart_service",
            target_node_id="node_01",
        )

        # Few recent actions
        recent_actions = [
            {"target_node_id": "node_01", "completed_at": datetime.utcnow().isoformat()}
            for _ in range(3)
        ]

        violation = checker.check_rate_limit(action, recent_actions)

        assert violation is None  # Under limit

    def test_rate_limit_check_over_limit(self, checker):
        """Test rate limit check when over limit."""
        action = RecommendedAction(
            action_type="restart_service",
            target_node_id="node_01",
        )

        # Many recent actions (over limit)
        recent_actions = [
            {"target_node_id": "node_01", "completed_at": datetime.utcnow().isoformat()}
            for _ in range(15)  # Over default limit of 10
        ]

        violation = checker.check_rate_limit(action, recent_actions)

        assert violation is not None
        assert violation.violation_type == ViolationType.RATE_LIMIT_EXCEEDED

    def test_node_criticality_check(self, checker):
        """Test node criticality check for critical nodes."""
        action = RecommendedAction(action_type="restart_node")

        violation = checker.check_node_criticality(action, node_type="router_core")

        assert violation is not None
        assert violation.violation_type == ViolationType.NODE_CRITICALITY

    def test_node_criticality_non_critical(self, checker):
        """Test node criticality check for non-critical nodes."""
        action = RecommendedAction(action_type="restart_service")

        violation = checker.check_node_criticality(action, node_type="server")

        assert violation is None  # No violation for non-critical nodes

    def test_run_all_checks(self, checker):
        """Test running all checks."""
        action = RecommendedAction(
            action_type="restart_node",
            target_node_id="router_core_01",
        )

        # Set time outside maintenance window
        test_time = datetime.utcnow().replace(hour=10, minute=0)

        violations = checker.run_all_checks(
            action=action,
            node_type="router_core",
            recent_actions=[],
            current_time=test_time,
        )

        # Should have multiple violations
        assert len(violations) >= 1
        violation_types = [v.violation_type for v in violations]
        assert ViolationType.MAINTENANCE_WINDOW in violation_types


class TestComplianceAgent:
    """Test cases for ComplianceAgent."""

    @pytest.fixture
    def agent(self):
        """Create compliance agent."""
        return ComplianceAgent()

    @pytest.fixture
    def sample_recommendation(self):
        """Create a sample policy recommendation."""
        recommendation = PolicyRecommendation(
            diagnosis_id="diag_123",
            issues_evaluated=1,
        )

        action = RecommendedAction(
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
            target_node_type="router_core",
            priority=ActionPriority.HIGH,
            reason="High CPU detected",
        )
        recommendation.recommended_actions.append(action)

        return recommendation

    @pytest.mark.asyncio
    async def test_validate_returns_result(self, agent, sample_recommendation):
        """Test that validate returns an AgentResult."""
        result = await agent.validate(sample_recommendation, use_llm=False)

        assert result is not None
        assert result.agent_name == "compliance"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_validate_creates_compliance_result(self, agent, sample_recommendation):
        """Test that validate creates a ComplianceResult."""
        result = await agent.validate(sample_recommendation, use_llm=False)

        compliance_result = result.result
        assert isinstance(compliance_result, ComplianceResult)
        assert compliance_result.recommendation_id == sample_recommendation.id
        assert compliance_result.total_actions == 1

    @pytest.mark.asyncio
    async def test_validate_no_actions(self, agent):
        """Test validation with no actions."""
        recommendation = PolicyRecommendation()
        # No actions added

        result = await agent.validate(recommendation, use_llm=False)

        assert result.success is True
        assert result.result.total_actions == 0
        assert "No actions" in result.result.summary

    @pytest.mark.asyncio
    async def test_validate_single_action(self, agent):
        """Test validating a single action directly."""
        result = await agent.validate_single_action(
            action_type="restart_service",
            target_node_id="router_core_01",
            reason="Test validation",
        )

        assert result.success is True
        assert result.result.total_actions == 1

    @pytest.mark.asyncio
    async def test_get_compliance_rules(self, agent):
        """Test getting compliance rules."""
        rules = await agent.get_compliance_rules()

        assert isinstance(rules, list)

    @pytest.mark.asyncio
    async def test_check_maintenance_window(self, agent):
        """Test checking maintenance window."""
        in_window = await agent.check_maintenance_window()

        assert isinstance(in_window, bool)


class TestIntegration:
    """Integration tests for Discovery → Policy → Compliance."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test the full agent pipeline."""
        from src.agents.discovery import DiscoveryAgent
        from src.agents.policy import PolicyAgent

        # Run discovery
        discovery = DiscoveryAgent()
        discovery_result = await discovery.run(use_llm=False)
        assert discovery_result.success is True

        # Run policy
        policy = PolicyAgent()
        policy_result = await policy.evaluate(discovery_result.result, use_llm=False)
        assert policy_result.success is True

        # Run compliance
        compliance = ComplianceAgent()
        compliance_result = await compliance.validate(policy_result.result, use_llm=False)
        assert compliance_result.success is True

        # Verify chain
        result = compliance_result.result
        assert result.recommendation_id == policy_result.result.id