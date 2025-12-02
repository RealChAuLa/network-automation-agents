"""Tests for network simulator."""

from src.simulator.network_sim import NetworkSimulator
from src.models.network import NetworkTopology


def test_network_simulator_init():
    """Test NetworkSimulator initialization."""
    simulator = NetworkSimulator()
    assert simulator is not None
    assert simulator.topology is None


def test_generate_topology(network_simulator):
    """Test topology generation."""
    topology = network_simulator.generate_topology(num_routers=2, num_switches=3, num_firewalls=1)

    assert isinstance(topology, NetworkTopology)
    assert len(topology.routers) == 2
    assert len(topology.switches) == 3
    assert len(topology.firewalls) == 1


def test_get_topology_creates_if_none(network_simulator):
    """Test get_topology creates topology if none exists."""
    assert network_simulator.topology is None
    topology = network_simulator.get_topology()
    assert topology is not None
    assert isinstance(topology, NetworkTopology)


def test_device_properties(sample_topology):
    """Test device properties are set correctly."""
    all_devices = sample_topology.get_all_devices()
    assert len(all_devices) == 6  # 2 routers + 3 switches + 1 firewall

    for device in all_devices:
        assert device.device_id is not None
        assert device.hostname is not None
        assert device.ip_address is not None
        assert device.location is not None
        assert device.status == "active"


def test_topology_device_count(sample_topology):
    """Test device count method."""
    counts = sample_topology.get_device_count()
    assert counts["routers"] == 2
    assert counts["switches"] == 3
    assert counts["firewalls"] == 1
    assert counts["total"] == 6


def test_get_device_by_id(sample_topology):
    """Test getting device by ID."""
    devices = sample_topology.get_all_devices()
    test_device = devices[0]

    found_device = sample_topology.get_device_by_id(test_device.device_id)
    assert found_device is not None
    assert found_device.device_id == test_device.device_id

    not_found = sample_topology.get_device_by_id("INVALID-ID")
    assert not_found is None
