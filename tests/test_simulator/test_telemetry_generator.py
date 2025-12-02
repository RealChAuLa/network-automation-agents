"""Tests for telemetry generator."""

import pytest
from src.simulator.telemetry_generator import TelemetryGenerator
from src.models.network import NetworkDevice


@pytest.fixture
def telemetry_generator():
    """Create a TelemetryGenerator instance."""
    return TelemetryGenerator()


@pytest.fixture
def sample_device():
    """Create a sample network device."""
    return NetworkDevice(
        device_id="SWT-001",
        device_type="switch",
        hostname="switch-test-01",
        ip_address="192.168.1.10",
        location="TestLab-B",
        status="active",
    )


def test_telemetry_generator_init(telemetry_generator):
    """Test TelemetryGenerator initialization."""
    assert telemetry_generator is not None
    assert telemetry_generator.baseline_cpu > 0
    assert telemetry_generator.baseline_memory > 0


def test_generate_telemetry_normal(telemetry_generator, sample_device):
    """Test normal telemetry generation."""
    telemetry = telemetry_generator.generate_telemetry(sample_device, inject_anomaly=False)

    assert isinstance(telemetry, dict)
    assert telemetry["device_id"] == "SWT-001"
    assert telemetry["hostname"] == "switch-test-01"
    assert "timestamp" in telemetry
    assert "metrics" in telemetry

    metrics = telemetry["metrics"]
    assert 0 <= metrics["cpu_usage"] <= 100
    assert 0 <= metrics["memory_usage"] <= 100
    assert 0 <= metrics["bandwidth_usage"] <= 100
    assert metrics["temperature"] > 0
    assert metrics["uptime_seconds"] > 0


def test_generate_telemetry_with_anomaly(telemetry_generator, sample_device):
    """Test telemetry generation with anomaly."""
    telemetry = telemetry_generator.generate_telemetry(sample_device, inject_anomaly=True)

    metrics = telemetry["metrics"]
    # Anomalies should have high values
    assert metrics["cpu_usage"] >= 85
    assert metrics["memory_usage"] >= 88
    assert metrics["bandwidth_usage"] >= 90


def test_generate_batch(telemetry_generator, sample_topology):
    """Test batch telemetry generation."""
    devices = sample_topology.get_all_devices()
    telemetry_data = telemetry_generator.generate_batch(devices, count=10, anomaly_rate=0.5)

    assert len(telemetry_data) == 10
    for telemetry in telemetry_data:
        assert isinstance(telemetry, dict)
        assert "device_id" in telemetry
        assert "metrics" in telemetry
