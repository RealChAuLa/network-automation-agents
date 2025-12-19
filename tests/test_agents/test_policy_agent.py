"""Tests for the Policy Agent."""

import pytest
from datetime import datetime

from src.agents.policy.agent import PolicyAgent
from src.agents.policy.models import (
    PolicyRecommendation,
    RecommendedAction,
    MatchedPolicy,
    ActionPriority,
    ActionStatus,
)
from src.agents.discovery.models import (
    DiagnosisReport,
    DetectedIssue,
    IssueSeverity,
    IssueType,
)


class TestRecommendedAction:
    """Test cases for RecommendedAction model."""

    def test_create_action(self):
        """Test creating a recommended action."""
        action = RecommendedAction(
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
            priority=ActionPriority.HIGH,
            reason="High CPU detected",
        )

        assert action.action_type == "restart_service"
        assert action.priority == ActionPriority.HIGH
        assert action.status == ActionStatus.PENDING
        assert action.id.startswith("action_")

    def test_action_from_dict(self):
        """Test creating action from dictionary."""
        data = {
            "action_type": "restart_service",
            "target_node_id": "router_01",
            "target_node_name": "Router 1",
            "priority": "immediate",
            "reason": "Critical issue",
        }

        action = RecommendedAction.from_dict(data)

        assert action.action_type == "restart_service"
        assert action.priority == ActionPriority.IMMEDIATE

    def test_action_to_dict(self):
        """Test converting action to dictionary."""
        action = RecommendedAction(
            action_type="failover",
            target_node_id="node_01",
            priority=ActionPriority.IMMEDIATE,
        )

        data = action.to_dict()

        assert data["action_type"] == "failover"
        assert data["priority"] == "immediate"
        assert data["status"] == "pending"


class TestPolicyRecommendation:
    """Test cases for PolicyRecommendation model."""

    def test_create_recommendation(self):
        """Test creating a policy recommendation."""
        rec = PolicyRecommendation(
            diagnosis_id="diag_123",
            issues_evaluated=3,
        )

        assert rec.diagnosis_id == "diag_123"
        assert rec.issues_evaluated == 3
        assert rec.id.startswith("rec_")
        assert rec.overall_priority == ActionPriority.NORMAL

    def test_add_matched_policy(self):
        """Test adding a matched policy."""
        rec = PolicyRecommendation()

        policy = MatchedPolicy(
            policy_id="POL-001",
            policy_name="Test Policy",
            actions=[
                RecommendedAction(
                    action_type="restart_service",
                    priority=ActionPriority.HIGH,
                )
            ],
        )

        rec.add_matched_policy(policy)

        assert len(rec.matched_policies) == 1
        assert len(rec.recommended_actions) == 1
        assert rec.recommended_actions[0].source_policy_id == "POL-001"

    def test_overall_priority_updates(self):
        """Test that overall priority reflects highest action priority."""
        rec = PolicyRecommendation()

        # Add normal priority action
        rec.recommended_actions.append(
            RecommendedAction(priority=ActionPriority.NORMAL)
        )
        rec._update_overall_priority()
        assert rec.overall_priority == ActionPriority.NORMAL

        # Add immediate priority action
        rec.recommended_actions.append(
            RecommendedAction(priority=ActionPriority.IMMEDIATE)
        )
        rec._update_overall_priority()
        assert rec.overall_priority == ActionPriority.IMMEDIATE

    def test_get_immediate_actions(self):
        """Test getting immediate priority actions."""
        rec = PolicyRecommendation()
        rec.recommended_actions = [
            RecommendedAction(action_type="action1", priority=ActionPriority.IMMEDIATE),
            RecommendedAction(action_type="action2", priority=ActionPriority.NORMAL),
            RecommendedAction(action_type="action3", priority=ActionPriority.IMMEDIATE),
        ]

        immediate = rec.get_immediate_actions()

        assert len(immediate) == 2
        assert all(a.priority == ActionPriority.IMMEDIATE for a in immediate)

    def test_from_llm_response(self):
        """Test creating recommendation from LLM response."""
        response = {
            "summary": "Test summary",
            "reasoning": "Test reasoning",
            "overall_priority": "high",
            "matched_policies": [
                {"policy_id": "POL-001", "policy_name": "Policy 1"}
            ],
            "recommended_actions": [
                {
                    "action_type": "restart_service",
                    "target_node_id": "node_01",
                    "priority": "immediate",
                    "reason": "Fix issue",
                }
            ],
        }

        rec = PolicyRecommendation.from_llm_response(response)

        assert rec.summary == "Test summary"
        assert rec.overall_priority == ActionPriority.HIGH
        assert len(rec.matched_policies) == 1
        assert len(rec.recommended_actions) == 1

    def test_get_summary(self):
        """Test getting recommendation summary."""
        rec = PolicyRecommendation(
            diagnosis_id="diag_123",
            issues_evaluated=2,
            overall_priority=ActionPriority.HIGH,
        )
        rec.matched_policies = [MatchedPolicy(policy_id="POL-001")]
        rec.recommended_actions = [RecommendedAction()]

        summary = rec.get_summary()

        assert "HIGH" in summary
        assert "diag_123" in summary
        assert "Policies Matched: 1" in summary


