"""
Topology Tool Handlers

MCP tools for querying network topology.
"""

import json
from typing import Any, Optional

from mcp.types import Tool, TextContent

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.topology import TopologyManager
from src.mcp_server.config import config

_topology_manager: Optional[TopologyManager] = None


def _get_topology_manager() -> TopologyManager:
    """Get or initialize topology manager."""
    global _topology_manager

    if _topology_manager is None:
        client = Neo4jClient(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
        client.connect()
        _topology_manager = TopologyManager(client)

    return _topology_manager


def get_tools() -> list[Tool]:
    """Return list of topology tools."""
    return [
        Tool(
            name="get_network_topology",
            description="Get the complete network topology including all nodes and links.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_links": {
                        "type": "boolean",
                        "description": "Include link details (default: true)",
                        "default": True
                    },
                    "node_type": {
                        "type": "string",
                        "enum": ["router_core", "router_edge", "switch_distribution", "switch_access", "server",
                                 "firewall", "load_balancer"],
                        "description": "Optional: Filter by node type"
                    }
                }
            }
        ),
        Tool(
            name="get_node_details",
            description="Get detailed information about a specific network node including its connections.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "The ID of the node"
                    }
                },
                "required": ["node_id"]
            }
        ),
        Tool(
            name="get_connected_nodes",
            description="Get all nodes directly connected to a specific node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "The ID of the node"
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
            description="Find the shortest path between two network nodes.",
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
                    }
                },
                "required": ["source_node_id", "target_node_id"]
            }
        ),
        Tool(
            name="get_critical_nodes",
            description="Get list of critical network nodes (core routers, firewalls, high-connectivity nodes).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_node_impact",
            description="Analyze the impact if a specific node fails.  Returns dependent nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID to analyze"
                    }
                },
                "required": ["node_id"]
            }
        ),
    ]


def get_handlers() -> dict:
    """Return tool name to handler mapping."""
    return {
        "get_network_topology": handle_get_network_topology,
        "get_node_details": handle_get_node_details,
        "get_connected_nodes": handle_get_connected_nodes,
        "find_network_path": handle_find_network_path,
        "get_critical_nodes": handle_get_critical_nodes,
        "get_node_impact": handle_get_node_impact,
    }


async def handle_get_network_topology(arguments: dict[str, Any]) -> list[TextContent]:
    """Get network topology."""
    topo_mgr = _get_topology_manager()

    include_links = arguments.get("include_links", True)
    node_type_filter = arguments.get("node_type")

    summary = topo_mgr.get_topology_summary()

    if node_type_filter:
        from src.models.network import NodeType
        nodes = topo_mgr.get_nodes_by_type(NodeType(node_type_filter))
    else:
        nodes = topo_mgr.get_all_nodes()

    result = {
        "summary": summary,
        "nodes": [
            {"id": n.id, "name": n.name, "type": n.type.value, "ip_address": n.ip_address, "status": n.status.value,
             "location": n.location}
            for n in nodes
        ],
    }

    if include_links:
        links = topo_mgr.get_all_links()
        result["links"] = [
            {"source": l.source_node_id, "target": l.target_node_id, "bandwidth_mbps": l.bandwidth_mbps,
             "status": l.status}
            for l in links
        ]

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_get_node_details(arguments: dict[str, Any]) -> list[TextContent]:
    """Get node details."""
    topo_mgr = _get_topology_manager()
    node_id = arguments.get("node_id")

    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]

    connected = topo_mgr.get_connected_nodes(node_id)

    return [TextContent(type="text", text=json.dumps({
        "node": {"id": node.id, "name": node.name, "type": node.type.value, "ip_address": node.ip_address,
                 "status": node.status.value, "vendor": node.vendor, "model": node.model},
        "connections": [{"id": c.id, "name": c.name, "type": c.type.value} for c in connected],
        "connection_count": len(connected),
    }, indent=2))]


async def handle_get_connected_nodes(arguments: dict[str, Any]) -> list[TextContent]:
    """Get connected nodes."""
    topo_mgr = _get_topology_manager()
    node_id = arguments.get("node_id")
    direction = arguments.get("direction", "all")

    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]

    if direction == "upstream":
        connected = topo_mgr.get_upstream_nodes(node_id)
    elif direction == "downstream":
        connected = topo_mgr.get_downstream_nodes(node_id)
    else:
        connected = topo_mgr.get_connected_nodes(node_id)

    return [TextContent(type="text", text=json.dumps({
        "node_id": node_id,
        "direction": direction,
        "connected_nodes": [{"id": c.id, "name": c.name, "type": c.type.value, "status": c.status.value} for c in
                            connected],
    }, indent=2))]


async def handle_find_network_path(arguments: dict[str, Any]) -> list[TextContent]:
    """Find network path."""
    topo_mgr = _get_topology_manager()
    source_id = arguments.get("source_node_id")
    target_id = arguments.get("target_node_id")

    source = topo_mgr.get_node(source_id)
    if not source:
        return [TextContent(type="text", text=json.dumps({"error": f"Source node '{source_id}' not found"}, indent=2))]

    target = topo_mgr.get_node(target_id)
    if not target:
        return [TextContent(type="text", text=json.dumps({"error": f"Target node '{target_id}' not found"}, indent=2))]

    path = topo_mgr.find_path(source_id, target_id)

    if not path:
        return [TextContent(type="text",
                            text=json.dumps({"source": source_id, "target": target_id, "path_found": False}, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "source": source_id,
        "target": target_id,
        "path_found": True,
        "hop_count": len(path) - 1,
        "path": [{"hop": i, "node_id": n.id, "node_name": n.name, "type": n.type.value} for i, n in enumerate(path)]
    }, indent=2))]


async def handle_get_critical_nodes(arguments: dict[str, Any]) -> list[TextContent]:
    """Get critical nodes."""
    topo_mgr = _get_topology_manager()
    critical = topo_mgr.get_critical_nodes()

    return [TextContent(type="text", text=json.dumps({
        "critical_node_count": len(critical),
        "critical_nodes": [{"id": n.id, "name": n.name, "type": n.type.value, "status": n.status.value} for n in
                           critical]
    }, indent=2))]


async def handle_get_node_impact(arguments: dict[str, Any]) -> list[TextContent]:
    """Analyze node impact."""
    topo_mgr = _get_topology_manager()
    node_id = arguments.get("node_id")

    node = topo_mgr.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]

    dependencies = topo_mgr.get_node_dependencies(node_id)

    by_type = {}
    for dep in dependencies:
        type_name = dep.type.value
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append({"id": dep.id, "name": dep.name})

    return [TextContent(type="text", text=json.dumps({
        "node_id": node_id,
        "node_name": node.name,
        "total_affected_nodes": len(dependencies),
        "affected_by_type": by_type,
        "severity": "critical" if len(dependencies) > 5 else "high" if len(
            dependencies) > 2 else "medium" if dependencies else "low"
    }, indent=2))]