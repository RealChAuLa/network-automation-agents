"""Tests for the policy manager."""

from datetime import timezone
import pytest
from unittest.mock import MagicMock
from datetime import datetime
from pathlib import Path
import tempfile

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.policies import PolicyManager
from src.models.policy import (
    Policy,
    PolicyType,
    PolicyStatus,
    PolicyAction,
    ActionType,
    Condition,
    ConditionOperator,
    ComplianceRule,
)


class TestPolicyManager:
    """Test cases for PolicyManager."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock Neo4j client."""
        client = MagicMock(spec=Neo4jClient)
        client.execute_write = MagicMock(return_value=[{"p": {}}])
        client.execute_read = MagicMock(return_value=[])
        return client
    
    @pytest.fixture
    def policy_mgr(self, mock_client):
        """Create PolicyManager with mock client."""
        return PolicyManager(mock_client)
    
    @pytest.fixture
    def sample_policy(self):
        """Create a sample policy."""
        return Policy(
            id="POL-TEST-001",
            name="Test Policy",
            description="A test policy",
            policy_type=PolicyType.REMEDIATION,
            status=PolicyStatus.ACTIVE,
            priority=10,
            conditions=[
                Condition(
                    field="anomaly_type",
                    operator=ConditionOperator.EQUALS,
                    value="HIGH_CPU",
                ),
                Condition(
                    field="severity",
                    operator=ConditionOperator.IN,
                    value=["critical", "high"],
                ),
            ],
            actions=[
                PolicyAction(
                    action_type=ActionType.RESTART_SERVICE,
                    target="affected_service",
                    parameters={"graceful": True},
                ),
            ],
            applies_to_node_types=["router_core"],
        )
    
    def test_create_policy(self, policy_mgr, sample_policy):
        """Test creating a policy."""
        result = policy_mgr.create_policy(sample_policy)
        
        policy_mgr.client.execute_write.assert_called()
    
    def test_get_policy_found(self, policy_mgr, mock_client):
        """Test getting a policy that exists."""
        import json
        mock_client.execute_read.return_value = [{
            "p": {
                "id": "POL-TEST-001",
                "name": "Test Policy",
                "description": "A test policy",
                "version": "1.0.0",
                "policy_type": "remediation",
                "status": "active",
                "priority": 10,
                "conditions": json. dumps([
                    {"field": "anomaly_type", "operator": "equals", "value": "HIGH_CPU"}
                ]),
                "actions": json.dumps([
                    {"action_type": "restart_service", "target": "test", "parameters": {}, "timeout_seconds": 300, "retry_count": 0, "requires_approval": False}
                ]),
                "applies_to_node_types": ["router_core"],
                "applies_to_locations": [],
                "active_hours_start": None,
                "active_hours_end": None,
                "active_days": [0, 1, 2, 3, 4, 5, 6],
                "tags": [],
            }
        }]
        
        policy = policy_mgr.get_policy("POL-TEST-001")
        
        assert policy is not None
        assert policy.id == "POL-TEST-001"
        assert policy.name == "Test Policy"
        assert len(policy.conditions) == 1
    
    def test_get_policy_not_found(self, policy_mgr, mock_client):
        """Test getting a policy that doesn't exist."""
        mock_client.execute_read.return_value = []
        
        policy = policy_mgr.get_policy("nonexistent")
        
        assert policy is None
    
    def test_evaluate_conditions_all_match(self, sample_policy):
        """Test condition evaluation when all conditions match."""
        context = {
            "anomaly_type": "HIGH_CPU",
            "severity": "critical",
        }
        
        result = sample_policy.evaluate_conditions(context)
        
        assert result is True
    
    def test_evaluate_conditions_partial_match(self, sample_policy):
        """Test condition evaluation when only some conditions match."""
        context = {
            "anomaly_type": "HIGH_CPU",
            "severity": "low",  # Not in ["critical", "high"]
        }
        
        result = sample_policy.evaluate_conditions(context)
        
        assert result is False
    
    def test_evaluate_conditions_no_match(self, sample_policy):
        """Test condition evaluation when no conditions match."""
        context = {
            "anomaly_type": "MEMORY_LEAK",
            "severity": "low",
        }
        
        result = sample_policy.evaluate_conditions(context)
        
        assert result is False
    
    def test_evaluate_conditions_empty(self):
        """Test condition evaluation with no conditions."""
        policy = Policy(
            name="Empty Policy",
            policy_type=PolicyType.REMEDIATION,
            conditions=[],
        )
        
        result = policy.evaluate_conditions({"any": "context"})
        
        assert result is True  # No conditions = always true
    
    def test_condition_operators(self):
        """Test various condition operators."""
        # EQUALS
        cond = Condition(field="status", operator=ConditionOperator. EQUALS, value="critical")
        assert cond.evaluate({"status": "critical"}) is True
        assert cond. evaluate({"status": "warning"}) is False
        
        # NOT_EQUALS
        cond = Condition(field="status", operator=ConditionOperator.NOT_EQUALS, value="healthy")
        assert cond.evaluate({"status": "critical"}) is True
        assert cond.evaluate({"status": "healthy"}) is False
        
        # GREATER_THAN
        cond = Condition(field="cpu", operator=ConditionOperator.GREATER_THAN, value=90)
        assert cond.evaluate({"cpu": 95}) is True
        assert cond.evaluate({"cpu": 85}) is False
        
        # LESS_THAN
        cond = Condition(field="cpu", operator=ConditionOperator.LESS_THAN, value=50)
        assert cond.evaluate({"cpu": 45}) is True
        assert cond.evaluate({"cpu": 55}) is False
        
        # GREATER_THAN_OR_EQUAL
        cond = Condition(field="cpu", operator=ConditionOperator. GREATER_THAN_OR_EQUAL, value=90)
        assert cond.evaluate({"cpu": 90}) is True
        assert cond.evaluate({"cpu": 89}) is False
        
        # LESS_THAN_OR_EQUAL
        cond = Condition(field="cpu", operator=ConditionOperator. LESS_THAN_OR_EQUAL, value=50)
        assert cond.evaluate({"cpu": 50}) is True
        assert cond.evaluate({"cpu": 51}) is False
        
        # IN
        cond = Condition(field="type", operator=ConditionOperator.IN, value=["router", "switch"])
        assert cond.evaluate({"type": "router"}) is True
        assert cond.evaluate({"type": "server"}) is False
        
        # NOT_IN
        cond = Condition(field="type", operator=ConditionOperator.NOT_IN, value=["router", "switch"])
        assert cond.evaluate({"type": "server"}) is True
        assert cond. evaluate({"type": "router"}) is False
        
        # CONTAINS
        cond = Condition(field="message", operator=ConditionOperator. CONTAINS, value="error")
        assert cond.evaluate({"message": "An error occurred"}) is True
        assert cond.evaluate({"message": "All good"}) is False
        
        # NOT_CONTAINS
        cond = Condition(field="message", operator=ConditionOperator.NOT_CONTAINS, value="error")
        assert cond.evaluate({"message": "All good"}) is True
        assert cond.evaluate({"message": "An error occurred"}) is False
    
    def test_condition_missing_field(self):
        """Test condition with missing field returns False."""
        cond = Condition(field="missing", operator=ConditionOperator.EQUALS, value="test")
        
        result = cond.evaluate({"other_field": "value"})
        
        assert result is False
    
    def test_policy_is_active_at(self, sample_policy):
        """Test checking if policy is active at a given time."""
        # Active policy should return True
        result = sample_policy. is_active_at(datetime.now(timezone.utc))
        assert result is True
        
        # Inactive policy should return False
        sample_policy.status = PolicyStatus.INACTIVE
        result = sample_policy.is_active_at(datetime.now(timezone.utc))
        assert result is False
    
    def test_policy_is_active_at_with_hours(self):
        """Test policy with active hours restriction."""
        policy = Policy(
            name="Business Hours Policy",
            policy_type=PolicyType.REMEDIATION,
            active_hours_start=9,
            active_hours_end=17,
            active_days=[0, 1, 2, 3, 4],  # Monday-Friday
        )
        
        # Create a datetime at 10:00 on a Monday
        weekday_business = datetime(2025, 12, 1, 10, 0, 0)  # Monday
        assert policy.is_active_at(weekday_business) is True
        
        # Create a datetime at 20:00 on a Monday (outside hours)
        weekday_evening = datetime(2025, 12, 1, 20, 0, 0)
        assert policy.is_active_at(weekday_evening) is False
    
    def test_policy_applies_to_node(self, sample_policy):
        """Test checking if policy applies to a node."""
        # Should apply to router_core
        assert sample_policy.applies_to_node("router_core", "datacenter-1") is True
        
        # Should not apply to server
        assert sample_policy.applies_to_node("server", "datacenter-1") is False
    
    def test_policy_applies_to_all_nodes(self):
        """Test policy that applies to all node types."""
        policy = Policy(
            name="Universal Policy",
            policy_type=PolicyType. REMEDIATION,
            applies_to_node_types=[],  # Empty = all
        )
        
        assert policy.applies_to_node("router_core", "dc1") is True
        assert policy.applies_to_node("server", "dc1") is True
        assert policy. applies_to_node("anything", "anywhere") is True
    
    def test_policy_applies_to_location(self):
        """Test policy with location restrictions."""
        policy = Policy(
            name="DC1 Only Policy",
            policy_type=PolicyType.REMEDIATION,
            applies_to_locations=["datacenter-1"],
        )
        
        assert policy.applies_to_node("router_core", "datacenter-1") is True
        assert policy.applies_to_node("router_core", "datacenter-2") is False
    
    def test_load_policies_from_yaml(self, policy_mgr):
        """Test loading policies from YAML file."""
        yaml_content = '''
policies:
  - id: POL-YAML-001
    name: YAML Test Policy
    description: Loaded from YAML
    policy_type: remediation
    status: active
    priority: 10
    conditions:
      - field: anomaly_type
        operator: equals
        value: HIGH_CPU
    actions:
      - action_type: restart_service
        target: test_service
    tags:
      - test
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            count = policy_mgr.load_policies_from_yaml(temp_path)
            assert count == 1
            policy_mgr.client. execute_write.assert_called()
        finally:
            Path(temp_path). unlink()
    
    def test_load_policies_file_not_found(self, policy_mgr):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            policy_mgr. load_policies_from_yaml("nonexistent.yaml")
    
    def test_get_policy_summary(self, policy_mgr, mock_client):
        """Test getting policy summary."""
        mock_client.execute_read.return_value = [{
            "total": 10,
            "active": 8,
            "types": ["remediation", "escalation", "compliance"],
        }]
        
        summary = policy_mgr.get_policy_summary()
        
        assert summary["total"] == 10
        assert summary["active"] == 8
        assert "remediation" in summary["types"]
    
    def test_update_policy_status(self, policy_mgr, mock_client):
        """Test updating policy status."""
        mock_client. execute_write.return_value = [{"p": {"id": "POL-001"}}]
        
        result = policy_mgr.update_policy_status("POL-001", PolicyStatus.INACTIVE)
        
        assert result is True
    
    def test_delete_policy(self, policy_mgr, mock_client):
        """Test deleting a policy."""
        mock_client.execute_write.return_value = [{"deleted": 1}]
        
        result = policy_mgr.delete_policy("POL-001")
        
        assert result is True


class TestComplianceRule:
    """Test cases for ComplianceRule."""
    
    def test_create_compliance_rule(self):
        """Test creating a compliance rule."""
        rule = ComplianceRule(
            name="Test Rule",
            regulation="SOC2",
            check_type="approval_required",
            parameters={"approvers": ["admin"]},
        )
        
        assert rule.id. startswith("COMP-")
        assert rule.name == "Test Rule"
        assert rule.regulation == "SOC2"
    
    def test_compliance_rule_defaults(self):
        """Test compliance rule default values."""
        rule = ComplianceRule(
            name="Minimal Rule",
            regulation="INTERNAL",
            check_type="test",
        )
        
        assert rule.severity == "medium"
        assert rule.enforcement == "block"
        assert rule.parameters == {}
        assert rule.tags == []


class TestPolicyAction:
    """Test cases for PolicyAction."""
    
    def test_create_action(self):
        """Test creating a policy action."""
        action = PolicyAction(
            action_type=ActionType.RESTART_SERVICE,
            target="my_service",
            parameters={"graceful": True},
        )
        
        assert action.action_type == ActionType. RESTART_SERVICE
        assert action.target == "my_service"
        assert action.parameters["graceful"] is True
    
    def test_action_defaults(self):
        """Test action default values."""
        action = PolicyAction(
            action_type=ActionType.LOG_ONLY,
        )
        
        assert action.target is None
        assert action.parameters == {}
        assert action.timeout_seconds == 300
        assert action.retry_count == 0
        assert action.requires_approval is False