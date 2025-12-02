"""Tests for the network simulator."""

import pytest
from src.simulator.network_sim import NetworkSimulator
from src.models.network import NodeType, NodeStatus


class TestNetworkSimulator:
    """Test cases for NetworkSimulator."""
    
    def test_create_default_topology(self):
        """Test creating the default topology."""
        sim = NetworkSimulator()
        topology = sim.create_default_topology()
        
        assert topology is not None
        assert topology.name == "telco-network-default"
        assert len(topology.nodes) > 0
        assert len(topology.links) > 0
    
    def test_get_all_nodes(self):
        """Test getting all nodes."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        nodes = sim. get_all_nodes()
        
        assert len(nodes) == 11  # Default topology has 11 nodes
        assert all(node.id is not None for node in nodes)
    
    def test_get_node(self):
        """Test getting a specific node."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        node = sim.get_node("router_core_01")
        
        assert node is not None
        assert node. id == "router_core_01"
        assert node.type == NodeType.ROUTER_CORE
    
    def test_get_node_not_found(self):
        """Test getting a non-existent node."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        node = sim.get_node("nonexistent")
        
        assert node is None
    
    def test_get_connected_nodes(self):
        """Test getting connected nodes."""
        sim = NetworkSimulator()
        sim. create_default_topology()
        
        connected = sim.get_connected_nodes("router_core_01")
        
        assert len(connected) > 0
        # Core router 1 is connected to firewall, core router 2, dist switch 1, and LB
        assert any(n.id == "router_core_02" for n in connected)
    
    def test_update_node_status(self):
        """Test updating node status."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        result = sim.update_node_status("router_core_01", NodeStatus.CRITICAL)
        
        assert result is True
        node = sim.get_node("router_core_01")
        assert node.status == NodeStatus.CRITICAL
    
    def test_get_nodes_by_type(self):
        """Test filtering nodes by type."""
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        routers = sim.get_nodes_by_type(NodeType. ROUTER_CORE)
        
        assert len(routers) == 2
        assert all(n.type == NodeType.ROUTER_CORE for n in routers)
    
    def test_get_topology_summary(self):
        """Test getting topology summary."""
        sim = NetworkSimulator()
        sim. create_default_topology()
        
        summary = sim.get_topology_summary()
        
        assert "name" in summary
        assert "total_nodes" in summary
        assert "total_links" in summary
        assert "nodes_by_type" in summary
        assert summary["total_nodes"] == 11