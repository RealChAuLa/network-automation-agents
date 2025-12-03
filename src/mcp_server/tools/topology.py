"""
Topology Tools

MCP tools for querying network topology from the knowledge graph.
"""

import json
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.topology import TopologyManager
from src.mcp_server.config import config

# Global instances
_neo4j_client: Optional[Neo4jClient] = None
_topology_manager: Optional[TopologyManager] = None


def _get_topology_manager() -> TopologyManager:
    """Get or initialize topology manager."""
    global _neo4j_client, _topology_manager

    if _topology_manager is None:
        _neo4j_client = Neo4jClient(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
        _neo4j_client.connect()
        _topology_manager = TopologyManager(_neo4j_client)

    return _topology_manager


def register_topology_tools(server: Server) -> None:
    """Register topology-related tools with the MCP server."""

    @server.list_tools()
    async def list_topology_tools() -> list[Tool]:
        """List topology tools."""
        return [
            Tool(
                name="get_network_topology",
                description="""
                    Get the complete network topology or a summary of it.
                    Returns information about all network nodes and their connections.
                    Use this to understand the network structure. 
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_links": {
                            "type": "boolean",
                            "description": "Whether to include link details (default: true)",
                            "default": True
                        },
                        "node_type": {
                            "type": "string",
                            "enum": [
                                "router_core",
                                "router_edge",
                                "switch_distribution",
                                "switch_access",
                                "server",
                                "firewall",
                                "load_balancer"
                            ],
                            "description": "Optional: Filter by node type"
                        }
                    }
                }
            ),
            Tool(
                name="get_node_details",
                description="""
                    Get detailed information about a specific network node.
                    Includes node properties, status, and connected neighbors.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "The ID of the node to get details for"
                        }
                    },
                    "required": ["node_id"]
                }
            ),
            Tool(
                name="get_connected_nodes",
                description="""
                    Get all nodes directly connected to a specific node.
                    Useful for understanding node relationships and dependencies.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "The ID of the node to find connections for"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["all", "upstream", "downstream"],
                            "description": "Direction of connections (default: all)",
                            "default": "all"
                        }
                    },
                    "required": ["node_id"]
                }
            ),
            Tool(
                name="find_network_path",
                description="""
                    Find the shortest path between two network nodes.
                    Returns the sequence of nodes that form the path.
                    Useful for troubleshooting connectivity issues.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_node_id": {
                            "type": "string",
                            "description": "Starting node ID"
                        },
                        "target_node_id": {
                            "type": "string",
                            "description": "Destination node ID"
                        },
                        "max_hops": {
                            "type": "integer",
                            "description": "Maximum number of hops (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["source_node_id", "target_node_id"]
                }
            ),
            Tool(
                name="get_critical_nodes",
                description="""
                    Get list of critical network nodes. 
                    Critical nodes are core routers, distribution switches, firewalls,
                    or nodes with high connectivity that would impact many other nodes if they fail.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_node_impact",
                description="""
                    Analyze the impact if a specific node fails. 
                    Returns list of nodes that depend on the specified node.
                    Useful for maintenance planning and impact assessment.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "The ID of the node to analyze impact for"
                        }
                    },
                    "required": ["node_id"]
                }
            ),
        ]

    @server.call_tool()
    async def call_topology_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle topology tool calls."""

        topo_mgr = _get_topology_manager()

        try:
            if name == "get_network_topology":
                return await _get_network_topology(topo_mgr, arguments)
            elif name == "get_node_details":
                return await _get_node_details(topo_mgr, arguments)
            elif name == "get_connected_nodes":
                return await _get_connected_nodes(topo_mgr, arguments)
            elif name == "find_network_path":
                return await _find_network_path(topo_mgr, arguments)
            elif name == "get_critical_nodes":
                return await _get_critical_nodes(topo_mgr, arguments)
            elif name == "get_node_impact":
                return await _get_node_impact(topo_mgr, arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_network_topology(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get network topology."""
    include_links = arguments.get("include_links", True)
    node_type_filter = arguments.get("node_type")

    # Get summary
    summary = topo_mgr.get_topology_summary()

    # Get nodes
    if node_type_filter:
        from src.models.network import NodeType
        nodes = topo_mgr.get_nodes_by_type(NodeType(node_type_filter))
    else:
        nodes = topo_mgr.get_all_nodes()

    nodes_data = [
        {
            "id": n.id,
            "name": n.name,
            "type": n.type.value,
            "ip_address": n.ip_address,
            "status": n.status.value,
            "location": n.location,
            "vendor": n.vendor,
        }
        for n in nodes
    ]

    result = {
        "summary": summary,
        "nodes": nodes_data,
    }

    # Optionally include links
    if include_links:
        links = topo_mgr.get_all_links()
        links_data = [
            {
                "source": l.source_node_id,
                "target": l.target_node_id,
                "bandwidth_mbps": l.bandwidth_mbps,
                "latency_ms": l.latency_ms,
                "status": l.status,
            }
            for l in links
        ]
        result["links"] = links_data

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_node_details(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get detailed node information."""
    node_id = arguments.get("node_id")

    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]

    # Get connected nodes
    connected = topo_mgr.get_connected_nodes(node_id)

    result = {
        "node": {
            "id": node.id,
            "name": node.name,
            "type": node.type.value,
            "ip_address": node.ip_address,
            "status": node.status.value,
            "location": node.location,
            "vendor": node.vendor,
            "model": node.model,
            "interfaces": node.interfaces[:10],  # Limit interfaces shown
        },
        "connections": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type.value,
                "status": c.status.value,
            }
            for c in connected
        ],
        "connection_count": len(connected),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_connected_nodes(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get connected nodes."""
    node_id = arguments.get("node_id")
    direction = arguments.get("direction", "all")

    # Check if node exists
    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]

    # Get connections based on direction
    if direction == "upstream":
        connected = topo_mgr.get_upstream_nodes(node_id)
    elif direction == "downstream":
        connected = topo_mgr.get_downstream_nodes(node_id)
    else:
        connected = topo_mgr.get_connected_nodes(node_id)

    result = {
        "node_id": node_id,
        "direction": direction,
        "connected_nodes": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type.value,
                "ip_address": c.ip_address,
                "status": c.status.value,
            }
            for c in connected
        ],
        "total_connections": len(connected),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _find_network_path(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Find path between nodes."""
    source_id = arguments.get("source_node_id")
    target_id = arguments.get("target_node_id")
    max_hops = arguments.get("max_hops", 10)

    # Validate nodes exist
    source = topo_mgr.get_node(source_id)
    if not source:
        return [TextContent(type="text", text=f"Error: Source node '{source_id}' not found")]

    target = topo_mgr.get_node(target_id)
    if not target:
        return [TextContent(type="text", text=f"Error: Target node '{target_id}' not found")]

    # Find path
    path = topo_mgr.find_path(source_id, target_id, max_hops)

    if not path:
        result = {
            "source": source_id,
            "target": target_id,
            "path_found": False,
            "message": f"No path found within {max_hops} hops"
        }
    else:
        result = {
            "source": source_id,
            "target": target_id,
            "path_found": True,
            "hop_count": len(path) - 1,
            "path": [
                {
                    "hop": i,
                    "node_id": n.id,
                    "node_name": n.name,
                    "type": n.type.value,
                }
                for i, n in enumerate(path)
            ]
        }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_critical_nodes(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get critical nodes."""
    critical = topo_mgr.get_critical_nodes()

    result = {
        "critical_node_count": len(critical),
        "critical_nodes": [
            {
                "id": n.id,
                "name": n.name,
                "type": n.type.value,
                "status": n.status.value,
                "location": n.location,
            }
            for n in critical
        ]
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_node_impact(
        topo_mgr: TopologyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Analyze node failure impact."""
    node_id = arguments.get("node_id")

    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]

    # Get dependent nodes
    dependencies = topo_mgr.get_node_dependencies(node_id)

    # Categorize by type
    by_type = {}
    for dep in dependencies:
        type_name = dep.type.value
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append({
            "id": dep.id,
            "name": dep.name,
            "status": dep.status.value,
        })

    result = {
        "node_id": node_id,
        "node_name": node.name,
        "node_type": node.type.value,
        "impact_analysis": {
            "total_affected_nodes": len(dependencies),
            "affected_by_type": by_type,
            "severity": "critical" if len(dependencies) > 5 else "high" if len(
                dependencies) > 2 else "medium" if dependencies else "low"
        }
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]