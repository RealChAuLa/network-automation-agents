"""
Policy Tool Handlers

MCP tools for policy management and evaluation.
"""

import json
from typing import Any, Optional
from datetime import datetime

from mcp.types import Tool, TextContent

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.policies import PolicyManager
from src.mcp_server.config import config

_policy_manager: Optional[PolicyManager] = None


def _get_policy_manager() -> PolicyManager:
    """Get or initialize policy manager."""
    global _policy_manager

    if _policy_manager is None:
        client = Neo4jClient(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password,
            database=config.neo4j_database,
        )
        client.connect()
        _policy_manager = PolicyManager(client)

    return _policy_manager


def get_tools() -> list[Tool]:
    """Return list of policy tools."""
    return [
        Tool(
            name="get_policies",
            description="Get all policies or filter by type/status.  Policies define automated responses to network events.",
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
                        "description": "Optional: Filter by status"
                    }
                }
            }
        ),
        Tool(
            name="get_policy_details",
            description="Get detailed information about a specific policy including conditions and actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "description": "The ID of the policy"
                    }
                },
                "required": ["policy_id"]
            }
        ),
        Tool(
            name="evaluate_policies",
            description="Evaluate which policies apply to a given situation. Pass anomaly type, severity, and node type to find matching policies and recommended actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "anomaly_type": {
                        "type": "string",
                        "enum": ["HIGH_CPU", "MEMORY_LEAK", "INTERFACE_DOWN", "PACKET_LOSS", "HIGH_LATENCY",
                                 "AUTH_FAILURE", "CONFIG_DRIFT", "SERVICE_DEGRADATION", "DISK_FULL",
                                 "TEMPERATURE_HIGH"],
                        "description": "Type of anomaly detected"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Severity of the issue"
                    },
                    "node_type": {
                        "type": "string",
                        "enum": ["router_core", "router_edge", "switch_distribution", "switch_access", "server",
                                 "firewall", "load_balancer"],
                        "description": "Optional: Type of affected node"
                    },
                    "cpu_utilization": {
                        "type": "number",
                        "description": "Optional: Current CPU %"
                    },
                    "memory_utilization": {
                        "type": "number",
                        "description": "Optional: Current memory %"
                    }
                },
                "required": ["anomaly_type", "severity"]
            }
        ),
        Tool(
            name="validate_action",
            description="Validate if a proposed action is allowed by compliance rules. Checks maintenance windows, approvals, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["restart_service", "restart_node", "scale_up", "scale_down", "failover",
                                 "block_traffic", "rate_limit", "update_config", "clear_cache"],
                        "description": "Type of action to validate"
                    },
                    "target_node_id": {
                        "type": "string",
                        "description": "ID of the target node"
                    },
                    "target_node_type": {
                        "type": "string",
                        "description": "Optional: Type of the target node"
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
            description="Get compliance rules that govern network operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "regulation": {
                        "type": "string",
                        "description": "Optional: Filter by regulation (e.g., SOC2, PCI-DSS)"
                    }
                }
            }
        ),
    ]


def get_handlers() -> dict:
    """Return tool name to handler mapping."""
    return {
        "get_policies": handle_get_policies,
        "get_policy_details": handle_get_policy_details,
        "evaluate_policies": handle_evaluate_policies,
        "validate_action": handle_validate_action,
        "get_compliance_rules": handle_get_compliance_rules,
    }


async def handle_get_policies(arguments: dict[str, Any]) -> list[TextContent]:
    """Get policies."""
    policy_mgr = _get_policy_manager()

    policy_type = arguments.get("policy_type")
    status = arguments.get("status")

    from src.models.policy import PolicyType, PolicyStatus

    if policy_type:
        policies = policy_mgr.get_policies_by_type(PolicyType(policy_type))
    elif status:
        policies = policy_mgr.get_all_policies(PolicyStatus(status))
    else:
        policies = policy_mgr.get_all_policies(PolicyStatus.ACTIVE)

    return [TextContent(type="text", text=json.dumps({
        "total_policies": len(policies),
        "policies": [
            {"id": p.id, "name": p.name, "type": p.policy_type.value, "status": p.status.value, "priority": p.priority,
             "description": p.description}
            for p in policies
        ]
    }, indent=2))]


