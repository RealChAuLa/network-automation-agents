"""Tests for MCP server tools."""

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock

from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import NodeType, NodeStatus, MetricType, AnomalyType, AnomalySeverity


class TestTelemetryTools:
    """Test cases for telemetry tools."""

    @pytest.fixture
    def setup_simulator(self):
        """Set up simulator components."""
        network_sim = NetworkSimulator()
        network_sim.create_default_topology()
        log_gen = LogGenerator(network_sim)
        tel_gen = TelemetryGenerator(network_sim)
        anomaly_inj = AnomalyInjector(network_sim, tel_gen, log_gen)
        return network_sim, log_gen, tel_gen, anomaly_inj

    def test_log_generation(self, setup_simulator):
        """Test that logs can be generated."""
        network_sim, log_gen, _, _ = setup_simulator

        logs = log_gen.generate_batch(count=10, time_range_minutes=60)

        assert len(logs) == 10
        for log in logs:
            assert log.node_id is not None
            assert log.message is not None

    def test_metric_generation(self, setup_simulator):
        """Test that metrics can be generated."""
        network_sim, _, tel_gen, _ = setup_simulator

        node = network_sim.get_node("router_core_01")
        snapshot = tel_gen.generate_snapshot(node)

        assert snapshot is not None
        assert snapshot.node_id == "router_core_01"
        assert len(snapshot.metrics) > 0

    def test_all_node_metrics(self, setup_simulator):
        """Test metrics for all nodes."""
        network_sim, _, tel_gen, _ = setup_simulator

        snapshots = tel_gen.generate_all_snapshots()

        assert len(snapshots) == len(network_sim.get_all_nodes())

    def test_anomaly_injection(self, setup_simulator):
        """Test anomaly injection."""
        network_sim, _, tel_gen, anomaly_inj = setup_simulator

        anomaly = anomaly_inj.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.CRITICAL
        )

        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.HIGH_CPU
        assert anomaly.severity == AnomalySeverity.CRITICAL

        # Verify metrics are affected
        node = network_sim.get_node("router_core_01")
        snapshot = tel_gen.generate_snapshot(node)
        cpu_metric = snapshot.get_metric(MetricType.CPU_UTILIZATION)

        assert cpu_metric.value >= 95  # Critical HIGH_CPU should be 98%

    def test_anomaly_clearing(self, setup_simulator):
        """Test clearing anomalies."""
        _, _, _, anomaly_inj = setup_simulator

        anomaly = anomaly_inj.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.HIGH
        )

        assert len(anomaly_inj.get_active_anomalies()) == 1

        anomaly_inj.clear_anomaly(anomaly.id)

        assert len(anomaly_inj.get_active_anomalies()) == 0


class TestDiagnosisLogic:
    """Test diagnosis logic."""

    @pytest.fixture
    def setup_simulator(self):
        """Set up simulator components."""
        network_sim = NetworkSimulator()
        network_sim.create_default_topology()
        log_gen = LogGenerator(network_sim)
        tel_gen = TelemetryGenerator(network_sim)
        anomaly_inj = AnomalyInjector(network_sim, tel_gen, log_gen)
        return network_sim, log_gen, tel_gen, anomaly_inj

    def test_diagnosis_detects_high_cpu(self, setup_simulator):
        """Test that diagnosis detects high CPU."""
        network_sim, _, tel_gen, anomaly_inj = setup_simulator

        # Inject high CPU anomaly
        anomaly_inj.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.CRITICAL
        )

        # Get metrics
        node = network_sim.get_node("router_core_01")
        snapshot = tel_gen.generate_snapshot(node)

        # Check CPU is high
        cpu_metric = snapshot.get_metric(MetricType.CPU_UTILIZATION)
        assert cpu_metric.value > 90

        # Status should be critical
        assert snapshot.status == NodeStatus.CRITICAL

    def test_diagnosis_detects_packet_loss(self, setup_simulator):
        """Test that diagnosis detects packet loss."""
        network_sim, _, tel_gen, anomaly_inj = setup_simulator

        # Inject packet loss anomaly
        anomaly_inj.inject_anomaly(
            "router_core_01",
            AnomalyType.PACKET_LOSS,
            AnomalySeverity.HIGH
        )

        # Get metrics
        node = network_sim.get_node("router_core_01")
        snapshot = tel_gen.generate_snapshot(node)

        # Check packet loss is high
        loss_metric = snapshot.get_metric(MetricType.PACKET_LOSS)
        assert loss_metric.value > 5


class TestPolicyEvaluation:
    """Test policy evaluation logic."""

    def test_condition_evaluation(self):
        """Test policy condition evaluation."""
        from src.models.policy import Condition, ConditionOperator

        # Test equals
        cond = Condition(field="anomaly_type", operator=ConditionOperator.EQUALS, value="HIGH_CPU")
        assert cond.evaluate({"anomaly_type": "HIGH_CPU"}) is True
        assert cond.evaluate({"anomaly_type": "MEMORY_LEAK"}) is False

        # Test greater than
        cond = Condition(field="cpu", operator=ConditionOperator.GREATER_THAN, value=90)
        assert cond.evaluate({"cpu": 95}) is True
        assert cond.evaluate({"cpu": 85}) is False

        # Test IN
        cond = Condition(field="severity", operator=ConditionOperator.IN, value=["high", "critical"])
        assert cond.evaluate({"severity": "critical"}) is True
        assert cond.evaluate({"severity": "low"}) is False

    def test_policy_matching(self):
        """Test policy matching logic."""
        from src.models.policy import Policy, PolicyType, Condition, ConditionOperator, PolicyAction, ActionType

        policy = Policy(
            id="POL-TEST",
            name="Test Policy",
            policy_type=PolicyType.REMEDIATION,
            conditions=[
                Condition(field="anomaly_type", operator=ConditionOperator.EQUALS, value="HIGH_CPU"),
                Condition(field="severity", operator=ConditionOperator.IN, value=["high", "critical"]),
            ],
            actions=[
                PolicyAction(action_type=ActionType.RESTART_SERVICE),
            ]
        )

        # Should match
        context = {"anomaly_type": "HIGH_CPU", "severity": "critical"}
        assert policy.evaluate_conditions(context) is True

        # Should not match (wrong severity)
        context = {"anomaly_type": "HIGH_CPU", "severity": "low"}
        assert policy.evaluate_conditions(context) is False

        # Should not match (wrong type)
        context = {"anomaly_type": "MEMORY_LEAK", "severity": "critical"}
        assert policy.evaluate_conditions(context) is False


class TestExecutionSimulation:
    """Test execution simulation."""

    @pytest.fixture
    def setup_simulator(self):
        """Set up simulator."""
        network_sim = NetworkSimulator()
        network_sim.create_default_topology()
        return network_sim

    def test_node_status_update(self, setup_simulator):
        """Test that node status can be updated."""
        network_sim = setup_simulator

        # Initial status should be healthy
        node = network_sim.get_node("router_core_01")
        assert node.status == NodeStatus.HEALTHY

        # Update to maintenance
        network_sim.update_node_status("router_core_01", NodeStatus.MAINTENANCE)
        node = network_sim.get_node("router_core_01")
        assert node.status == NodeStatus.MAINTENANCE

        # Restore to healthy
        network_sim.update_node_status("router_core_01", NodeStatus.HEALTHY)
        node = network_sim.get_node("router_core_01")
        assert node.status == NodeStatus.HEALTHY