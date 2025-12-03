"""
Diagnosis Tool Handlers

MCP tools for network diagnosis.
"""

import json
import uuid
from typing import Any, Optional
from datetime import datetime

from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import MetricType, AnomalyType, AnomalySeverity

_network_sim: Optional[NetworkSimulator] = None
_log_generator: Optional[LogGenerator] = None
_telemetry_generator: Optional[TelemetryGenerator] = None
_anomaly_injector: Optional[AnomalyInjector] = None
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


def get_tools() -> list[Tool]:
    """Return list of diagnosis tools."""
    return [
        Tool(
            name="run_diagnosis",
            description="Run comprehensive diagnosis on a node or entire network.  Analyzes metrics to identify issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Node to diagnose (omit for network-wide)"
                    },
                    "check_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["cpu", "memory", "network", "latency", "errors", "all"]},
                        "description": "Types of checks (default: all)"
                    }
                }
            }
        ),
        Tool(
            name="get_anomalies",
            description="Get currently active anomalies in the network.",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Optional: Minimum severity"
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Filter by node"
                    }
                }
            }
        ),
        Tool(
            name="inject_test_anomaly",
            description="Inject a test anomaly for testing purposes.  FOR TESTING ONLY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node to inject anomaly on"
                    },
                    "anomaly_type": {
                        "type": "string",
                        "enum": ["HIGH_CPU", "MEMORY_LEAK", "INTERFACE_DOWN", "PACKET_LOSS", "HIGH_LATENCY",
                                 "AUTH_FAILURE", "SERVICE_DEGRADATION", "TEMPERATURE_HIGH"],
                        "description": "Type of anomaly"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Severity (default: medium)"
                    }
                },
                "required": ["node_id", "anomaly_type"]
            }
        ),
        Tool(
            name="clear_anomaly",
            description="Clear anomalies after testing or when resolved.",
            inputSchema={
                "type": "object",
                "properties": {
                    "anomaly_id": {
                        "type": "string",
                        "description": "Optional: Specific anomaly ID (omit to clear all)"
                    }
                }
            }
        ),
    ]


def get_handlers() -> dict:
    """Return tool name to handler mapping."""
    return {
        "run_diagnosis": handle_run_diagnosis,
        "get_anomalies": handle_get_anomalies,
        "inject_test_anomaly": handle_inject_test_anomaly,
        "clear_anomaly": handle_clear_anomaly,
    }


async def handle_run_diagnosis(arguments: dict[str, Any]) -> list[TextContent]:
    """Run diagnosis."""
    global _diagnosis_history

    network_sim, _, tel_gen, _ = _get_components()

    node_id = arguments.get("node_id")
    check_types = arguments.get("check_types", ["all"])
    if "all" in check_types:
        check_types = ["cpu", "memory", "network", "latency", "errors"]

    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]
        nodes = [node]
    else:
        nodes = network_sim.get_all_nodes()

    diagnosis_id = f"diag_{uuid.uuid4().hex[:12]}"
    issues_found = []

    for node in nodes:
        snapshot = tel_gen.generate_snapshot(node)

        if "cpu" in check_types:
            cpu = snapshot.get_metric(MetricType.CPU_UTILIZATION)
            if cpu and cpu.value > 90:
                issues_found.append(
                    {"type": "HIGH_CPU", "severity": "critical" if cpu.value > 95 else "high", "node_id": node.id,
                     "value": cpu.value})
            elif cpu and cpu.value > 80:
                issues_found.append({"type": "HIGH_CPU", "severity": "medium", "node_id": node.id, "value": cpu.value})

        if "memory" in check_types:
            mem = snapshot.get_metric(MetricType.MEMORY_UTILIZATION)
            if mem and mem.value > 90:
                issues_found.append(
                    {"type": "MEMORY_LEAK", "severity": "critical" if mem.value > 95 else "high", "node_id": node.id,
                     "value": mem.value})

        if "network" in check_types:
            loss = snapshot.get_metric(MetricType.PACKET_LOSS)
            if loss and loss.value > 5:
                issues_found.append(
                    {"type": "PACKET_LOSS", "severity": "critical" if loss.value > 10 else "high", "node_id": node.id,
                     "value": loss.value})

        if "latency" in check_types:
            lat = snapshot.get_metric(MetricType.LATENCY)
            if lat and lat.value > 50:
                issues_found.append(
                    {"type": "HIGH_LATENCY", "severity": "critical" if lat.value > 100 else "high", "node_id": node.id,
                     "value": lat.value})

    overall = "critical" if any(i["severity"] == "critical" for i in issues_found) else \
        "high" if any(i["severity"] == "high" for i in issues_found) else \
            "medium" if issues_found else "healthy"

    report = {
        "diagnosis_id": diagnosis_id,
        "timestamp": datetime.utcnow().isoformat(),
        "scope": node_id or "network-wide",
        "nodes_analyzed": len(nodes),
        "overall_status": overall,
        "total_issues": len(issues_found),
        "issues": issues_found,
    }

    _diagnosis_history.append(report)

    return [TextContent(type="text", text=json.dumps(report, indent=2))]