async def handle_get_policy_details(arguments: dict[str, Any]) -> list[TextContent]:
    """Get policy details."""
    policy_mgr = _get_policy_manager()
    policy_id = arguments.get("policy_id")

    policy = policy_mgr.get_policy(policy_id)
    if not policy:
        return [TextContent(type="text", text=json.dumps({"error": f"Policy '{policy_id}' not found"}, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "type": policy.policy_type.value,
        "status": policy.status.value,
        "priority": policy.priority,
        "conditions": [{"field": c.field, "operator": c.operator.value, "value": c.value} for c in policy.conditions],
        "actions": [{"type": a.action_type.value, "target": a.target, "parameters": a.parameters} for a in
                    policy.actions],
        "applies_to_node_types": policy.applies_to_node_types or ["all"],
        "tags": policy.tags,
    }, indent=2))]


async def handle_evaluate_policies(arguments: dict[str, Any]) -> list[TextContent]:
    """Evaluate policies."""
    policy_mgr = _get_policy_manager()

    context = {
        "anomaly_type": arguments.get("anomaly_type"),
        "severity": arguments.get("severity"),
    }

    if arguments.get("cpu_utilization") is not None:
        context["cpu_utilization"] = arguments["cpu_utilization"]
    if arguments.get("memory_utilization") is not None:
        context["memory_utilization"] = arguments["memory_utilization"]

    node_type = arguments.get("node_type")

    results = policy_mgr.evaluate_policies(context, node_type)
    matched = [r for r in results if r.matched]

    all_actions = []
    for r in matched:
        for action in r.recommended_actions:
            all_actions.append({
                "policy_id": r.policy_id,
                "policy_name": r.policy_name,
                "action_type": action.action_type.value,
                "target": action.target,
                "parameters": action.parameters,
            })

    return [TextContent(type="text", text=json.dumps({
        "context": context,
        "matched_policies": [
            {"policy_id": r.policy_id, "policy_name": r.policy_name, "conditions_met": r.conditions_met} for r in
            matched],
        "matched_count": len(matched),
        "recommended_actions": all_actions,
    }, indent=2))]


async def handle_validate_action(arguments: dict[str, Any]) -> list[TextContent]:
    """Validate action."""
    policy_mgr = _get_policy_manager()

    action_type = arguments.get("action_type")
    target_node_id = arguments.get("target_node_id")
    target_node_type = arguments.get("target_node_type", "unknown")
    reason = arguments.get("reason", "")

    compliance_rules = policy_mgr.get_compliance_rules()

    violations = []
    warnings = []
    current_hour = datetime.utcnow().hour

    for rule in compliance_rules:
        if rule.check_type == "maintenance_window":
            required_actions = rule.parameters.get("required_for", [])
            if action_type in required_actions:
                window = rule.parameters.get("window_hours", {})
                start = window.get("start", 0)
                end = window.get("end", 24)
                if not (start <= current_hour < end):
                    if rule.enforcement == "block":
                        violations.append(
                            {"rule_id": rule.id, "reason": f"Outside maintenance window ({start}:00-{end}:00 UTC)"})
                    else:
                        warnings.append({"rule_id": rule.id, "reason": "Should be during maintenance window"})

        elif rule.check_type == "approval_required":
            required_actions = rule.parameters.get("required_for", [])
            if action_type in required_actions:
                warnings.append(
                    {"rule_id": rule.id, "reason": f"Requires approval from: {rule.parameters.get('approvers', [])}"})

    approved = len(violations) == 0

    return [TextContent(type="text", text=json.dumps({
        "action": {"type": action_type, "target_node_id": target_node_id, "reason": reason},
        "validation_result": {"approved": approved, "status": "APPROVED" if approved else "DENIED",
                              "violations": violations, "warnings": warnings},
    }, indent=2))]


async def handle_get_compliance_rules(arguments: dict[str, Any]) -> list[TextContent]:
    """Get compliance rules."""
    policy_mgr = _get_policy_manager()
    regulation = arguments.get("regulation")

    rules = policy_mgr.get_compliance_rules(regulation)

    return [TextContent(type="text", text=json.dumps({
        "total_rules": len(rules),
        "rules": [{"id": r.id, "name": r.name, "regulation": r.regulation, "check_type": r.check_type,
                   "enforcement": r.enforcement} for r in rules]
    }, indent=2))]