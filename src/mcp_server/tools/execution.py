"""
Execution Tools

MCP tools for executing network actions (simulated).
"""

import json
import uuid
from typing import Any, Optional
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.models.network import NodeStatus


# Global instances
_network_sim: Optional[NetworkSimulator] = None

# Execution history (in-memory for now, will move to blockchain in Phase 8)
_execution_history: list[dict] = []


def _get_network_sim() -> NetworkSimulator:
    """Get or initialize network simulator."""
    global _network_sim

    if _network_sim is None:
        _network_sim = NetworkSimulator()
        _network_sim.create_default_topology()

    return _network_sim


def register_execution_tools(server: Server) -> None:
    """Register execution-related tools with the MCP server."""

    @server. list_tools()
    async def list_execution_tools() -> list[Tool]:
        """List execution tools."""
        return [
            Tool(
                name="execute_action",
                description="""
                    Execute a network action on a target node. 
                    This simulates executing remediation actions like restarting services,
                    applying rate limits, triggering failovers, etc. 
                    
                    IMPORTANT: Before calling this tool, you should:
                    1.  Use evaluate_policies to find recommended actions
                    2. Use validate_action to ensure the action is allowed
                    
                    All executions are logged for audit purposes.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "enum": [
                                "restart_service",
                                "restart_node",
                                "scale_up",
                                "scale_down",
                                "failover",
                                "block_traffic",
                                "rate_limit",
                                "update_config",
                                "clear_cache"
                            ],
                            "description": "Type of action to execute"
                        },
                        "target_node_id": {
                            "type": "string",
                            "description": "ID of the target node"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Optional: Action-specific parameters"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for executing this action"
                        },
                        "policy_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of policies that approved this action"
                        },
                        "diagnosis_id": {
                            "type": "string",
                            "description": "Optional: ID of the diagnosis that triggered this action"
                        }
                    },
                    "required": ["action_type", "target_node_id", "reason"]
                }
            ),
            Tool(
                name="get_execution_status",
                description="""
                    Get the status of a previously executed action.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "execution_id": {
                            "type": "string",
                            "description": "ID of the execution to check"
                        }
                    },
                    "required": ["execution_id"]
                }
            ),
            Tool(
                name="get_execution_history",
                description="""
                    Get history of executed actions.
                    Useful for auditing and reviewing past actions. 
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Optional: Filter by target node ID"
                        },
                        "action_type": {
                            "type": "string",
                            "description": "Optional: Filter by action type"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of records to return (default: 50)",
                            "default": 50
                        }
                    }
                }
            ),
        ]

    @server.call_tool()
    async def call_execution_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle execution tool calls."""

        try:
            if name == "execute_action":
                return await _execute_action(arguments)
            elif name == "get_execution_status":
                return await _get_execution_status(arguments)
            elif name == "get_execution_history":
                return await _get_execution_history(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _execute_action(arguments: dict[str, Any]) -> list[TextContent]:
    """Execute an action on a node."""
    global _execution_history

    network_sim = _get_network_sim()

    action_type = arguments. get("action_type")
    target_node_id = arguments.get("target_node_id")
    parameters = arguments. get("parameters", {})
    reason = arguments.get("reason", "")
    policy_ids = arguments.get("policy_ids", [])
    diagnosis_id = arguments.get("diagnosis_id")

    # Validate node exists
    node = network_sim.get_node(target_node_id)
    if not node:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": f"Node '{target_node_id}' not found"
        }, indent=2))]

    # Create execution record
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    started_at = datetime. utcnow()

    # Record intent (before execution)
    intent_record = {
        "execution_id": execution_id,
        "type": "INTENT",
        "timestamp": started_at.isoformat(),
        "action_type": action_type,
        "target_node_id": target_node_id,
        "target_node_name": node.name,
        "target_node_type": node.type. value,
        "parameters": parameters,
        "reason": reason,
        "policy_ids": policy_ids,
        "diagnosis_id": diagnosis_id,
        "status": "PENDING",
    }

    # Simulate action execution
    execution_result = await _simulate_action(
        network_sim, action_type, target_node_id, parameters
    )

    completed_at = datetime. utcnow()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    # Create result record
    result_record = {
        "execution_id": execution_id,
        "type": "RESULT",
        "timestamp": completed_at.isoformat(),
        "action_type": action_type,
        "target_node_id": target_node_id,
        "target_node_name": node.name,
        "target_node_type": node.type.value,
        "parameters": parameters,
        "reason": reason,
        "policy_ids": policy_ids,
        "diagnosis_id": diagnosis_id,
        "status": execution_result["status"],
        "result": execution_result,
        "duration_ms": duration_ms,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
    }

    # Store in history
    _execution_history.append(result_record)

    # Format response
    response = {
        "execution_id": execution_id,
        "success": execution_result["status"] == "SUCCESS",
        "action": {
            "type": action_type,
            "target_node_id": target_node_id,
            "target_node_name": node. name,
            "parameters": parameters,
        },
        "result": {
            "status": execution_result["status"],
            "message": execution_result["message"],
            "details": execution_result. get("details", {}),
        },
        "timing": {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
        },
        "audit": {
            "reason": reason,
            "policy_ids": policy_ids,
            "diagnosis_id": diagnosis_id,
        }
    }

    return [TextContent(type="text", text=json. dumps(response, indent=2))]


