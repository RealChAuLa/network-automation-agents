"""Tests for the topology manager."""

import pytest
from unittest.mock import MagicMock, patch

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.topology import TopologyManager
from src.simulator. network_sim import NetworkSimulator
from src.models.network import Node, NodeType, NodeStatus, Link


class TestTopologyManager:
    """Test cases for TopologyManager."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Neo4j client."""
        client = MagicMock(spec=Neo4jClient)

        # Default responses for different operations
        client.execute_write = MagicMock(side_effect=self._mock_execute_write)
        client.execute_read = MagicMock(return_value=[])
        return client

    def _mock_execute_write(self, query, parameters=None):
        """Mock execute_write to return appropriate responses based on query."""
        if parameters is None:
            parameters = {}

        # Check what kind of query is being executed
        if "MERGE (n:NetworkNode" in query:
            # Node creation
            return [{"n": {
                "id": parameters.get("id", "test_node"),
                "name": parameters.get("name", "Test Node"),
                "type": parameters.get("type", "router_core"),
                "ip_address": parameters.get("ip_address", "10.0.0.1"),
                "location": parameters.get("location", "datacenter-1"),
                "status": parameters.get("status", "healthy"),
                "vendor": parameters.get("vendor", "Cisco"),
                "model": parameters.get("model", "ASR-9000"),
                "interfaces": parameters.get("interfaces", []),
            }}]
        elif "MERGE (source)-[r:CONNECTS_TO" in query:
            # Link creation
            return [{"r": {
                "id": parameters.get("id", "link_01"),
                "source_interface": parameters.get("source_interface", "eth0"),
                "target_interface": parameters. get("target_interface", "eth0"),
                "bandwidth_mbps": parameters. get("bandwidth_mbps", 1000),
                "latency_ms": parameters.get("latency_ms", 1.0),
                "status": parameters.get("status", "up"),
            }}]
        elif "SET n.status" in query:
            # Status update
            return [{"n": {"id": parameters.get("id", "test_node")}}]
        elif "DETACH DELETE" in query:
            # Delete operation
            return [{"deleted": 1}]
        else:
            return [{}]

    @pytest.fixture
    def topo_mgr(self, mock_client):
        """Create TopologyManager with mock client."""
        return TopologyManager(mock_client)

    @pytest.fixture
    def sample_node(self):
        """Create a sample node."""
        return Node(
            id="router_core_01",
            name="core-rtr-01",
            type=NodeType.ROUTER_CORE,
            ip_address="10.0.0.1",
            location="datacenter-1",
            vendor="Cisco",
            model="ASR-9000",
            interfaces=["ge-0/0/0", "ge-0/0/1"],
        )

    def test_create_node(self, topo_mgr, sample_node):
        """Test creating a node."""
        result = topo_mgr.create_node(sample_node)

        assert result is not None
        assert "id" in result
        topo_mgr. client.execute_write.assert_called_once()

    def test_get_node_found(self, topo_mgr, mock_client):
        """Test getting a node that exists."""
        mock_client.execute_read.return_value = [{
            "n": {
                "id": "router_core_01",
                "name": "core-rtr-01",
                "type": "router_core",
                "ip_address": "10.0.0.1",
                "location": "datacenter-1",
                "status": "healthy",
                "vendor": "Cisco",
                "model": "ASR-9000",
                "interfaces": [],
            }
        }]

        node = topo_mgr.get_node("router_core_01")

        assert node is not None
        assert node.id == "router_core_01"
        assert node. type == NodeType. ROUTER_CORE

    def test_get_node_not_found(self, topo_mgr, mock_client):
        """Test getting a node that doesn't exist."""
        mock_client.execute_read.return_value = []

        node = topo_mgr.get_node("nonexistent")

        assert node is None

    def test_get_all_nodes(self, topo_mgr, mock_client):
        """Test getting all nodes."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "node1", "name": "Node 1", "type": "router_core", "ip_address": "10.0.0.1", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
            {"n": {"id": "node2", "name": "Node 2", "type": "switch_access", "ip_address": "10.0.0.2", "location": "dc1", "status": "healthy", "vendor": "Juniper", "model": "QFX", "interfaces": []}},
        ]

        nodes = topo_mgr.get_all_nodes()

        assert len(nodes) == 2
        assert nodes[0].id == "node1"
        assert nodes[1].id == "node2"

    def test_update_node_status(self, topo_mgr, mock_client):
        """Test updating node status."""
        # Override the side_effect for this specific test
        mock_client.execute_write.side_effect = None
        mock_client.execute_write.return_value = [{"n": {"id": "node1"}}]

        result = topo_mgr.update_node_status("node1", NodeStatus. CRITICAL)

        assert result is True
        mock_client. execute_write.assert_called_once()

    def test_update_node_status_not_found(self, topo_mgr, mock_client):
        """Test updating status of non-existent node."""
        mock_client.execute_write.side_effect = None
        mock_client.execute_write.return_value = []

        result = topo_mgr.update_node_status("nonexistent", NodeStatus.CRITICAL)

        assert result is False

    def test_get_connected_nodes(self, topo_mgr, mock_client):
        """Test getting connected nodes."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "connected1", "name": "Connected 1", "type": "switch_distribution", "ip_address": "10.0.0.2", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "Cat", "interfaces": []}},
        ]

        connected = topo_mgr.get_connected_nodes("router_core_01")

        assert len(connected) == 1
        assert connected[0].id == "connected1"

    def test_import_from_simulator(self, topo_mgr, mock_client):
        """Test importing topology from simulator."""
        sim = NetworkSimulator()
        sim.create_default_topology()

        result = topo_mgr.import_from_simulator(sim)

        assert result["nodes"] > 0
        assert result["links"] > 0
        # Verify execute_write was called for nodes and links
        assert mock_client.execute_write.call_count > 0

    def test_import_from_empty_simulator(self, topo_mgr):
        """Test importing from simulator with no topology."""
        sim = NetworkSimulator()
        # Don't create topology

        result = topo_mgr. import_from_simulator(sim)

        assert result["nodes"] == 0
        assert result["links"] == 0

    def test_create_link(self, topo_mgr, mock_client):
        """Test creating a link."""
        link = Link(
            source_node_id="node1",
            target_node_id="node2",
            bandwidth_mbps=10000,
            latency_ms=0.5,
        )

        result = topo_mgr.create_link(link)

        assert result is not None
        mock_client.execute_write.assert_called_once()

    def test_get_link(self, topo_mgr, mock_client):
        """Test getting a link between two nodes."""
        mock_client.execute_read.return_value = [{
            "r": {
                "id": "link_01",
                "source_interface": "eth0",
                "target_interface": "eth1",
                "bandwidth_mbps": 10000,
                "latency_ms": 0.5,
                "status": "up",
            },
            "source_id": "node1",
            "target_id": "node2",
        }]

        link = topo_mgr.get_link("node1", "node2")

        assert link is not None
        assert link.source_node_id == "node1"
        assert link.target_node_id == "node2"

    def test_get_link_not_found(self, topo_mgr, mock_client):
        """Test getting a link that doesn't exist."""
        mock_client.execute_read.return_value = []

        link = topo_mgr. get_link("node1", "nonexistent")

        assert link is None

    def test_find_path(self, topo_mgr, mock_client):
        """Test finding path between nodes."""
        mock_client.execute_read.return_value = [{
            "nodes": [
                {"id": "node1", "name": "Node 1", "type": "router_core", "ip_address": "10.0.0.1", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []},
                {"id": "node2", "name": "Node 2", "type": "switch_distribution", "ip_address": "10.0.0.2", "location": "dc1", "status": "healthy", "vendor": "Juniper", "model": "QFX", "interfaces": []},
                {"id": "node3", "name": "Node 3", "type": "server", "ip_address": "10.0.0.3", "location": "dc1", "status": "healthy", "vendor": "Dell", "model": "R750", "interfaces": []},
            ]
        }]

        path = topo_mgr. find_path("node1", "node3")

        assert len(path) == 3
        assert path[0]. id == "node1"
        assert path[2].id == "node3"

    def test_find_path_no_path(self, topo_mgr, mock_client):
        """Test finding path when none exists."""
        mock_client.execute_read.return_value = []

        path = topo_mgr.find_path("node1", "node99")

        assert len(path) == 0

    def test_get_topology_summary(self, topo_mgr, mock_client):
        """Test getting topology summary."""
        mock_client.execute_read.return_value = [{
            "nodeCount": 11,
            "linkCount": 10,
            "types": ["router_core", "switch_distribution", "server"],
            "locations": ["datacenter-1"],
        }]

        summary = topo_mgr.get_topology_summary()

        assert summary["nodes"] == 11
        assert summary["links"] == 10
        assert "router_core" in summary["types"]

    def test_get_topology_summary_empty(self, topo_mgr, mock_client):
        """Test getting topology summary when empty."""
        mock_client.execute_read.return_value = []

        summary = topo_mgr.get_topology_summary()

        assert summary["nodes"] == 0
        assert summary["links"] == 0

    def test_delete_node(self, topo_mgr, mock_client):
        """Test deleting a node."""
        mock_client. execute_write.side_effect = None
        mock_client. execute_write.return_value = [{"deleted": 1}]

        result = topo_mgr.delete_node("router_core_01")

        assert result is True

    def test_delete_node_not_found(self, topo_mgr, mock_client):
        """Test deleting a node that doesn't exist."""
        mock_client.execute_write. side_effect = None
        mock_client.execute_write. return_value = [{"deleted": 0}]

        result = topo_mgr.delete_node("nonexistent")

        assert result is False

    def test_get_nodes_by_type(self, topo_mgr, mock_client):
        """Test getting nodes by type."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "router1", "name": "Router 1", "type": "router_core", "ip_address": "10.0.0.1", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
            {"n": {"id": "router2", "name": "Router 2", "type": "router_core", "ip_address": "10.0.0.2", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
        ]

        nodes = topo_mgr.get_nodes_by_type(NodeType.ROUTER_CORE)

        assert len(nodes) == 2
        assert all(n.type == NodeType. ROUTER_CORE for n in nodes)

    def test_get_nodes_by_status(self, topo_mgr, mock_client):
        """Test getting nodes by status."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "node1", "name": "Node 1", "type": "router_core", "ip_address": "10.0.0.1", "location": "dc1", "status": "critical", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
        ]

        nodes = topo_mgr.get_nodes_by_status(NodeStatus.CRITICAL)

        assert len(nodes) == 1
        assert nodes[0].status == NodeStatus. CRITICAL

    def test_get_nodes_by_location(self, topo_mgr, mock_client):
        """Test getting nodes by location."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "node1", "name": "Node 1", "type": "router_core", "ip_address": "10.0. 0.1", "location": "datacenter-1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
        ]

        nodes = topo_mgr. get_nodes_by_location("datacenter-1")

        assert len(nodes) == 1
        assert "datacenter-1" in nodes[0].location

    def test_get_upstream_nodes(self, topo_mgr, mock_client):
        """Test getting upstream nodes."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "upstream1", "name": "Upstream 1", "type": "router_core", "ip_address": "10.0.0. 1", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
        ]

        nodes = topo_mgr.get_upstream_nodes("switch_01")

        assert len(nodes) == 1
        assert nodes[0]. id == "upstream1"

    def test_get_downstream_nodes(self, topo_mgr, mock_client):
        """Test getting downstream nodes."""
        mock_client. execute_read.return_value = [
            {"n": {"id": "downstream1", "name": "Downstream 1", "type": "server", "ip_address": "10.0.0.10", "location": "dc1", "status": "healthy", "vendor": "Dell", "model": "R750", "interfaces": []}},
        ]

        nodes = topo_mgr.get_downstream_nodes("switch_01")

        assert len(nodes) == 1
        assert nodes[0].id == "downstream1"

    def test_get_critical_nodes(self, topo_mgr, mock_client):
        """Test getting critical nodes."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "core1", "name": "Core Router 1", "type": "router_core", "ip_address": "10.0.0.1", "location": "dc1", "status": "healthy", "vendor": "Cisco", "model": "ASR", "interfaces": []}},
            {"n": {"id": "fw1", "name": "Firewall 1", "type": "firewall", "ip_address": "10.0.0.2", "location": "dc1", "status": "healthy", "vendor": "Palo Alto", "model": "PA-5220", "interfaces": []}},
        ]

        nodes = topo_mgr.get_critical_nodes()

        assert len(nodes) == 2

    def test_get_node_dependencies(self, topo_mgr, mock_client):
        """Test getting node dependencies."""
        mock_client.execute_read.return_value = [
            {"n": {"id": "dep1", "name": "Dependent 1", "type": "server", "ip_address": "10.0.0.10", "location": "dc1", "status": "healthy", "vendor": "Dell", "model": "R750", "interfaces": []}},
            {"n": {"id": "dep2", "name": "Dependent 2", "type": "server", "ip_address": "10.0.0.11", "location": "dc1", "status": "healthy", "vendor": "Dell", "model": "R750", "interfaces": []}},
        ]

        deps = topo_mgr.get_node_dependencies("router_core_01")

        assert len(deps) == 2

    def test_update_link_status(self, topo_mgr, mock_client):
        """Test updating link status."""
        mock_client.execute_write.side_effect = None
        mock_client.execute_write.return_value = [{"r": {"id": "link1"}}]

        result = topo_mgr. update_link_status("node1", "node2", "down")

        assert result is True

    def test_update_link_status_not_found(self, topo_mgr, mock_client):
        """Test updating status of non-existent link."""
        mock_client.execute_write.side_effect = None
        mock_client.execute_write.return_value = []

        result = topo_mgr.update_link_status("node1", "nonexistent", "down")

        assert result is False

    def test_get_all_links(self, topo_mgr, mock_client):
        """Test getting all links."""
        mock_client.execute_read.return_value = [
            {
                "r": {"id": "link1", "source_interface": "eth0", "target_interface": "eth1", "bandwidth_mbps": 10000, "latency_ms": 0.5, "status": "up"},
                "source_id": "node1",
                "target_id": "node2",
            },
            {
                "r": {"id": "link2", "source_interface": "eth0", "target_interface": "eth1", "bandwidth_mbps": 10000, "latency_ms": 0.5, "status": "up"},
                "source_id": "node2",
                "target_id": "node3",
            },
        ]

        links = topo_mgr. get_all_links()

        assert len(links) == 2
        assert links[0].source_node_id == "node1"
        assert links[1].source_node_id == "node2"