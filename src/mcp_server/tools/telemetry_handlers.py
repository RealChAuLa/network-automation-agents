"""
Telemetry Tool Handlers

MCP tools for accessing network telemetry and logs.
"""

import json
from datetime import datetime
from typing import Any, Optional

from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import MetricType

# Global instances (initialized lazily)
_network_sim: Optional[NetworkSimulator] = None
_log_generator: Optional[LogGenerator] = None
_telemetry_generator: Optional[TelemetryGenerator] = None
_anomaly_injector: Optional[AnomalyInjector] = None


def _get_components():
    """Get or initialize simulator components."""
    global _network_sim, _log_generator, _telemetry_generator, _anomaly_injector

    if _network_sim is None:
        _network_sim = NetworkSimulator()
        _network_sim.create_default_topology()
        _log_generator = LogGenerator(_network_sim)
        _telemetry_generator = TelemetryGenerator(_network_sim)
        _anomaly_injector = AnomalyInjector(_network_sim, _telemetry_generator, _log_generator)

    return _network_sim, _log_generator, _telemetry_generator, _anomaly_injector


def get_tools() -> list[Tool]:
    """Return list of telemetry tools."""
    return [
        Tool(
            name="get_network_logs",
            description="Get recent network logs from all or specific nodes.  Use this to check for errors, warnings, or specific events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Filter logs by specific node ID"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        "description": "Optional: Filter by minimum log level"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of logs to return (default: 50)",
                        "default": 50
                    },
                    "time_range_minutes": {
                        "type": "integer",
                        "description": "Time range in minutes (default: 60)",
                        "default": 60
                    }
                }
            }
        ),
        Tool(
            name="get_node_metrics",
            description="Get current telemetry metrics (CPU, memory, bandwidth, latency, etc.) for a specific node or all nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Get metrics for specific node (omit for all)"
                    },
                    "metric_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["cpu_utilization", "memory_utilization", "bandwidth_in", "bandwidth_out",
                                     "packet_loss", "latency", "error_count", "temperature"]
                        },
                        "description": "Optional: Specific metrics to return"
                    }
                }
            }
        ),
        Tool(
            name="get_metric_history",
            description="Get historical telemetry data for a node over a time period. Useful for trend analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID to get history for"
                    },
                    "metric_type": {
                        "type": "string",
                        "enum": ["cpu_utilization", "memory_utilization", "bandwidth_in", "bandwidth_out",
                                 "packet_loss", "latency"],
                        "description": "Type of metric to retrieve"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration to look back (default: 60)",
                        "default": 60
                    }
                },
                "required": ["node_id", "metric_type"]
            }
        ),
        Tool(
            name="get_alerts",
            description="Get current active alerts and anomalies in the network.",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Optional: Filter by minimum severity"
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Optional: Filter by specific node"
                    }
                }
            }
        ),
    ]


def get_handlers() -> dict:
    """Return tool name to handler mapping."""
    return {
        "get_network_logs": handle_get_network_logs,
        "get_node_metrics": handle_get_node_metrics,
        "get_metric_history": handle_get_metric_history,
        "get_alerts": handle_get_alerts,
    }


async def handle_get_network_logs(arguments: dict[str, Any]) -> list[TextContent]:
    """Get network logs."""
    network_sim, log_gen, _, _ = _get_components()

    node_id = arguments.get("node_id")
    level_filter = arguments.get("level")
    count = min(arguments.get("count", 50), 500)
    time_range = arguments.get("time_range_minutes", 60)

    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]
        nodes = [node]
    else:
        nodes = network_sim.get_all_nodes()

    logs = log_gen.generate_batch(count=count, time_range_minutes=time_range, nodes=nodes)

    if level_filter:
        level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        min_level_idx = level_order.index(level_filter)
        logs = [l for l in logs if level_order.index(l.level.value) >= min_level_idx]

    log_entries = [
        {
            "timestamp": log.timestamp.isoformat(),
            "node_id": log.node_id,
            "node_name": log.node_name,
            "level": log.level.value,
            "source": log.source,
            "message": log.message,
        }
        for log in logs[-count:]
    ]

    return [TextContent(type="text", text=json.dumps({
        "total_logs": len(log_entries),
        "time_range_minutes": time_range,
        "logs": log_entries
    }, indent=2))]


async def handle_get_node_metrics(arguments: dict[str, Any]) -> list[TextContent]:
    """Get node metrics."""
    network_sim, _, tel_gen, _ = _get_components()

    node_id = arguments.get("node_id")
    metric_types = arguments.get("metric_types")

    selected_metrics = None
    if metric_types:
        selected_metrics = [MetricType(mt) for mt in metric_types]

    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]
        snapshots = [tel_gen.generate_snapshot(node, metric_types=selected_metrics)]
    else:
        snapshots = tel_gen.generate_all_snapshots()

    nodes_data = []
    for snapshot in snapshots:
        metrics = {}
        for m in snapshot.metrics:
            if selected_metrics is None or m.metric_type in selected_metrics:
                metrics[m.metric_type.value] = {"value": m.value, "unit": m.unit}

        nodes_data.append({
            "node_id": snapshot.node_id,
            "node_name": snapshot.node_name,
            "status": snapshot.status.value,
            "timestamp": snapshot.timestamp.isoformat(),
            "metrics": metrics
        })

    return [TextContent(type="text", text=json.dumps({
        "node_count": len(nodes_data),
        "timestamp": datetime.utcnow().isoformat(),
        "nodes": nodes_data
    }, indent=2))]


async def handle_get_metric_history(arguments: dict[str, Any]) -> list[TextContent]:
    """Get metric history."""
    network_sim, _, tel_gen, _ = _get_components()

    node_id = arguments.get("node_id")
    metric_type_str = arguments.get("metric_type")
    duration = arguments.get("duration_minutes", 60)

    node = network_sim.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=json.dumps({"error": f"Node '{node_id}' not found"}, indent=2))]

    metric_type = MetricType(metric_type_str)
    timeseries = tel_gen.generate_timeseries(node, duration_minutes=duration, interval_seconds=60,
                                             metric_types=[metric_type])

    data_points = []
    for snapshot in timeseries:
        metric = snapshot.get_metric(metric_type)
        if metric:
            data_points.append(
                {"timestamp": snapshot.timestamp.isoformat(), "value": metric.value, "unit": metric.unit})

    return [TextContent(type="text", text=json.dumps({
        "node_id": node_id,
        "metric_type": metric_type_str,
        "data_points": data_points,
        "summary": {
            "min": min(d["value"] for d in data_points) if data_points else None,
            "max": max(d["value"] for d in data_points) if data_points else None,
            "avg": sum(d["value"] for d in data_points) / len(data_points) if data_points else None,
        }
    }, indent=2))]


async def handle_get_alerts(arguments: dict[str, Any]) -> list[TextContent]:
    """Get active alerts."""
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
        "total_alerts": len(anomalies),
        "timestamp": datetime.utcnow().isoformat(),
        "alerts": [
            {
                "id": a.id,
                "type": a.anomaly_type.value,
                "severity": a.severity.value,
                "node_id": a.node_id,
                "description": a.description,
                "started_at": a.started_at.isoformat(),
            }
            for a in anomalies
        ]
    }, indent=2))]