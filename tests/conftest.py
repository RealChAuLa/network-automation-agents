"""Test configuration and fixtures."""

import pytest
from src.simulator.network_sim import NetworkSimulator


@pytest.fixture
def network_simulator():
    """Create a NetworkSimulator instance for testing."""
    return NetworkSimulator()


@pytest.fixture
def sample_topology(network_simulator):
    """Create a sample network topology."""
    return network_simulator.generate_topology(num_routers=2, num_switches=3, num_firewalls=1)
