"""
Topology Manager

Manages network topology in Neo4j knowledge graph.
"""

from typing import Any, Optional
from datetime import datetime

from src.knowledge_graph. client import Neo4jClient
from src.models.network import Node, Link, NetworkTopology, NodeType, NodeStatus
from src. simulator.network_sim import NetworkSimulator


class TopologyManager:
    """
    Manages network topology storage and queries in Neo4j.

    Example:
        >>> client = Neo4jClient()
        >>> client.connect()
        >>> topo_mgr = TopologyManager(client)
        >>>
        >>> # Import from simulator
        >>> sim = NetworkSimulator()
        >>> sim. create_default_topology()
        >>> topo_mgr.  import_from_simulator(sim)
        >>>
        >>> # Query
        >>> node = topo_mgr.get_node("router_core_01")
        >>> neighbors = topo_mgr.get_connected_nodes("router_core_01")
    """

    def __init__(self, client: Neo4jClient):
        """
        Initialize TopologyManager.

        Args:
            client: Neo4jClient instance
        """
        self.client = client

    # =========================================================================
    # Import Operations
    # =========================================================================

    def import_from_simulator(self, simulator: NetworkSimulator) -> dict[str, int]:
        """
        Import network topology from simulator into Neo4j.

        Args:
            simulator: NetworkSimulator instance with topology

        Returns:
            Dictionary with counts of imported nodes and links
        """
        if simulator.topology is None:
            return {"nodes": 0, "links": 0}

        nodes_imported = 0
        links_imported = 0

        # Import nodes
        for node in simulator. get_all_nodes():
            self. create_node(node)
            nodes_imported += 1

        # Import links
        for link in simulator.topology.links:
            self. create_link(link)
            links_imported += 1

        return {"nodes": nodes_imported, "links": links_imported}

    # =========================================================================
    # Node Operations
    # =========================================================================

    def create_node(self, node: Node) -> dict[str, Any]:
        """
        Create a network node in Neo4j.

        Args:
            node: Node object to create

        Returns:
            Created node properties
        """
        query = """
        MERGE (n:NetworkNode {id: $id})
        SET n. name = $name,
            n.type = $type,
            n.ip_address = $ip_address,
            n.location = $location,
            n.status = $status,
            n.vendor = $vendor,
            n.model = $model,
            n.interfaces = $interfaces,
            n.metadata = $metadata,
            n.created_at = $created_at,
            n.updated_at = datetime()
        RETURN n {.*} as node
        """

        parameters = {
            "id": node.id,
            "name": node.name,
            "type": node.type.value,
            "ip_address": node.ip_address,
            "location": node. location,
            "status": node.status.value,
            "vendor": node. vendor,
            "model": node.model,
            "interfaces": node.interfaces,
            "metadata": str(node.metadata),
            "created_at": node.created_at. isoformat(),
        }

        result = self.client.execute_write(query, parameters)
        return result[0]["node"] if result else {}

    def get_node(self, node_id: str) -> Optional[Node]:
        """
        Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node object or None if not found
        """
        query = """
        MATCH (n:NetworkNode {id: $id})
        RETURN n {.*} as node
        """

        result = self.client. execute_read(query, {"id": node_id})

        if not result:
            return None

        return self._node_from_record(result[0]["node"])

    def get_all_nodes(self) -> list[Node]:
        """Get all network nodes."""
        query = """
        MATCH (n:NetworkNode)
        RETURN n {.*} as node
        ORDER BY n.type, n.name
        """

        result = self. client.execute_read(query)
        return [self._node_from_record(r["node"]) for r in result]

    def get_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """Get all nodes of a specific type."""
        query = """
        MATCH (n:NetworkNode {type: $type})
        RETURN n {.*} as node
        ORDER BY n.name
        """

        result = self.client. execute_read(query, {"type": node_type.value})
        return [self._node_from_record(r["node"]) for r in result]

    def get_nodes_by_status(self, status: NodeStatus) -> list[Node]:
        """Get all nodes with a specific status."""
        query = """
        MATCH (n:NetworkNode {status: $status})
        RETURN n {.*} as node
        ORDER BY n. name
        """

        result = self.client.execute_read(query, {"status": status. value})
        return [self._node_from_record(r["node"]) for r in result]

    def get_nodes_by_location(self, location: str) -> list[Node]:
        """Get all nodes in a specific location."""
        query = """
        MATCH (n:NetworkNode)
        WHERE n. location CONTAINS $location
        RETURN n {.*} as node
        ORDER BY n.name
        """

        result = self.client.execute_read(query, {"location": location})
        return [self._node_from_record(r["node"]) for r in result]

    def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """
        Update a node's status.

        Args:
            node_id: Node ID
            status: New status

        Returns:
            True if updated, False if node not found
        """
        query = """
        MATCH (n:NetworkNode {id: $id})
        SET n. status = $status, n.updated_at = datetime()
        RETURN n {.*} as node
        """

        result = self.client. execute_write(query, {
            "id": node_id,
            "status": status.value,
        })

        return len(result) > 0

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships."""
        query = """
        MATCH (n:NetworkNode {id: $id})
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        result = self.client.execute_write(query, {"id": node_id})
        return result[0]["deleted"] > 0 if result else False

    # =========================================================================
    # Link Operations
    # =========================================================================

    def create_link(self, link: Link) -> dict[str, Any]:
        """
        Create a link between two nodes.

        Args:
            link: Link object

        Returns:
            Created relationship properties
        """
        query = """
        MATCH (source:NetworkNode {id: $source_id})
        MATCH (target:NetworkNode {id: $target_id})
        MERGE (source)-[r:CONNECTS_TO {id: $id}]->(target)
        SET r.source_interface = $source_interface,
            r. target_interface = $target_interface,
            r.bandwidth_mbps = $bandwidth_mbps,
            r.latency_ms = $latency_ms,
            r.status = $status,
            r.created_at = datetime()
        RETURN r {.*} as link, source. id as source_id, target.id as target_id
        """

        parameters = {
            "id": link.id,
            "source_id": link.source_node_id,
            "target_id": link.target_node_id,
            "source_interface": link. source_interface,
            "target_interface": link.target_interface,
            "bandwidth_mbps": link.bandwidth_mbps,
            "latency_ms": link.latency_ms,
            "status": link.status,
        }

        result = self.client.execute_write(query, parameters)
        return result[0]["link"] if result else {}

    def get_link(self, source_id: str, target_id: str) -> Optional[Link]:
        """Get a link between two nodes."""
        query = """
        MATCH (source:NetworkNode {id: $source_id})-[r:CONNECTS_TO]->(target:NetworkNode {id: $target_id})
        RETURN r {.*} as link, source.id as source_id, target. id as target_id
        """

        result = self.client.execute_read(query, {
            "source_id": source_id,
            "target_id": target_id,
        })

        if not result:
            return None

        return self._link_from_record(result[0])

    def get_all_links(self) -> list[Link]:
        """Get all links in the topology."""
        query = """
        MATCH (source:NetworkNode)-[r:CONNECTS_TO]->(target:NetworkNode)
        RETURN r {.*} as link, source.id as source_id, target.id as target_id
        """

        result = self.client. execute_read(query)
        return [self._link_from_record(r) for r in result]

    def update_link_status(self, source_id: str, target_id: str, status: str) -> bool:
        """Update link status (up/down)."""
        query = """
        MATCH (source:NetworkNode {id: $source_id})-[r:CONNECTS_TO]->(target:NetworkNode {id: $target_id})
        SET r.status = $status
        RETURN r {.*} as link
        """

        result = self. client.execute_write(query, {
            "source_id": source_id,
            "target_id": target_id,
            "status": status,
        })

        return len(result) > 0

    # =========================================================================
    # Graph Queries
    # =========================================================================

    def get_connected_nodes(self, node_id: str) -> list[Node]:
        """Get all nodes directly connected to a node."""
        query = """
        MATCH (n:NetworkNode {id: $id})-[:CONNECTS_TO]-(connected:NetworkNode)
        RETURN DISTINCT connected {.*} as node
        """

        result = self.client. execute_read(query, {"id": node_id})
        return [self._node_from_record(r["node"]) for r in result]

    def get_upstream_nodes(self, node_id: str) -> list[Node]:
        """Get nodes that connect TO this node (upstream)."""
        query = """
        MATCH (upstream:NetworkNode)-[:CONNECTS_TO]->(n:NetworkNode {id: $id})
        RETURN upstream {.*} as node
        """

        result = self.client.execute_read(query, {"id": node_id})
        return [self._node_from_record(r["node"]) for r in result]

    def get_downstream_nodes(self, node_id: str) -> list[Node]:
        """Get nodes that this node connects to (downstream)."""
        query = """
        MATCH (n:NetworkNode {id: $id})-[:CONNECTS_TO]->(downstream:NetworkNode)
        RETURN downstream {.*} as node
        """

        result = self.client.execute_read(query, {"id": node_id})
        return [self._node_from_record(r["node"]) for r in result]

    def find_path(self, source_id: str, target_id: str, max_hops: int = 10) -> list[Node]:
        """
        Find shortest path between two nodes.

        Args:
            source_id: Starting node ID
            target_id: Ending node ID
            max_hops: Maximum path length

        Returns:
            List of nodes in the path
        """
        query = f"""
        MATCH path = shortestPath(
            (source:NetworkNode {{id: $source_id}})-[:CONNECTS_TO*1..{max_hops}]-(target:NetworkNode {{id: $target_id}})
        )
        RETURN [n IN nodes(path) | n {{.*}}] as nodes
        """

        result = self.client.execute_read(query, {
            "source_id": source_id,
            "target_id": target_id,
        })

        if not result:
            return []

        return [self._node_from_record(n) for n in result[0]["nodes"]]

    def get_node_dependencies(self, node_id: str) -> list[Node]:
        """
        Get all nodes that depend on a given node (downstream impact).

        Useful for impact analysis - if this node fails, what else is affected?
        """
        query = """
        MATCH (n:NetworkNode {id: $id})<-[:CONNECTS_TO*]-(dependent:NetworkNode)
        RETURN DISTINCT dependent {.*} as node
        """

        result = self.client. execute_read(query, {"id": node_id})
        return [self._node_from_record(r["node"]) for r in result]

    def get_critical_nodes(self) -> list[Node]:
        """
        Get nodes that are critical (high connectivity or core type).

        A node is critical if:
        - It's a core router or distribution switch
        - It has more than 3 connections
        """
        query = """
        MATCH (n:NetworkNode)
        WHERE n.type IN ['router_core', 'switch_distribution', 'firewall', 'load_balancer']
           OR size([(n)-[:CONNECTS_TO]-() | 1]) > 3
        RETURN n {.*} as node
        ORDER BY size([(n)-[:CONNECTS_TO]-() | 1]) DESC
        """

        result = self.client.execute_read(query)
        return [self._node_from_record(r["node"]) for r in result]

    def get_topology_summary(self) -> dict[str, Any]:
        """Get summary statistics about the topology."""
        query = """
        MATCH (n:NetworkNode)
        WITH count(n) as nodeCount,
             collect(DISTINCT n.type) as types,
             collect(DISTINCT n.location) as locations
        OPTIONAL MATCH ()-[r:CONNECTS_TO]->()
        RETURN nodeCount, 
               count(r) as linkCount,
               types,
               locations
        """

        result = self. client.execute_read(query)

        if not result:
            return {"nodes": 0, "links": 0, "types": [], "locations": []}

        r = result[0]
        return {
            "nodes": r["nodeCount"],
            "links": r["linkCount"],
            "types": r["types"],
            "locations": r["locations"],
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _node_from_record(self, record: dict) -> Node:
        """Convert a Neo4j node record to a Node object."""
        if record is None:
            record = {}

        return Node(
            id=record. get("id", ""),
            name=record.get("name", ""),
            type=NodeType(record.get("type", "server")),
            ip_address=record. get("ip_address", "0.0.0.0"),
            location=record.get("location", "unknown"),
            status=NodeStatus(record. get("status", "unknown")),
            vendor=record.get("vendor", "Unknown"),
            model=record.get("model", "Unknown"),
            interfaces=record. get("interfaces", []),
            metadata={},
        )

    def _link_from_record(self, record: dict) -> Link:
        """Convert a Neo4j relationship record to a Link object."""
        if record is None:
            record = {}

        # The link properties are in the "link" key
        link_data = record.get("link", {})
        if link_data is None:
            link_data = {}

        return Link(
            id=link_data.get("id", ""),
            source_node_id=record.get("source_id", ""),
            target_node_id=record.get("target_id", ""),
            source_interface=link_data.get("source_interface", "eth0"),
            target_interface=link_data.get("target_interface", "eth0"),
            bandwidth_mbps=link_data.get("bandwidth_mbps", 1000),
            latency_ms=link_data.get("latency_ms", 1.0),
            status=link_data. get("status", "up"),
        )