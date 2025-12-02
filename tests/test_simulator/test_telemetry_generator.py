"""Tests for the telemetry generator."""

import pytest
from datetime import datetime
from src.simulator. network_sim import NetworkSimulator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.models. network import MetricType, NodeStatus


class TestTelemetryGenerator:
    """Test cases for TelemetryGenerator."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        tel_gen = TelemetryGenerator(sim)
        return sim, tel_gen
    
    def test_generate_metric(self, setup):
        """Test generating a single metric."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        metric = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION)
        
        assert metric is not None
        assert metric.node_id == node.id
        assert metric.metric_type == MetricType.CPU_UTILIZATION
        assert 0 <= metric.value <= 100
        assert metric.unit == "%"
    
    def test_generate_metric_with_timestamp(self, setup):
        """Test generating a metric with specific timestamp."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        custom_time = datetime(2025, 1, 1, 12, 0, 0)
        
        metric = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION, timestamp=custom_time)
        
        assert metric.timestamp == custom_time
    
    def test_generate_snapshot(self, setup):
        """Test generating a telemetry snapshot."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        snapshot = tel_gen.generate_snapshot(node)
        
        assert snapshot is not None
        assert snapshot.node_id == node. id
        assert snapshot.node_name == node.name
        assert len(snapshot.metrics) > 0
        assert snapshot.status in NodeStatus
    
    def test_generate_snapshot_all_metrics(self, setup):
        """Test that snapshot contains all expected metrics."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        snapshot = tel_gen.generate_snapshot(node)
        
        metric_types = {m.metric_type for m in snapshot. metrics}
        expected_types = {
            MetricType. CPU_UTILIZATION,
            MetricType.MEMORY_UTILIZATION,
            MetricType.BANDWIDTH_IN,
            MetricType.BANDWIDTH_OUT,
            MetricType.PACKET_LOSS,
            MetricType. LATENCY,
            MetricType.ERROR_COUNT,
            MetricType.TEMPERATURE,
        }
        
        assert metric_types == expected_types
    
    def test_generate_snapshot_specific_metrics(self, setup):
        """Test generating snapshot with specific metrics."""
        sim, tel_gen = setup
        node = sim. get_node("router_core_01")
        
        snapshot = tel_gen. generate_snapshot(
            node,
            metric_types=[MetricType.CPU_UTILIZATION, MetricType. MEMORY_UTILIZATION]
        )
        
        assert len(snapshot.metrics) == 2
        metric_types = {m.metric_type for m in snapshot.metrics}
        assert metric_types == {MetricType.CPU_UTILIZATION, MetricType.MEMORY_UTILIZATION}
    
    def test_generate_all_snapshots(self, setup):
        """Test generating snapshots for all nodes."""
        sim, tel_gen = setup
        
        snapshots = tel_gen. generate_all_snapshots()
        
        assert len(snapshots) == len(sim.get_all_nodes())
        node_ids = {s.node_id for s in snapshots}
        expected_ids = {n.id for n in sim.get_all_nodes()}
        assert node_ids == expected_ids
    
    def test_generate_timeseries(self, setup):
        """Test generating time series data."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        timeseries = tel_gen. generate_timeseries(
            node,
            duration_minutes=10,
            interval_seconds=60
        )
        
        # Should have ~11 snapshots (0, 1, 2, ..., 10 minutes)
        assert len(timeseries) >= 10
        
        # Check timestamps are in order
        for i in range(1, len(timeseries)):
            assert timeseries[i].timestamp > timeseries[i-1].timestamp
    
    def test_set_anomaly_override(self, setup):
        """Test setting anomaly override for metrics."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        # Set override
        tel_gen. set_anomaly_override(node. id, MetricType.CPU_UTILIZATION, 99.5)
        
        # Generate metric
        metric = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION)
        
        assert metric.value == 99.5
        assert metric. metadata.get("anomaly_override") is True
    
    def test_clear_anomaly_override(self, setup):
        """Test clearing anomaly override."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        # Set and clear override
        tel_gen.set_anomaly_override(node.id, MetricType.CPU_UTILIZATION, 99.5)
        tel_gen. clear_anomaly_override(node.id, MetricType. CPU_UTILIZATION)
        
        # Generate metric - should be normal now
        metric = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION)
        
        assert metric.metadata.get("anomaly_override") is not True
    
    def test_clear_all_anomaly_overrides(self, setup):
        """Test clearing all anomaly overrides for a node."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        # Set multiple overrides
        tel_gen.set_anomaly_override(node.id, MetricType.CPU_UTILIZATION, 99.5)
        tel_gen. set_anomaly_override(node.id, MetricType. MEMORY_UTILIZATION, 95.0)
        
        # Clear all
        tel_gen. clear_anomaly_override(node.id)
        
        # Generate metrics - should be normal
        cpu = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION)
        mem = tel_gen.generate_metric(node, MetricType.MEMORY_UTILIZATION)
        
        assert cpu.metadata.get("anomaly_override") is not True
        assert mem.metadata.get("anomaly_override") is not True
    
    def test_get_baseline(self, setup):
        """Test getting baseline values for a node."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        baseline = tel_gen.get_baseline(node)
        
        assert MetricType.CPU_UTILIZATION in baseline
        assert "min" in baseline[MetricType.CPU_UTILIZATION]
        assert "max" in baseline[MetricType.CPU_UTILIZATION]
        assert "unit" in baseline[MetricType.CPU_UTILIZATION]
    
    def test_metric_has_snmp_oid(self, setup):
        """Test that metrics include SNMP OID references."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        metric = tel_gen.generate_metric(node, MetricType.CPU_UTILIZATION)
        
        assert metric. oid is not None
        assert metric. oid.startswith("1.3.6.1")
    
    def test_status_determination_healthy(self, setup):
        """Test that normal metrics result in healthy status."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        # Generate without anomalies
        snapshot = tel_gen. generate_snapshot(node)
        
        # Most of the time should be healthy or warning (due to randomness)
        assert snapshot.status in [NodeStatus.HEALTHY, NodeStatus.WARNING]
    
    def test_status_determination_critical(self, setup):
        """Test that critical metrics result in critical status."""
        sim, tel_gen = setup
        node = sim.get_node("router_core_01")
        
        # Set critical CPU
        tel_gen. set_anomaly_override(node.id, MetricType. CPU_UTILIZATION, 98.0)
        
        snapshot = tel_gen. generate_snapshot(node)
        
        assert snapshot.status == NodeStatus.CRITICAL