async def _simulate_action(
    network_sim: NetworkSimulator,
    action_type: str,
    target_node_id: str,
    parameters: dict[str, Any]
) -> dict[str, Any]:
    """Simulate executing an action and return result."""

    node = network_sim. get_node(target_node_id)

    # Simulate different action types
    if action_type == "restart_service":
        # Simulate service restart
        graceful = parameters.get("graceful", True)
        service = parameters.get("service", "default")

        # Update node status temporarily
        network_sim.update_node_status(target_node_id, NodeStatus.MAINTENANCE)
        # Then restore to healthy
        network_sim.update_node_status(target_node_id, NodeStatus.HEALTHY)

        return {
            "status": "SUCCESS",
            "message": f"Service '{service}' restarted successfully on {node.name}",
            "details": {
                "graceful": graceful,
                "service": service,
                "downtime_seconds": 5 if graceful else 2,
            }
        }

    elif action_type == "restart_node":
        network_sim.update_node_status(target_node_id, NodeStatus.MAINTENANCE)
        network_sim.update_node_status(target_node_id, NodeStatus.HEALTHY)

        return {
            "status": "SUCCESS",
            "message": f"Node {node.name} restarted successfully",
            "details": {
                "downtime_seconds": 30,
            }
        }

    elif action_type == "failover":
        return {
            "status": "SUCCESS",
            "message": f"Failover initiated for {node.name}",
            "details": {
                "failover_target": "backup_node",
                "traffic_redirected": True,
            }
        }

    elif action_type == "scale_up":
        scale_factor = parameters. get("scale_factor", 1.5)
        return {
            "status": "SUCCESS",
            "message": f"Scaled up resources on {node.name}",
            "details": {
                "scale_factor": scale_factor,
                "new_capacity": f"{scale_factor * 100}%",
            }
        }

    elif action_type == "scale_down":
        reduction = parameters.get("reduction_percent", 20)
        return {
            "status": "SUCCESS",
            "message": f"Scaled down resources on {node.name}",
            "details": {
                "reduction_percent": reduction,
            }
        }

    elif action_type == "rate_limit":
        reduction = parameters.get("reduction_percent", 20)
        duration = parameters.get("duration_minutes", 15)
        return {
            "status": "SUCCESS",
            "message": f"Rate limiting applied to {node. name}",
            "details": {
                "reduction_percent": reduction,
                "duration_minutes": duration,
            }
        }

    elif action_type == "block_traffic":
        source = parameters.get("source", "unknown")
        duration = parameters.get("duration_minutes", 60)
        return {
            "status": "SUCCESS",
            "message": f"Traffic blocked on {node.name}",
            "details": {
                "source": source,
                "duration_minutes": duration,
            }
        }

    elif action_type == "update_config":
        config_key = parameters.get("key", "unknown")
        config_value = parameters.get("value", "unknown")
        return {
            "status": "SUCCESS",
            "message": f"Configuration updated on {node.name}",
            "details": {
                "key": config_key,
                "value": config_value,
                "backup_created": True,
            }
        }

    elif action_type == "clear_cache":
        scope = parameters.get("scope", "all")
        return {
            "status": "SUCCESS",
            "message": f"Cache cleared on {node. name}",
            "details": {
                "scope": scope,
                "bytes_freed": 1024 * 1024 * 100,  # 100 MB
            }
        }

    else:
        return {
            "status": "FAILED",
            "message": f"Unknown action type: {action_type}",
            "details": {}
        }


async def _get_execution_status(arguments: dict[str, Any]) -> list[TextContent]:
    """Get status of an execution."""
    execution_id = arguments. get("execution_id")

    # Find execution in history
    for record in reversed(_execution_history):
        if record. get("execution_id") == execution_id:
            return [TextContent(type="text", text=json.dumps(record, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "error": f"Execution '{execution_id}' not found"
    }, indent=2))]


async def _get_execution_history(arguments: dict[str, Any]) -> list[TextContent]:
    """Get execution history."""
    node_id = arguments. get("node_id")
    action_type = arguments.get("action_type")
    limit = arguments.get("limit", 50)

    # Filter history
    filtered = _execution_history. copy()

    if node_id:
        filtered = [r for r in filtered if r.get("target_node_id") == node_id]

    if action_type:
        filtered = [r for r in filtered if r.get("action_type") == action_type]

    # Get most recent
    filtered = list(reversed(filtered))[:limit]

    result = {
        "total_records": len(filtered),
        "executions": filtered
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]