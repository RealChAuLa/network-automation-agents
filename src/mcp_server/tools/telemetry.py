"""
Telemetry Tools

MCP tools for accessing network telemetry and logs.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import LogLevel, MetricType

# Global instances (initialized when tools are registered)
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


def register_telemetry_tools(server: Server) -> None:
    """Register telemetry-related tools with the MCP server."""

    @server.list_tools()
    async def list_telemetry_tools() -> list[Tool]:
        """List telemetry tools."""
        return [
            Tool(
                name="get_network_logs",
                description="""
                    Get recent network logs from all or specific nodes.
                    Use this to check for errors, warnings, or specific events in the network.
                    Returns logs sorted by timestamp (newest first).
                """,
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
                            "description": "Optional: Filter by log level (minimum level)"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of logs to return (default: 50, max: 500)",
                            "default": 50
                        },
                        "time_range_minutes": {
                            "type": "integer",
                            "description": "Time range in minutes to look back (default: 60)",
                            "default": 60
                        }
                    }
                }
            ),
            Tool(
                name="get_node_metrics",
                description="""
                    Get current telemetry metrics for a specific node or all nodes.
                    Returns CPU, memory, bandwidth, latency, packet loss, temperature, etc.
                    Use this to check the health status of network devices.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Optional: Get metrics for a specific node (omit for all nodes)"
                        },
                        "metric_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "cpu_utilization",
                                    "memory_utilization",
                                    "bandwidth_in",
                                    "bandwidth_out",
                                    "packet_loss",
                                    "latency",
                                    "error_count",
                                    "temperature"
                                ]
                            },
                            "description": "Optional: Specific metrics to return (omit for all)"
                        }
                    }
                }
            ),
            Tool(
                name="get_metric_history",
                description="""
                    Get historical telemetry data for a node over a time period.
                    Useful for trend analysis and identifying patterns.
                """,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Node ID to get history for"
                        },
                        "metric_type": {
                            "type": "string",
                            "enum": [
                                "cpu_utilization",
                                "memory_utilization",
                                "bandwidth_in",
                                "bandwidth_out",
                                "packet_loss",
                                "latency"
                            ],
                            "description": "Type of metric to retrieve"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration to look back in minutes (default: 60)",
                            "default": 60
                        },
                        "interval_seconds": {
                            "type": "integer",
                            "description": "Interval between data points in seconds (default: 60)",
                            "default": 60
                        }
                    },
                    "required": ["node_id", "metric_type"]
                }
            ),
            Tool(
                name="get_alerts",
                description="""
                    Get current active alerts and anomalies in the network.
                    Returns information about ongoing issues that need attention.
                """,
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

    @server.call_tool()
    async def call_telemetry_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle telemetry tool calls."""

        network_sim, log_gen, tel_gen, anomaly_inj = _get_components()

        if name == "get_network_logs":
            return await _get_network_logs(log_gen, network_sim, arguments)
        elif name == "get_node_metrics":
            return await _get_node_metrics(tel_gen, network_sim, arguments)
        elif name == "get_metric_history":
            return await _get_metric_history(tel_gen, network_sim, arguments)
        elif name == "get_alerts":
            return await _get_alerts(anomaly_inj, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _get_network_logs(
        log_gen: LogGenerator,
        network_sim: NetworkSimulator,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get network logs."""
    node_id = arguments.get("node_id")
    level_filter = arguments.get("level")
    count = min(arguments.get("count", 50), 500)
    time_range = arguments.get("time_range_minutes", 60)

    # Get nodes to generate logs for
    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]
        nodes = [node]
    else:
        nodes = network_sim.get_all_nodes()

    # Generate logs
    logs = log_gen.generate_batch(count=count, time_range_minutes=time_range, nodes=nodes)

    # Filter by level if specified
    if level_filter:
        level_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        min_level_idx = level_order.index(level_filter)
        logs = [l for l in logs if level_order.index(l.level.value) >= min_level_idx]

    # Format output
    log_entries = []
    for log in logs[-count:]:  # Get last N logs
        log_entries.append({
            "timestamp": log.timestamp.isoformat(),
            "node_id": log.node_id,
            "node_name": log.node_name,
            "level": log.level.value,
            "source": log.source,
            "message": log.message,
        })

    result = {
        "total_logs": len(log_entries),
        "time_range_minutes": time_range,
        "logs": log_entries
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_node_metrics(
        tel_gen: TelemetryGenerator,
        network_sim: NetworkSimulator,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get node metrics."""
    node_id = arguments.get("node_id")
    metric_types = arguments.get("metric_types")

    # Parse metric types
    selected_metrics = None
    if metric_types:
        selected_metrics = [MetricType(mt) for mt in metric_types]

    # Get snapshots
    if node_id:
        node = network_sim.get_node(node_id)
        if not node:
            return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]
        snapshots = [tel_gen.generate_snapshot(node, metric_types=selected_metrics)]
    else:
        snapshots = tel_gen.generate_all_snapshots()

    # Format output
    nodes_data = []
    for snapshot in snapshots:
        metrics = {}
        for m in snapshot.metrics:
            if selected_metrics is None or m.metric_type in selected_metrics:
                metrics[m.metric_type.value] = {
                    "value": m.value,
                    "unit": m.unit,
                    "oid": m.oid
                }

        nodes_data.append({
            "node_id": snapshot.node_id,
            "node_name": snapshot.node_name,
            "status": snapshot.status.value,
            "timestamp": snapshot.timestamp.isoformat(),
            "metrics": metrics
        })

    result = {
        "node_count": len(nodes_data),
        "timestamp": datetime.utcnow().isoformat(),
        "nodes": nodes_data
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_metric_history(
        tel_gen: TelemetryGenerator,
        network_sim: NetworkSimulator,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get historical metrics for a node."""
    node_id = arguments.get("node_id")
    metric_type_str = arguments.get("metric_type")
    duration = arguments.get("duration_minutes", 60)
    interval = arguments.get("interval_seconds", 60)

    node = network_sim.get_node(node_id)
    if not node:
        return [TextContent(type="text", text=f"Error: Node '{node_id}' not found")]

    metric_type = MetricType(metric_type_str)

    # Generate time series
    timeseries = tel_gen.generate_timeseries(
        node,
        duration_minutes=duration,
        interval_seconds=interval,
        metric_types=[metric_type]
    )

    # Extract the specific metric values
    data_points = []
    for snapshot in timeseries:
        metric = snapshot.get_metric(metric_type)
        if metric:
            data_points.append({
                "timestamp": snapshot.timestamp.isoformat(),
                "value": metric.value,
                "unit": metric.unit
            })

    result = {
        "node_id": node_id,
        "node_name": node.name,
        "metric_type": metric_type_str,
        "duration_minutes": duration,
        "interval_seconds": interval,
        "data_points": data_points,
        "summary": {
            "min": min(d["value"] for d in data_points) if data_points else None,
            "max": max(d["value"] for d in data_points) if data_points else None,
            "avg": sum(d["value"] for d in data_points) / len(data_points) if data_points else None,
        }
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_alerts(
        anomaly_inj: AnomalyInjector,
        arguments: dict[str, Any]
) -> list[TextContent]:
    """Get active alerts/anomalies."""
    severity_filter = arguments.get("severity")
    node_filter = arguments.get("node_id")

    # Get active anomalies
    anomalies = anomaly_inj.get_active_anomalies()

    # Filter by severity
    if severity_filter:
        severity_order = ["low", "medium", "high", "critical"]
        min_severity_idx = severity_order.index(severity_filter)
        anomalies = [a for a in anomalies if severity_order.index(a.severity.value) >= min_severity_idx]

    # Filter by node
    if node_filter:
        anomalies = [a for a in anomalies if a.node_id == node_filter]

    # Format output
    alerts = []
    for anomaly in anomalies:
        alerts.append({
            "id": anomaly.id,
            "type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "node_id": anomaly.node_id,
            "description": anomaly.description,
            "started_at": anomaly.started_at.isoformat(),
            "duration_seconds": anomaly.duration_seconds,
            "affected_metrics": [m.value for m in anomaly.affected_metrics],
        })

    result = {
        "total_alerts": len(alerts),
        "timestamp": datetime.utcnow().isoformat(),
        "alerts": alerts
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]