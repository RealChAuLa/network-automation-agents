"""Tests for the log generator."""

import pytest
from datetime import datetime, timedelta
from src.simulator.network_sim import NetworkSimulator
from src. simulator.log_generator import LogGenerator
from src.models.network import LogLevel


class TestLogGenerator:
    """Test cases for LogGenerator."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        log_gen = LogGenerator(sim)
        return sim, log_gen
    
    def test_generate_single_log(self, setup):
        """Test generating a single log entry."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        log = log_gen.generate_log(node)
        
        assert log is not None
        assert log.node_id == node. id
        assert log.node_name == node.name
        assert log.level in LogLevel
        assert log.message is not None
        assert len(log.message) > 0
    
    def test_generate_log_with_specific_level(self, setup):
        """Test generating a log with a specific level."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        log = log_gen.generate_log(node, level=LogLevel.ERROR)
        
        assert log. level == LogLevel. ERROR
    
    def test_generate_log_with_specific_source(self, setup):
        """Test generating a log with a specific source."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        log = log_gen.generate_log(node, source="security")
        
        assert log.source == "security"
    
    def test_generate_log_with_timestamp(self, setup):
        """Test generating a log with a specific timestamp."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        custom_time = datetime(2025, 1, 1, 12, 0, 0)
        
        log = log_gen.generate_log(node, timestamp=custom_time)
        
        assert log. timestamp == custom_time
    
    def test_generate_batch(self, setup):
        """Test generating a batch of logs."""
        sim, log_gen = setup
        
        logs = log_gen. generate_batch(count=50, time_range_minutes=30)
        
        assert len(logs) == 50
        # Logs should be sorted by timestamp
        for i in range(1, len(logs)):
            assert logs[i]. timestamp >= logs[i-1].timestamp
    
    def test_generate_batch_with_specific_nodes(self, setup):
        """Test generating logs for specific nodes."""
        sim, log_gen = setup
        nodes = [sim.get_node("router_core_01"), sim.get_node("router_core_02")]
        
        logs = log_gen.generate_batch(count=20, nodes=nodes)
        
        assert len(logs) == 20
        for log in logs:
            assert log.node_id in ["router_core_01", "router_core_02"]
    
    def test_generate_batch_empty_nodes(self, setup):
        """Test generating logs with no nodes."""
        sim, log_gen = setup
        
        logs = log_gen.generate_batch(count=10, nodes=[])
        
        assert len(logs) == 0
    
    def test_log_has_required_fields(self, setup):
        """Test that generated logs have all required fields."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        log = log_gen.generate_log(node)
        
        assert log.id is not None
        assert log.timestamp is not None
        assert log.node_id is not None
        assert log.node_name is not None
        assert log. level is not None
        assert log.source is not None
        assert log.message is not None
        assert log.metadata is not None
    
    def test_log_metadata_contains_node_info(self, setup):
        """Test that log metadata contains node information."""
        sim, log_gen = setup
        node = sim. get_node("router_core_01")
        
        log = log_gen. generate_log(node)
        
        assert "node_type" in log.metadata
        assert "node_ip" in log.metadata
        assert log.metadata["node_type"] == node. type.value
    
    def test_to_syslog_format(self, setup):
        """Test converting log to syslog format."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        log = log_gen.generate_log(node)
        syslog = log. to_syslog_format()
        
        assert node.name in syslog
        assert log.level. value in syslog
        assert log.source in syslog
    
    def test_generate_anomaly_logs(self, setup):
        """Test generating anomaly-related logs."""
        sim, log_gen = setup
        node = sim.get_node("router_core_01")
        
        logs = log_gen. generate_anomaly_logs(node, "HIGH_CPU", count=5)
        
        assert len(logs) == 5
        for log in logs:
            assert log.node_id == node. id
            assert log.metadata. get("anomaly_related") is True
            assert log.metadata.get("anomaly_type") == "HIGH_CPU"
    
    def test_generate_continuous(self, setup):
        """Test continuous log generation."""
        sim, log_gen = setup
        
        generator = log_gen. generate_continuous()
        
        # Get a few logs from the generator
        logs = [next(generator) for _ in range(5)]
        
        assert len(logs) == 5
        for log in logs:
            assert log. node_id is not None
            assert log.message is not None