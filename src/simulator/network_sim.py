"""
Network Topology Simulator

Creates and manages a simulated network topology for testing. 
"""

from typing import Optional
from src.models.network import (
    Node,
    NodeType,
    NodeStatus,
    Link,
    NetworkTopology,
)


class NetworkSimulator:
    """
    Simulates a network topology with nodes and links.
    
    Example:
        >>> sim = NetworkSimulator()
        >>> sim. create_default_topology()
        >>> nodes = sim.get_all_nodes()
        >>> print(f"Created {len(nodes)} nodes")
    """
    
    def __init__(self):
        self. topology: Optional[NetworkTopology] = None
    
    def create_default_topology(self) -> NetworkTopology:
        """
        Create a default telco network topology with ~10 nodes. 
        
        Topology:
            Internet
               │
           [Firewall]
               │
         [Core Router 1]────[Core Router 2]
               │                   │
        [Dist Switch 1]     [Dist Switch 2]
            │     │             │     │
        [Access1][Access2] [Access3][Access4]
               │                   │
           [Server1]           [Server2]
        """
        nodes = {}
        
        # Core Layer - Routers
        nodes["router_core_01"] = Node(
            id="router_core_01",
            name="core-rtr-01",
            type=NodeType.ROUTER_CORE,
            ip_address="10.0.0.1",
            location="datacenter-1",
            vendor="Cisco",
            model="ASR-9000",
            interfaces=["ge-0/0/0", "ge-0/0/1", "ge-0/0/2", "ge-0/0/3"],
            metadata={"role": "primary", "as_number": 65001}
        )
        
        nodes["router_core_02"] = Node(
            id="router_core_02",
            name="core-rtr-02",
            type=NodeType.ROUTER_CORE,
            ip_address="10.0.0.2",
            location="datacenter-1",
            vendor="Cisco",
            model="ASR-9000",
            interfaces=["ge-0/0/0", "ge-0/0/1", "ge-0/0/2", "ge-0/0/3"],
            metadata={"role": "secondary", "as_number": 65001}
        )
        
        # Edge Layer - Firewall
        nodes["firewall_01"] = Node(
            id="firewall_01",
            name="fw-edge-01",
            type=NodeType. FIREWALL,
            ip_address="10.0.0.10",
            location="datacenter-1",
            vendor="Palo Alto",
            model="PA-5220",
            interfaces=["eth1", "eth2", "eth3", "eth4"],
            metadata={"zone": "dmz", "ha_mode": "active-passive"}
        )
        
        # Distribution Layer - Switches
        nodes["switch_dist_01"] = Node(
            id="switch_dist_01",
            name="dist-sw-01",
            type=NodeType. SWITCH_DISTRIBUTION,
            ip_address="10.0.1.1",
            location="datacenter-1",
            vendor="Juniper",
            model="QFX5100",
            interfaces=["xe-0/0/0", "xe-0/0/1", "xe-0/0/2", "xe-0/0/3"],
            metadata={"vlan_range": "100-200"}
        )
        
        nodes["switch_dist_02"] = Node(
            id="switch_dist_02",
            name="dist-sw-02",
            type=NodeType.SWITCH_DISTRIBUTION,
            ip_address="10.0.1.2",
            location="datacenter-1",
            vendor="Juniper",
            model="QFX5100",
            interfaces=["xe-0/0/0", "xe-0/0/1", "xe-0/0/2", "xe-0/0/3"],
            metadata={"vlan_range": "200-300"}
        )
        
        # Access Layer - Switches
        nodes["switch_access_01"] = Node(
            id="switch_access_01",
            name="access-sw-01",
            type=NodeType. SWITCH_ACCESS,
            ip_address="10.0.2.1",
            location="datacenter-1-rack-1",
            vendor="Arista",
            model="7050X",
            interfaces=[f"eth{i}" for i in range(1, 49)],
            metadata={"rack": "rack-1", "pod": "pod-1"}
        )
        
        nodes["switch_access_02"] = Node(
            id="switch_access_02",
            name="access-sw-02",
            type=NodeType.SWITCH_ACCESS,
            ip_address="10.0.2.2",
            location="datacenter-1-rack-2",
            vendor="Arista",
            model="7050X",
            interfaces=[f"eth{i}" for i in range(1, 49)],
            metadata={"rack": "rack-2", "pod": "pod-1"}
        )
        
        nodes["switch_access_03"] = Node(
            id="switch_access_03",
            name="access-sw-03",
            type=NodeType.SWITCH_ACCESS,
            ip_address="10.0.2.3",
            location="datacenter-1-rack-3",
            vendor="Arista",
            model="7050X",
            interfaces=[f"eth{i}" for i in range(1, 49)],
            metadata={"rack": "rack-3", "pod": "pod-2"}
        )
        
        # Servers
        nodes["server_01"] = Node(
            id="server_01",
            name="app-server-01",
            type=NodeType.SERVER,
            ip_address="10.0.10.1",
            location="datacenter-1-rack-1",
            vendor="Dell",
            model="PowerEdge R750",
            interfaces=["eno1", "eno2", "eno3", "eno4"],
            metadata={"os": "RHEL 9", "role": "application", "cpu_cores": 64}
        )
        
        nodes["server_02"] = Node(
            id="server_02",
            name="db-server-01",
            type=NodeType.SERVER,
            ip_address="10.0.10.2",
            location="datacenter-1-rack-3",
            vendor="Dell",
            model="PowerEdge R750",
            interfaces=["eno1", "eno2", "eno3", "eno4"],
            metadata={"os": "RHEL 9", "role": "database", "cpu_cores": 128}
        )
        
        # Load Balancer
        nodes["lb_01"] = Node(
            id="lb_01",
            name="lb-01",
            type=NodeType.LOAD_BALANCER,
            ip_address="10.0.0.100",
            location="datacenter-1",
            vendor="F5",
            model="BIG-IP i5800",
            interfaces=["1. 1", "1.2", "1.3", "1.4"],
            metadata={"vip_count": 50, "pool_count": 25}
        )
        
        # Create links
        links = [
            # Firewall to Core
            Link(
                source_node_id="firewall_01",
                target_node_id="router_core_01",
                source_interface="eth1",
                target_interface="ge-0/0/0",
                bandwidth_mbps=10000,
                latency_ms=0.5
            ),
            # Core to Core (redundancy)
            Link(
                source_node_id="router_core_01",
                target_node_id="router_core_02",
                source_interface="ge-0/0/1",
                target_interface="ge-0/0/1",
                bandwidth_mbps=100000,
                latency_ms=0.1
            ),
            # Core to Distribution
            Link(
                source_node_id="router_core_01",
                target_node_id="switch_dist_01",
                source_interface="ge-0/0/2",
                target_interface="xe-0/0/0",
                bandwidth_mbps=40000,
                latency_ms=0.2
            ),
            Link(
                source_node_id="router_core_02",
                target_node_id="switch_dist_02",
                source_interface="ge-0/0/2",
                target_interface="xe-0/0/0",
                bandwidth_mbps=40000,
                latency_ms=0.2
            ),
            # Distribution to Access
            Link(
                source_node_id="switch_dist_01",
                target_node_id="switch_access_01",
                source_interface="xe-0/0/1",
                target_interface="eth48",
                bandwidth_mbps=10000,
                latency_ms=0.3
            ),
            Link(
                source_node_id="switch_dist_01",
                target_node_id="switch_access_02",
                source_interface="xe-0/0/2",
                target_interface="eth48",
                bandwidth_mbps=10000,
                latency_ms=0.3
            ),
            Link(
                source_node_id="switch_dist_02",
                target_node_id="switch_access_03",
                source_interface="xe-0/0/1",
                target_interface="eth48",
                bandwidth_mbps=10000,
                latency_ms=0.3
            ),
            # Access to Servers
            Link(
                source_node_id="switch_access_01",
                target_node_id="server_01",
                source_interface="eth1",
                target_interface="eno1",
                bandwidth_mbps=25000,
                latency_ms=0.1
            ),
            Link(
                source_node_id="switch_access_03",
                target_node_id="server_02",
                source_interface="eth1",
                target_interface="eno1",
                bandwidth_mbps=25000,
                latency_ms=0.1
            ),
            # Load Balancer connections
            Link(
                source_node_id="router_core_01",
                target_node_id="lb_01",
                source_interface="ge-0/0/3",
                target_interface="1.1",
                bandwidth_mbps=40000,
                latency_ms=0.2
            ),
        ]
        
        self.topology = NetworkTopology(
            name="telco-network-default",
            nodes=nodes,
            links=links,
            metadata={
                "description": "Default telco network topology for simulation",
                "version": "1.0",
                "node_count": len(nodes),
                "link_count": len(links)
            }
        )
        
        return self.topology
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        if self.topology is None:
            return None
        return self.topology.get_node(node_id)
    
    def get_connected_nodes(self, node_id: str) -> list[Node]:
        """Get all nodes connected to the given node."""
        if self.topology is None:
            return []
        return self. topology.get_connected_nodes(node_id)
    
    def get_all_nodes(self) -> list[Node]:
        """Get all nodes in the topology."""
        if self.topology is None:
            return []
        return self. topology.get_all_nodes()
    
    def get_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """Get all nodes of a specific type."""
        return [n for n in self. get_all_nodes() if n.type == node_type]
    
    def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """Update the status of a node."""
        if self.topology is None:
            return False
        node = self.topology.get_node(node_id)
        if node:
            node.status = status
            return True
        return False
    
    def get_topology_summary(self) -> dict:
        """Get a summary of the topology."""
        if self.topology is None:
            return {}
        
        type_counts = {}
        for node in self.get_all_nodes():
            type_name = node.type. value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "name": self.topology. name,
            "total_nodes": len(self.topology.nodes),
            "total_links": len(self.topology.links),
            "nodes_by_type": type_counts,
            "created_at": self. topology.created_at.isoformat()
        }