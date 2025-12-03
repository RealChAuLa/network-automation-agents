"""
Policy Tools

MCP tools for policy management and evaluation.
"""

import json
from typing import Any, Optional
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.policies import PolicyManager
from src.mcp_server.config import config

# Global instances
_neo4j_client: Optional[Neo4jClient] = None
_policy_manager: Optional[PolicyManager] = None


def _get_policy_manager() -> PolicyManager:
    """Get or initialize policy manager."""
    global _neo4j_client, _policy_manager

    if _policy_manager is None:
        _neo4j_client = Neo4jClient(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
        _neo4j_client.connect()
        _policy_manager = PolicyManager(_neo4j_client)

    return _policy_manager


def register_policy_tools(server: Server) -> None:
    """Register policy-related tools with the MCP server."""

    @server.list_tools()
    async def list_policy_tools() -> list[Tool]:
        """List policy tools."""
        return [
            Tool(
                name="get_policies",
                description="""
                    Get all policies or filter by type/status.
                    Policies define automated responses to network events.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "policy_type": {
                            "type": "string",
                            "enum": ["remediation", "escalation", "prevention", "compliance", "maintenance"],
                            "description": "Optional: Filter by policy type"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "inactive", "draft"],
                            "description": "Optional: Filter by status (default: active)"
                        }
                    }
                }
            ),
            Tool(
                name="get_policy_details",
                description="""
                    Get detailed information about a specific policy.
                    Includes conditions, actions, and applicability.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "policy_id": {
                            "type": "string",
                            "description": "The ID of the policy to retrieve"
                        }
                    },
                    "required": ["policy_id"]
                }
            ),
            Tool(
                name="evaluate_policies",
                description="""
                    Evaluate which policies apply to a given situation/context.
                    Pass anomaly type, severity, node type, and metrics to find matching policies.
                    Returns recommended actions based on matching policies.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anomaly_type": {
                            "type": "string",
                            "enum": [
                                "HIGH_CPU",
                                "MEMORY_LEAK",
                                "INTERFACE_DOWN",
                                "PACKET_LOSS",
                                "HIGH_LATENCY",
                                "AUTH_FAILURE",
                                "CONFIG_DRIFT",
                                "SERVICE_DEGRADATION",
                                "DISK_FULL",
                                "TEMPERATURE_HIGH"
                            ],
                            "description": "Type of anomaly detected"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Severity of the issue"
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
                            "description": "Type of affected node"
                        },
                        "node_id": {
                            "type": "string",
                            "description": "Optional: ID of the affected node"
                        },
                        "cpu_utilization": {
                            "type": "number",
                            "description": "Optional: Current CPU utilization %"
                        },
                        "memory_utilization": {
                            "type": "number",
                            "description": "Optional: Current memory utilization %"
                        },
                        "packet_loss": {
                            "type": "number",
                            "description": "Optional: Current packet loss %"
                        },
                        "latency": {
                            "type": "number",
                            "description": "Optional: Current latency in ms"
                        }
                    },
                    "required": ["anomaly_type", "severity"]
                }
            ),
            Tool(
                name="validate_action",
                description="""
                    Validate if a proposed action is allowed by policies.
                    Checks the action against all applicable policies and compliance rules.
                    Returns whether the action is approved or denied with reasons.
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
                                "clear_cache",
                                "notify",
                                "escalate"
                            ],
                            "description": "Type of action to validate"
                        },
                        "target_node_id": {
                            "type": "string",
                            "description": "ID of the target node"
                        },
                        "target_node_type": {
                            "type": "string",
                            "description": "Type of the target node"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the action"
                        }
                    },
                    "required": ["action_type", "target_node_id"]
                }
            ),
            Tool(
                name="get_compliance_rules",
                description="""
                    Get compliance rules that govern network operations.
                    These rules ensure regulatory and policy compliance.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "regulation": {
                            "type": "string",
                            "description": "Optional: Filter by regulation (e.g., SOC2, PCI-DSS, INTERNAL)"
                        }
                    }
                }
            ),
        ]

    @server.call_tool()
    async def call_policy_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle policy tool calls."""

        policy_mgr = _get_policy_manager()

        try:
            if name == "get_policies":
                return await _get_policies(policy_mgr, arguments)
            elif name == "get_policy_details":
                return await _get_policy_details(policy_mgr, arguments)
            elif name == "evaluate_policies":
                return await _evaluate_policies(policy_mgr, arguments)
            elif name == "validate_action":
                return await _validate_action(policy_mgr, arguments)
            elif name == "get_compliance_rules":
                return await _get_compliance_rules(policy_mgr, arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_policies(
        policy_mgr: PolicyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get policies."""
    policy_type = arguments.get("policy_type")
    status = arguments.get("status")

    # Get policies based on filters
    if policy_type:
        from src.models.policy import PolicyType
        policies = policy_mgr.get_policies_by_type(PolicyType(policy_type))
    elif status:
        from src.models.policy import PolicyStatus
        policies = policy_mgr.get_all_policies(PolicyStatus(status))
    else:
        from src.models.policy import PolicyStatus
        policies = policy_mgr.get_all_policies(PolicyStatus.ACTIVE)

    policies_data = [
        {
            "id": p.id,
            "name": p.name,
            "type": p.policy_type.value,
            "status": p.status.value,
            "priority": p.priority,
            "description": p.description,
            "conditions_count": len(p.conditions),
            "actions_count": len(p.actions),
        }
        for p in policies
    ]

    result = {
        "total_policies": len(policies_data),
        "policies": policies_data
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_policy_details(
        policy_mgr: PolicyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get policy details."""
    policy_id = arguments.get("policy_id")

    policy = policy_mgr.get_policy(policy_id)
    if not policy:
        return [TextContent(type="text", text=f"Error: Policy '{policy_id}' not found")]

    result = {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "version": policy.version,
        "type": policy.policy_type.value,
        "status": policy.status.value,
        "priority": policy.priority,
        "conditions": [
            {
                "field": c.field,
                "operator": c.operator.value,
                "value": c.value
            }
            for c in policy.conditions
        ],
        "actions": [
            {
                "type": a.action_type.value,
                "target": a.target,
                "parameters": a.parameters,
                "timeout_seconds": a.timeout_seconds,
                "requires_approval": a.requires_approval,
            }
            for a in policy.actions
        ],
        "applies_to": {
            "node_types": policy.applies_to_node_types or ["all"],
            "locations": policy.applies_to_locations or ["all"],
        },
        "schedule": {
            "active_hours": f"{policy.active_hours_start or 0}:00 - {policy.active_hours_end or 24}:00" if policy.active_hours_start else "24/7",
            "active_days": policy.active_days,
        },
        "tags": policy.tags,
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _evaluate_policies(
        policy_mgr: PolicyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Evaluate policies against a context."""
    # Build context from arguments
    context = {
        "anomaly_type": arguments.get("anomaly_type"),
        "severity": arguments.get("severity"),
    }

    # Add optional context values
    if arguments.get("node_id"):
        context["node_id"] = arguments["node_id"]
    if arguments.get("cpu_utilization") is not None:
        context["cpu_utilization"] = arguments["cpu_utilization"]
    if arguments.get("memory_utilization") is not None:
        context["memory_utilization"] = arguments["memory_utilization"]
    if arguments.get("packet_loss") is not None:
        context["packet_loss"] = arguments["packet_loss"]
    if arguments.get("latency") is not None:
        context["latency"] = arguments["latency"]

    node_type = arguments.get("node_type")

    # Evaluate policies
    results = policy_mgr.evaluate_policies(context, node_type)

    # Separate matched and unmatched
    matched = [r for r in results if r.matched]

    # Get recommended actions from matched policies
    all_actions = []
    for r in matched:
        for action in r.recommended_actions:
            all_actions.append({
                "policy_id": r.policy_id,
                "policy_name": r.policy_name,
                "action_type": action.action_type.value,
                "target": action.target,
                "parameters": action.parameters,
                "requires_approval": action.requires_approval,
            })

    result = {
        "context": context,
        "node_type": node_type,
        "evaluation_timestamp": datetime.utcnow().isoformat(),
        "matched_policies": [
            {
                "policy_id": r.policy_id,
                "policy_name": r.policy_name,
                "conditions_met": r.conditions_met,
            }
            for r in matched
        ],
        "matched_count": len(matched),
        "recommended_actions": all_actions,
        "total_policies_evaluated": len(results),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _validate_action(
        policy_mgr: PolicyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Validate a proposed action."""
    action_type = arguments.get("action_type")
    target_node_id = arguments.get("target_node_id")
    target_node_type = arguments.get("target_node_type", "unknown")
    reason = arguments.get("reason", "")

    # Get compliance rules
    compliance_rules = policy_mgr.get_compliance_rules()

    # Check against compliance rules
    violations = []
    warnings = []

    current_hour = datetime.utcnow().hour
    current_day = datetime.utcnow().weekday()

    for rule in compliance_rules:
        # Check maintenance window
        if rule.check_type == "maintenance_window":
            required_actions = rule.parameters.get("required_for", [])
            if action_type in required_actions:
                window = rule.parameters.get("window_hours", {})
                start = window.get("start", 0)
                end = window.get("end", 24)

                if not (start <= current_hour < end):
                    if rule.enforcement == "block":
                        violations.append({
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "reason": f"Action '{action_type}' requires maintenance window ({start}:00-{end}:00 UTC)"
                        })
                    else:
                        warnings.append({
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "reason": f"Action '{action_type}' should be performed during maintenance window"
                        })

        # Check approval requirements
        elif rule.check_type == "approval_required":
            required_actions = rule.parameters.get("required_for", [])
            if action_type in required_actions:
                warnings.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "reason": f"Action '{action_type}' requires approval from: {rule.parameters.get('approvers', [])}"
                })

        # Check dual authorization for critical systems
        elif rule.check_type == "dual_authorization":
            required_actions = rule.parameters.get("required_for", [])
            applies_to = rule.parameters.get("applies_to_node_types", [])

            if action_type in required_actions and (not applies_to or target_node_type in applies_to):
                if rule.enforcement == "block":
                    violations.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "reason": f"Action '{action_type}' on '{target_node_type}' requires dual authorization"
                    })

    # Determine final status
    approved = len(violations) == 0

    result = {
        "action": {
            "type": action_type,
            "target_node_id": target_node_id,
            "target_node_type": target_node_type,
            "reason": reason,
        },
        "validation_result": {
            "approved": approved,
            "status": "APPROVED" if approved else "DENIED",
            "violations": violations,
            "warnings": warnings,
        },
        "evaluated_at": datetime.utcnow().isoformat(),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_compliance_rules(
        policy_mgr: PolicyManager,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get compliance rules."""
    regulation = arguments.get("regulation")

    rules = policy_mgr.get_compliance_rules(regulation)

    rules_data = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "regulation": r.regulation,
            "severity": r.severity,
            "check_type": r.check_type,
            "enforcement": r.enforcement,
            "parameters": r.parameters,
        }
        for r in rules
    ]

    result = {
        "total_rules": len(rules_data),
        "rules": rules_data
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]