async def handle_get_anomalies(arguments: dict[str, Any]) -> list[TextContent]:
    """Get anomalies."""
    _, _, _, anomaly_inj = _get_components()

    severity_filter = arguments.get("severity")
    node_filter = arguments.get("node_id")

    anomalies = anomaly_inj.get_active_anomalies()

    if severity_filter:
        severity_order = ["low", "medium", "high", "critical"]
        min_idx = severity_order.index(severity_filter)
        anomalies = [a for a in anomalies if severity_order.index(a.severity.value) >= min_idx]

    if node_filter:
        anomalies = [a for a in anomalies if a.node_id == node_filter]

    return [TextContent(type="text", text=json.dumps({
        "total_anomalies": len(anomalies),
        "anomalies": [{"id": a.id, "type": a.anomaly_type.value, "severity": a.severity.value, "node_id": a.node_id,
                       "description": a.description} for a in anomalies]
    }, indent=2))]


async def handle_inject_test_anomaly(arguments: dict[str, Any]) -> list[TextContent]:
    """Inject test anomaly."""
    _, _, _, anomaly_inj = _get_components()

    node_id = arguments.get("node_id")
    anomaly_type = AnomalyType(arguments.get("anomaly_type"))
    severity = AnomalySeverity(arguments.get("severity", "medium"))

    anomaly = anomaly_inj.inject_anomaly(node_id, anomaly_type, severity)

    if not anomaly:
        return [TextContent(type="text",
                            text=json.dumps({"success": False, "error": f"Node '{node_id}' not found"}, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "success": True,
        "anomaly": {"id": anomaly.id, "type": anomaly.anomaly_type.value, "severity": anomaly.severity.value,
                    "node_id": anomaly.node_id, "description": anomaly.description}
    }, indent=2))]


async def handle_clear_anomaly(arguments: dict[str, Any]) -> list[TextContent]:
    """Clear anomaly."""
    _, _, _, anomaly_inj = _get_components()

    anomaly_id = arguments.get("anomaly_id")

    if anomaly_id:
        success = anomaly_inj.clear_anomaly(anomaly_id)
        if success:
            return [TextContent(type="text",
                                text=json.dumps({"success": True, "message": f"Anomaly '{anomaly_id}' cleared"},
                                                indent=2))]
        else:
            return [TextContent(type="text",
                                text=json.dumps({"success": False, "error": f"Anomaly '{anomaly_id}' not found"},
                                                indent=2))]
    else:
        count = anomaly_inj.clear_all_anomalies()
        return [TextContent(type="text",
                            text=json.dumps({"success": True, "message": f"Cleared {count} anomalies"}, indent=2))]