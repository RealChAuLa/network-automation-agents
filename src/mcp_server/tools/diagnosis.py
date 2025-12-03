"""
Diagnosis Tools

MCP tools for network diagnosis and anomaly detection.
"""

import json
import uuid
from typing import Any, Optional
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import MetricType, NodeStatus, AnomalyType, AnomalySeverity

# Global instances
_network_sim: Optional[NetworkSimulator] = None
_log_generator: Optional[LogGenerator] = None
_telemetry_generator: Optional[TelemetryGenerator] = None
_anomaly_injector: Optional[AnomalyInjector] = None

# Diagnosis history
_diagnosis_history: list[dict] = []


def _get_components():
    """Get or initialize components."""
    global _network_sim, _log_generator, _telemetry_generator, _anomaly_injector

    if _network_sim is None:
        _network_sim = NetworkSimulator()
        _network_sim.create_default_topology()
        _log_generator = LogGenerator(_network_sim)
        _telemetry_generator = TelemetryGenerator(_network_sim)
        _anomaly_injector = AnomalyInjector(_network_sim, _telemetry_generator, _log_generator)

    return _network_sim, _log_generator, _telemetry_generator, _anomaly_injector


def register_diagnosis_tools(server: Server) -> None:
    """Register diagnosis-related tools with the MCP server."""

    @server.list_tools()
    async def list_diagnosis_tools() -> list[Tool]:
        """List diagnosis tools."""
        return [
            Tool(
                name="run_diagnosis",
                description="""
                    Run a comprehensive diagnosis on a specific node or the entire network.
                    Analyzes telemetry, logs, and current state to identify issues.
                    Returns a diagnosis report with detected anomalies and their severity.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Optional: Node ID to diagnose (omit for network-wide diagnosis)"
                        },
                        "check_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["cpu", "memory", "network", "latency", "errors", "all"]
                            },
                            "description": "Types of checks to perform (default: all)",
                            "default": ["all"]
                        }
                    }
                }
            ),
            Tool(
                name="get_anomalies",
                description="""
                    Get currently active anomalies in the network.
                    Returns details about ongoing issues that need attention.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Optional: Minimum severity filter"
                        },
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
                                "SERVICE_DEGRADATION"
                            ],
                            "description": "Optional: Filter by anomaly type"
                        },
                        "node_id": {
                            "type": "string",
                            "description": "Optional: Filter by node ID"
                        }
                    }
                }
            ),
            Tool(
                name="inject_test_anomaly",
                description="""
                    Inject a test anomaly into the network for testing purposes.
                    Use this to simulate network issues and test agent responses.
                    FOR TESTING ONLY. 
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Node ID to inject anomaly on"
                        },
                        "anomaly_type": {
                            "type": "string",
                            "enum": [
                                "HIGH_CPU",
                                "MEMORY_LEAK",
                                "INTERFACE_DOWN",
                                "PACKET_LOSS",
                                "HIGH_LATENCY",
                                "AUTH_FAILURE",
                                "SERVICE_DEGRADATION",
                                "TEMPERATURE_HIGH"
                            ],
                            "description": "Type of anomaly to inject"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Severity of the anomaly (default: medium)",
                            "default": "medium"
                        }
                    },
                    "required": ["node_id", "anomaly_type"]
                }
            ),
            Tool(
                name="clear_anomaly",
                description="""
                    Clear a specific anomaly or all anomalies. 
                    Use after testing or when an issue has been resolved.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anomaly_id": {
                            "type": "string",
                            "description": "Optional: Specific anomaly ID to clear (omit to clear all)"
                        }
                    }
                }
            ),
            Tool(
                name="get_diagnosis_history",
                description="""
                    Get history of diagnosis reports.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Optional: Filter by node ID"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum records to return (default: 20)",
                            "default": 20
                        }
                    }
                }
            ),
        ]

    @server.call_tool()
    async def call_diagnosis_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle diagnosis tool calls."""

        try:
            if name == "run_diagnosis":
                return await _run_diagnosis(arguments)
            elif name == "get_anomalies":
                return await _get_anomalies(arguments)
            elif name == "inject_test_anomaly":
                return await _inject_test_anomaly(arguments)
            elif name == "clear_anomaly":
                return await _clear_anomaly(arguments)
            elif name == "get_diagnosis_history":
                return await _get_diagnosis_history(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _run_diagnosis(arguments: dict[str, Any]) -> list[TextContent]:
    """Run diagnosis on node(s)."""
    global _diagnosis_history

    network_sim, log_gen, tel_gen, anomaly_inj = _get_components()

    node_id = arguments.get("node_id")
    check_types = arguments.get("check_types", ["all"])

    if "all" in check_types:
        check_types = ["cpu", "memory", "network", "latency", "errors"]

    # Get nodes to diagnose
    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]
        nodes = [node]
    else:
        nodes = network_sim.get_all_nodes()

    # Create diagnosis report
    diagnosis_id = f"diag_{uuid.uuid4().hex[:12]}"
    diagnosis_time = datetime.utcnow()

    issues_found = []
    node_reports = []

    for node in nodes:
        # Get current metrics
        snapshot = tel_gen.generate_snapshot(node)

        node_issues = []

        # Check CPU
        if "cpu" in check_types:
            cpu_metric = snapshot.get_metric(MetricType.CPU_UTILIZATION)
            if cpu_metric and cpu_metric.value > 90:
                node_issues.append({
                    "type": "HIGH_CPU",
                    "severity": "critical" if cpu_metric.value > 95 else "high",
                    "metric": "cpu_utilization",
                    "value": cpu_metric.value,
                    "threshold": 90,
                    "message": f"CPU utilization is {cpu_metric.value}% (threshold: 90%)"
                })
            elif cpu_metric and cpu_metric.value > 80:
                node_issues.append({
                    "type": "HIGH_CPU",
                    "severity": "medium",
                    "metric": "cpu_utilization",
                    "value": cpu_metric.value,
                    "threshold": 80,
                    "message": f"CPU utilization is elevated at {cpu_metric.value}%"
                })

        # Check Memory
        if "memory" in check_types:
            mem_metric = snapshot.get_metric(MetricType.MEMORY_UTILIZATION)
            if mem_metric and mem_metric.value > 90:
                node_issues.append({
                    "type": "MEMORY_LEAK",
                    "severity": "critical" if mem_metric.value > 95 else "high",
                    "metric": "memory_utilization",
                    "value": mem_metric.value,
                    "threshold": 90,
                    "message": f"Memory utilization is {mem_metric.value}% (threshold: 90%)"
                })

        # Check Network/Packet Loss
        if "network" in check_types:
            loss_metric = snapshot.get_metric(MetricType.PACKET_LOSS)
            if loss_metric and loss_metric.value > 5:
                node_issues.append({
                    "type": "PACKET_LOSS",
                    "severity": "critical" if loss_metric.value > 10 else "high",
                    "metric": "packet_loss",
                    "value": loss_metric.value,
                    "threshold": 5,
                    "message": f"Packet loss is {loss_metric.value}% (threshold: 5%)"
                })

        # Check Latency
        if "latency" in check_types:
            lat_metric = snapshot.get_metric(MetricType.LATENCY)
            if lat_metric and lat_metric.value > 50:
                node_issues.append({
                    "type": "HIGH_LATENCY",
                    "severity": "critical" if lat_metric.value > 100 else "high" if lat_metric.value > 75 else "medium",
                    "metric": "latency",
                    "value": lat_metric.value,
                    "threshold": 50,
                    "message": f"Latency is {lat_metric.value}ms (threshold: 50ms)"
                })

        # Check Error Count
        if "errors" in check_types:
            err_metric = snapshot.get_metric(MetricType.ERROR_COUNT)
            if err_metric and err_metric.value > 100:
                node_issues.append({
                    "type": "HIGH_ERROR_RATE",
                    "severity": "high" if err_metric.value > 500 else "medium",
                    "metric": "error_count",
                    "value": err_metric.value,
                    "threshold": 100,
                    "message": f"Error count is {err_metric.value} (threshold: 100)"
                })

        # Add to issues
        issues_found.extend([{**issue, "node_id": node.id, "node_name": node.name} for issue in node_issues])

        # Create node report
        node_reports.append({
            "node_id": node.id,
            "node_name": node.name,
            "node_type": node.type.value,
            "status": snapshot.status.value,
            "issues_count": len(node_issues),
            "issues": node_issues,
            "metrics": {
                m.metric_type.value: {"value": m.value, "unit": m.unit}
                for m in snapshot.metrics
            }
        })

    # Determine overall severity
    if any(i["severity"] == "critical" for i in issues_found):
        overall_severity = "critical"
    elif any(i["severity"] == "high" for i in issues_found):
        overall_severity = "high"
    elif any(i["severity"] == "medium" for i in issues_found):
        overall_severity = "medium"
    elif issues_found:
        overall_severity = "low"
    else:
        overall_severity = "healthy"

    # Create diagnosis report
    diagnosis_report = {
        "diagnosis_id": diagnosis_id,
        "timestamp": diagnosis_time.isoformat(),
        "scope": node_id or "network-wide",
        "nodes_analyzed": len(nodes),
        "check_types": check_types,
        "overall_status": overall_severity,
        "total_issues": len(issues_found),
        "issues_by_severity": {
            "critical": len([i for i in issues_found if i["severity"] == "critical"]),
            "high": len([i for i in issues_found if i["severity"] == "high"]),
            "medium": len([i for i in issues_found if i["severity"] == "medium"]),
            "low": len([i for i in issues_found if i["severity"] == "low"]),
        },
        "issues": issues_found,
        "node_reports": node_reports if len(nodes) <= 5 else None,  # Only include for small scope
    }

    # Store in history
    _diagnosis_history.append(diagnosis_report)

    return [TextContent(type="text", text=json.dumps(diagnosis_report, indent=2))]


async def _get_anomalies(arguments: dict[str, Any]) -> list[TextContent]:
    """Get active anomalies."""
    network_sim, log_gen, tel_gen, anomaly_inj = _get_components()

    severity_filter = arguments.get("severity")
    type_filter = arguments.get("anomaly_type")
    node_filter = arguments.get("node_id")

    anomalies = anomaly_inj.get_active_anomalies()

    # Apply filters
    if severity_filter:
        severity_order = ["low", "medium", "high", "critical"]
        min_idx = severity_order.index(severity_filter)
        anomalies = [a for a in anomalies if severity_order.index(a.severity.value) >= min_idx]

    if type_filter:
        anomalies = [a for a in anomalies if a.anomaly_type.value == type_filter]

    if node_filter:
        anomalies = [a for a in anomalies if a.node_id == node_filter]

    result = {
        "total_anomalies": len(anomalies),
        "timestamp": datetime.utcnow().isoformat(),
        "anomalies": [
            {
                "id": a.id,
                "type": a.anomaly_type.value,
                "severity": a.severity.value,
                "node_id": a.node_id,
                "description": a.description,
                "started_at": a.started_at.isoformat(),
                "affected_metrics": [m.value for m in a.affected_metrics],
                "is_active": a.is_active,
            }
            for a in anomalies
        ]
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _inject_test_anomaly(arguments: dict[str, Any]) -> list[TextContent]:
    """Inject a test anomaly."""
    network_sim, log_gen, tel_gen, anomaly_inj = _get_components()

    node_id = arguments.get("node_id")
    anomaly_type_str = arguments.get("anomaly_type")
    severity_str = arguments.get("severity", "medium")

    # Convert to enums
    anomaly_type = AnomalyType(anomaly_type_str)
    severity = AnomalySeverity(severity_str)

    # Inject anomaly
    anomaly = anomaly_inj.inject_anomaly(node_id, anomaly_type, severity)

    if not anomaly:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": f"Failed to inject anomaly.  Node '{node_id}' may not exist."
        }, indent=2))]

    # Generate related logs
    logs = anomaly_inj.generate_anomaly_logs(anomaly, count=3)

    result = {
        "success": True,
        "anomaly": {
            "id": anomaly.id,
            "type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "node_id": anomaly.node_id,
            "description": anomaly.description,
            "started_at": anomaly.started_at.isoformat(),
            "affected_metrics": [m.value for m in anomaly.affected_metrics],
        },
        "generated_logs": [
            {
                "level": log.level.value,
                "message": log.message,
            }
            for log in logs
        ],
        "message": f"Test anomaly '{anomaly_type_str}' injected on node '{node_id}'"
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _clear_anomaly(arguments: dict[str, Any]) -> list[TextContent]:
    """Clear anomaly(s)."""
    network_sim, log_gen, tel_gen, anomaly_inj = _get_components()

    anomaly_id = arguments.get("anomaly_id")

    if anomaly_id:
        success = anomaly_inj.clear_anomaly(anomaly_id)
        if success:
            result = {"success": True, "message": f"Anomaly '{anomaly_id}' cleared"}
        else:
            result = {"success": False, "error": f"Anomaly '{anomaly_id}' not found"}
    else:
        count = anomaly_inj.clear_all_anomalies()
        result = {"success": True, "message": f"Cleared {count} anomalies"}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_diagnosis_history(arguments: dict[str, Any]) -> list[TextContent]:
    """Get diagnosis history."""
    node_id = arguments.get("node_id")
    limit = arguments.get("limit", 20)

    filtered = _diagnosis_history.copy()

    if node_id:
        filtered = [d for d in filtered if d.get("scope") == node_id]

    filtered = list(reversed(filtered))[:limit]

    result = {
        "total_records": len(filtered),
        "diagnoses": [
            {
                "diagnosis_id": d["diagnosis_id"],
                "timestamp": d["timestamp"],
                "scope": d["scope"],
                "overall_status": d["overall_status"],
                "total_issues": d["total_issues"],
            }
            for d in filtered
        ]
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]