class TestPolicyAgent:
    """Test cases for PolicyAgent."""

    @pytest.fixture
    def agent(self):
        """Create policy agent."""
        return PolicyAgent()

    @pytest.fixture
    def sample_diagnosis(self):
        """Create a sample diagnosis report."""
        diagnosis = DiagnosisReport(
            scope="network-wide",
            nodes_analyzed=5,
        )

        issue = DetectedIssue(
            issue_type=IssueType.HIGH_CPU,
            severity=IssueSeverity.CRITICAL,
            node_id="router_core_01",
            node_name="core-rtr-01",
            node_type="router_core",
            current_value=95.0,
            description="High CPU detected",
        )
        diagnosis.add_issue(issue)

        return diagnosis

    @pytest.mark.asyncio
    async def test_evaluate_returns_result(self, agent, sample_diagnosis):
        """Test that evaluate returns an AgentResult."""
        result = await agent.evaluate(sample_diagnosis, use_llm=False)

        assert result is not None
        assert result.agent_name == "policy"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_evaluate_creates_recommendation(self, agent, sample_diagnosis):
        """Test that evaluate creates a PolicyRecommendation."""
        result = await agent.evaluate(sample_diagnosis, use_llm=False)

        rec = result.result
        assert isinstance(rec, PolicyRecommendation)
        assert rec.diagnosis_id == sample_diagnosis.id
        assert rec.issues_evaluated == 1

    @pytest.mark.asyncio
    async def test_evaluate_no_issues(self, agent):
        """Test evaluation with no issues."""
        diagnosis = DiagnosisReport(scope="test", nodes_analyzed=5)
        # No issues added

        result = await agent.evaluate(diagnosis, use_llm=False)

        assert result.success is True
        assert len(result.result.recommended_actions) == 0
        assert "No issues" in result.result.summary or "no actions" in result.result.summary.lower()

    @pytest.mark.asyncio
    async def test_evaluate_single_issue(self, agent):
        """Test evaluating a single issue directly."""
        result = await agent.evaluate_single_issue(
            issue_type="HIGH_CPU",
            severity="critical",
            node_id="router_core_01",
            node_type="router_core",
        )

        assert result.success is True
        assert result.result.issues_evaluated == 1

    @pytest.mark.asyncio
    async def test_get_all_policies(self, agent):
        """Test getting all policies."""
        policies = await agent.get_all_policies()

        assert isinstance(policies, list)
        # Should have policies from our setup
        if policies:
            assert "id" in policies[0]
            assert "name" in policies[0]

    def test_determine_priority(self, agent):
        """Test priority determination from severity."""
        assert agent._determine_priority("critical") == ActionPriority.IMMEDIATE
        assert agent._determine_priority("high") == ActionPriority.HIGH
        assert agent._determine_priority("medium") == ActionPriority.NORMAL
        assert agent._determine_priority("low") == ActionPriority.LOW


class TestIntegration:
    """Integration tests for Discovery + Policy agents."""

    @pytest.mark.asyncio
    async def test_discovery_to_policy_flow(self):
        """Test the flow from discovery to policy evaluation."""
        from src.agents.discovery import DiscoveryAgent

        # Run discovery
        discovery = DiscoveryAgent()
        discovery_result = await discovery.run(use_llm=False)

        assert discovery_result.success is True
        diagnosis = discovery_result.result

        # Run policy evaluation
        policy = PolicyAgent()
        policy_result = await policy.evaluate(diagnosis, use_llm=False)

        assert policy_result.success is True
        recommendation = policy_result.result

        assert recommendation.diagnosis_id == diagnosis.id