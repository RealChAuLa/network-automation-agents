"""
Execution Tool Handlers

MCP tools for executing network actions.
"""

import json
import uuid
from typing import Any, Optional
from datetime import datetime

from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.models.network import NodeStatus

_network_sim: Optional[NetworkSimulator] = None
_execution_history: list[dict] = []


def _get_network_sim() -> NetworkSimulator:
    """Get or initialize network simulator."""
    global _network_sim
    if _network_sim is None:
        _network_sim = NetworkSimulator()
        _network_sim.create_default_topology()
    return _network_sim


def get_tools() -> list[Tool]:
    """Return list of execution tools."""
    return [
        Tool(
            name="execute_action",
            description="Execute a network action on a target node.  Use evaluate_policies first to get recommended actions, then validate_action to check compliance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["restart_service", "restart_node", "scale_up", "scale_down", "failover",
                                 "block_traffic", "rate_limit", "update_config", "clear_cache"],
                        "description": "Type of action to execute"
                    },
                    "target_node_id": {
                        "type": "string",
                        "description": "ID of the target node"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Action-specific parameters"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the action"
                    },
                    "policy_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of policies that approved this action"
                    }
                },
                "required": ["action_type", "target_node_id", "reason"]
            }
        ),
        Tool(
            name="get_execution_status",
            description="Get the status of a previously executed action.",
            inputSchema={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "ID of the execution"
                    }
                },
                "required": ["execution_id"]
            }
        ),
        Tool(
            name="get_execution_history",
            description="Get history of executed actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Filter by node ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max records (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
    ]


def get_handlers() -> dict:
    """Return tool name to handler mapping."""
    return {
        "execute_action": handle_execute_action,
        "get_execution_status": handle_get_execution_status,
        "get_execution_history": handle_get_execution_history,
    }


async def handle_execute_action(arguments: dict[str, Any]) -> list[TextContent]:
    """Execute action."""
    global _execution_history

    network_sim = _get_network_sim()

    action_type = arguments.get("action_type")
    target_node_id = arguments.get("target_node_id")
    parameters = arguments.get("parameters", {})
    reason = arguments.get("reason", "")
    policy_ids = arguments.get("policy_ids", [])

    node = network_sim.get_node(target_node_id)
    if not node:
        return [TextContent(type="text",
                            text=json.dumps({"success": False, "error": f"Node '{target_node_id}' not found"},
                                            indent=2))]

    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    started_at = datetime.utcnow()

    # Simulate action
    result = await _simulate_action(network_sim, action_type, target_node_id, parameters)

    completed_at = datetime.utcnow()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    record = {
        "execution_id": execution_id,
        "action_type": action_type,
        "target_node_id": target_node_id,
        "target_node_name": node.name,
        "parameters": parameters,
        "reason": reason,
        "policy_ids": policy_ids,
        "status": result["status"],
        "message": result["message"],
        "duration_ms": duration_ms,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
    }

    _execution_history.append(record)

    return [TextContent(type="text", text=json.dumps({
        "execution_id": execution_id,
        "success": result["status"] == "SUCCESS",
        "action": {"type": action_type, "target": target_node_id, "parameters": parameters},
        "result": result,
        "duration_ms": duration_ms,
    }, indent=2))]


async def _simulate_action(network_sim: NetworkSimulator, action_type: str, target_node_id: str,
                           parameters: dict) -> dict:
    """Simulate action execution."""
    node = network_sim.get_node(target_node_id)

    if action_type == "restart_service":
        network_sim.update_node_status(target_node_id, NodeStatus.MAINTENANCE)
        network_sim.update_node_status(target_node_id, NodeStatus.HEALTHY)
        return {"status": "SUCCESS", "message": f"Service restarted on {node.name}"}

    elif action_type == "restart_node":
        network_sim.update_node_status(target_node_id, NodeStatus.MAINTENANCE)
        network_sim.update_node_status(target_node_id, NodeStatus.HEALTHY)
        return {"status": "SUCCESS", "message": f"Node {node.name} restarted"}

    elif action_type == "failover":
        return {"status": "SUCCESS", "message": f"Failover initiated for {node.name}"}

    elif action_type == "clear_cache":
        return {"status": "SUCCESS", "message": f"Cache cleared on {node.name}"}

    elif action_type == "rate_limit":
        return {"status": "SUCCESS", "message": f"Rate limiting applied to {node.name}"}

    else:
        return {"status": "SUCCESS", "message": f"Action {action_type} executed on {node.name}"}


async def handle_get_execution_status(arguments: dict[str, Any]) -> list[TextContent]:
    """Get execution status."""
    execution_id = arguments.get("execution_id")

    for record in reversed(_execution_history):
        if record.get("execution_id") == execution_id:
            return [TextContent(type="text", text=json.dumps(record, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"Execution '{execution_id}' not found"}, indent=2))]


async def handle_get_execution_history(arguments: dict[str, Any]) -> list[TextContent]:
    """Get execution history."""
    node_id = arguments.get("node_id")
    limit = arguments.get("limit", 50)

    filtered = _execution_history.copy()
    if node_id:
        filtered = [r for r in filtered if r.get("target_node_id") == node_id]

    filtered = list(reversed(filtered))[:limit]

    return [TextContent(type="text", text=json.dumps({"total": len(filtered), "executions": filtered}, indent=2))]