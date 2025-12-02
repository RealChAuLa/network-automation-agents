"""Tests for the anomaly injector."""

import pytest
from src.simulator.network_sim import NetworkSimulator
from src. simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models. network import (
    AnomalyType,
    AnomalySeverity,
    NodeStatus,
    MetricType,
)


class TestAnomalyInjector:
    """Test cases for AnomalyInjector."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        sim = NetworkSimulator()
        sim. create_default_topology()
        log_gen = LogGenerator(sim)
        tel_gen = TelemetryGenerator(sim)
        injector = AnomalyInjector(sim, tel_gen, log_gen)
        return sim, log_gen, tel_gen, injector
    
    def test_inject_anomaly(self, setup):
        """Test injecting an anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity. CRITICAL
        )
        
        assert anomaly is not None
        assert anomaly.node_id == "router_core_01"
        assert anomaly. anomaly_type == AnomalyType.HIGH_CPU
        assert anomaly. severity == AnomalySeverity. CRITICAL
        assert anomaly.is_active is True
    
    def test_inject_anomaly_nonexistent_node(self, setup):
        """Test injecting anomaly on non-existent node."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector.inject_anomaly(
            "nonexistent_node",
            AnomalyType.HIGH_CPU
        )
        
        assert anomaly is None
    
    def test_inject_anomaly_affects_metrics(self, setup):
        """Test that injected anomaly affects telemetry."""
        sim, log_gen, tel_gen, injector = setup
        node = sim.get_node("router_core_01")
        
        # Inject high CPU anomaly
        injector.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.CRITICAL
        )
        
        # Generate telemetry
        snapshot = tel_gen.generate_snapshot(node)
        cpu_metric = snapshot. get_metric(MetricType.CPU_UTILIZATION)
        
        assert cpu_metric is not None
        assert cpu_metric.value >= 95  # Critical HIGH_CPU sets 98%
    
    def test_inject_anomaly_affects_node_status(self, setup):
        """Test that anomaly affects node status."""
        sim, log_gen, tel_gen, injector = setup
        
        injector.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.CRITICAL
        )
        
        node = sim.get_node("router_core_01")
        assert node.status == NodeStatus.CRITICAL
    
    def test_clear_anomaly(self, setup):
        """Test clearing an anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector. inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU
        )
        
        result = injector.clear_anomaly(anomaly. id)
        
        assert result is True
        assert len(injector.get_active_anomalies()) == 0
        
        # Node should be healthy again
        node = sim.get_node("router_core_01")
        assert node.status == NodeStatus.HEALTHY
    
    def test_clear_anomaly_not_found(self, setup):
        """Test clearing non-existent anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        result = injector.clear_anomaly("nonexistent_id")
        
        assert result is False
    
    def test_clear_all_anomalies(self, setup):
        """Test clearing all anomalies."""
        sim, log_gen, tel_gen, injector = setup
        
        # Inject multiple anomalies
        injector.inject_anomaly("router_core_01", AnomalyType.HIGH_CPU)
        injector. inject_anomaly("router_core_02", AnomalyType.MEMORY_LEAK)
        injector.inject_anomaly("server_01", AnomalyType.HIGH_LATENCY)
        
        count = injector.clear_all_anomalies()
        
        assert count == 3
        assert len(injector.get_active_anomalies()) == 0
    
    def test_get_active_anomalies(self, setup):
        """Test getting active anomalies."""
        sim, log_gen, tel_gen, injector = setup
        
        injector.inject_anomaly("router_core_01", AnomalyType.HIGH_CPU)
        injector.inject_anomaly("router_core_02", AnomalyType. MEMORY_LEAK)
        
        active = injector.get_active_anomalies()
        
        assert len(active) == 2
        node_ids = {a.node_id for a in active}
        assert node_ids == {"router_core_01", "router_core_02"}
    
    def test_get_anomaly(self, setup):
        """Test getting a specific anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector. inject_anomaly("router_core_01", AnomalyType.HIGH_CPU)
        
        retrieved = injector. get_anomaly(anomaly.id)
        
        assert retrieved is not None
        assert retrieved.id == anomaly.id
    
    def test_inject_random_anomaly(self, setup):
        """Test injecting a random anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector. inject_random_anomaly()
        
        assert anomaly is not None
        assert anomaly. node_id in [n.id for n in sim.get_all_nodes()]
        assert anomaly.anomaly_type in AnomalyType
    
    def test_inject_random_anomaly_with_severity(self, setup):
        """Test injecting random anomaly with specific severity."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector.inject_random_anomaly(severity=AnomalySeverity.LOW)
        
        assert anomaly is not None
        assert anomaly.severity == AnomalySeverity.LOW
    
    def test_create_incident_scenario(self, setup):
        """Test creating an incident scenario."""
        sim, log_gen, tel_gen, injector = setup
        
        anomalies = injector. create_incident_scenario("network_congestion")
        
        assert len(anomalies) > 0
        for anomaly in anomalies:
            assert anomaly.metadata.get("scenario") == "network_congestion"
    
    def test_create_incident_scenario_unknown(self, setup):
        """Test creating unknown scenario."""
        sim, log_gen, tel_gen, injector = setup
        
        anomalies = injector.create_incident_scenario("unknown_scenario")
        
        assert len(anomalies) == 0
    
    def test_get_available_scenarios(self, setup):
        """Test getting available scenarios."""
        sim, log_gen, tel_gen, injector = setup
        
        scenarios = injector.get_available_scenarios()
        
        assert len(scenarios) > 0
        assert "network_congestion" in scenarios
        assert "ddos_attack" in scenarios
        assert "datacenter_cooling_failure" in scenarios
    
    def test_generate_anomaly_logs(self, setup):
        """Test generating logs for an anomaly."""
        sim, log_gen, tel_gen, injector = setup
        
        anomaly = injector.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity. CRITICAL
        )
        
        logs = injector.generate_anomaly_logs(anomaly, count=5)
        
        assert len(logs) == 5
        for log in logs:
            assert log.node_id == "router_core_01"
    
    def test_anomaly_severity_levels(self, setup):
        """Test different severity levels produce different metric values."""
        sim, log_gen, tel_gen, injector = setup
        
        # Inject LOW severity
        injector.inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity.LOW
        )
        node = sim.get_node("router_core_01")
        snapshot_low = tel_gen.generate_snapshot(node)
        cpu_low = snapshot_low. get_metric(MetricType.CPU_UTILIZATION). value
        
        # Clear and inject CRITICAL severity
        injector. clear_all_anomalies()
        injector. inject_anomaly(
            "router_core_01",
            AnomalyType.HIGH_CPU,
            AnomalySeverity. CRITICAL
        )
        snapshot_critical = tel_gen.generate_snapshot(node)
        cpu_critical = snapshot_critical.get_metric(MetricType.CPU_UTILIZATION).value
        
        # Critical should be higher than low
        assert cpu_critical > cpu_low
    
    def test_interface_down_anomaly(self, setup):
        """Test interface down anomaly zeroes bandwidth."""
        sim, log_gen, tel_gen, injector = setup
        node = sim.get_node("router_core_01")
        
        injector.inject_anomaly(
            "router_core_01",
            AnomalyType. INTERFACE_DOWN,
            AnomalySeverity.CRITICAL
        )
        
        snapshot = tel_gen. generate_snapshot(node)
        bandwidth_in = snapshot.get_metric(MetricType.BANDWIDTH_IN)
        bandwidth_out = snapshot.get_metric(MetricType.BANDWIDTH_OUT)
        
        assert bandwidth_in. value == 0
        assert bandwidth_out.value == 0
    
    def test_service_degradation_affects_multiple_metrics(self, setup):
        """Test service degradation affects multiple metrics."""
        sim, log_gen, tel_gen, injector = setup
        node = sim.get_node("router_core_01")
        
        anomaly = injector. inject_anomaly(
            "router_core_01",
            AnomalyType.SERVICE_DEGRADATION,
            AnomalySeverity.HIGH
        )
        
        # Should affect CPU, latency, and packet loss
        assert MetricType.CPU_UTILIZATION in anomaly.affected_metrics
        assert MetricType. LATENCY in anomaly.affected_metrics
        assert MetricType.PACKET_LOSS in anomaly. affected_metrics