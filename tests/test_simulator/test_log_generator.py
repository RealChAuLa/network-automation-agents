"""Tests for log generator."""

import pytest
from src.simulator.log_generator import LogGenerator
from src.models.network import NetworkDevice


@pytest.fixture
def log_generator():
    """Create a LogGenerator instance."""
    return LogGenerator()


@pytest.fixture
def sample_device():
    """Create a sample network device."""
    return NetworkDevice(
        device_id="RTR-001",
        device_type="router",
        hostname="router-test-01",
        ip_address="192.168.1.1",
        location="TestLab-A",
        status="active",
    )


def test_log_generator_init(log_generator):
    """Test LogGenerator initialization."""
    assert log_generator is not None


def test_generate_log(log_generator, sample_device):
    """Test log generation for a device."""
    log = log_generator.generate_log(sample_device)

    assert isinstance(log, dict)
    assert log["device_id"] == "RTR-001"
    assert log["hostname"] == "router-test-01"
    assert log["ip_address"] == "192.168.1.1"
    assert log["device_type"] == "router"
    assert log["level"] in ["INFO", "WARNING", "ERROR", "DEBUG"]
    assert "timestamp" in log
    assert "message" in log
    assert "facility" in log


def test_generate_batch(log_generator, sample_topology):
    """Test batch log generation."""
    devices = sample_topology.get_all_devices()
    logs = log_generator.generate_batch(devices, count=10)

    assert len(logs) == 10
    for log in logs:
        assert isinstance(log, dict)
        assert "device_id" in log
        assert "timestamp" in log
        assert "level" in log


def test_get_facility_by_device_type(log_generator):
    """Test facility assignment based on device type."""
    router_facility = log_generator._get_facility("router")
    assert router_facility in ["ROUTING", "BGP", "OSPF", "INTERFACE"]

    switch_facility = log_generator._get_facility("switch")
    assert switch_facility in ["VLAN", "STP", "PORT", "INTERFACE"]

    firewall_facility = log_generator._get_facility("firewall")
    assert firewall_facility in ["SECURITY", "POLICY", "VPN", "IPS"]
