"""
Telemetry Generator

Generates realistic network telemetry and metrics data.
"""

import random
import math
from datetime import datetime, timedelta
from typing import Optional

from src.models.network import (
    Node,
    NodeType,
    NodeStatus,
    MetricType,
    MetricReading,
    TelemetrySnapshot,
    AnomalyType,
)
from src.simulator.network_sim import NetworkSimulator


# SNMP OID mappings (mock)
SNMP_OIDS = {
    MetricType.CPU_UTILIZATION: "1.3.6.1.4.1.9.9.109.1.1.1.1.3",
    MetricType.MEMORY_UTILIZATION: "1.3.6.1.4.1.9.9.48.1.1.1.5",
    MetricType.BANDWIDTH_IN: "1.3.6.1.2.1.2.2.1.10",
    MetricType.BANDWIDTH_OUT: "1.3.6.1.2.1.2.2.1.16",
    MetricType.PACKET_LOSS: "1.3.6.1.2.1.2.2.1.14",
    MetricType.LATENCY: "1.3.6.1.4.1.9.9.42.1.2.10.1.1",
    MetricType.ERROR_COUNT: "1.3.6.1.2.1.2.2.1.14",
    MetricType.TEMPERATURE: "1.3.6.1.4.1.9.9.13.1.3.1.3",
    MetricType. UPTIME: "1.3.6.1.2.1.1.3.0",
    MetricType. INTERFACE_STATUS: "1.3.6.1.2.1.2.2.1.8",
}

# Baseline values by node type
BASELINES = {
    NodeType.ROUTER_CORE: {
        MetricType.CPU_UTILIZATION: {"min": 20, "max": 45, "unit": "%"},
        MetricType. MEMORY_UTILIZATION: {"min": 40, "max": 60, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 5000, "max": 25000, "unit": "Mbps"},
        MetricType. BANDWIDTH_OUT: {"min": 5000, "max": 25000, "unit": "Mbps"},
        MetricType.PACKET_LOSS: {"min": 0, "max": 0.1, "unit": "%"},
        MetricType.LATENCY: {"min": 0.5, "max": 2.0, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 10, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 35, "max": 55, "unit": "°C"},
    },
    NodeType.ROUTER_EDGE: {
        MetricType.CPU_UTILIZATION: {"min": 15, "max": 40, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 35, "max": 55, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 1000, "max": 8000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 1000, "max": 8000, "unit": "Mbps"},
        MetricType. PACKET_LOSS: {"min": 0, "max": 0.2, "unit": "%"},
        MetricType.LATENCY: {"min": 1.0, "max": 5.0, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 20, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 30, "max": 50, "unit": "°C"},
    },
    NodeType.SWITCH_DISTRIBUTION: {
        MetricType.CPU_UTILIZATION: {"min": 10, "max": 35, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 30, "max": 50, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 2000, "max": 15000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 2000, "max": 15000, "unit": "Mbps"},
        MetricType. PACKET_LOSS: {"min": 0, "max": 0.05, "unit": "%"},
        MetricType.LATENCY: {"min": 0.1, "max": 1.0, "unit": "ms"},
        MetricType.ERROR_COUNT: {"min": 0, "max": 5, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 30, "max": 45, "unit": "°C"},
    },
    NodeType.SWITCH_ACCESS: {
        MetricType.CPU_UTILIZATION: {"min": 5, "max": 25, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 20, "max": 40, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 500, "max": 5000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 500, "max": 5000, "unit": "Mbps"},
        MetricType.PACKET_LOSS: {"min": 0, "max": 0.05, "unit": "%"},
        MetricType.LATENCY: {"min": 0.1, "max": 0.5, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 5, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 25, "max": 40, "unit": "°C"},
    },
    NodeType.SERVER: {
        MetricType.CPU_UTILIZATION: {"min": 20, "max": 60, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 50, "max": 75, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 100, "max": 2000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 100, "max": 2000, "unit": "Mbps"},
        MetricType. PACKET_LOSS: {"min": 0, "max": 0.01, "unit": "%"},
        MetricType.LATENCY: {"min": 0.1, "max": 1.0, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 2, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 40, "max": 65, "unit": "°C"},
    },
    NodeType.FIREWALL: {
        MetricType.CPU_UTILIZATION: {"min": 30, "max": 55, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 45, "max": 65, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 3000, "max": 20000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 3000, "max": 20000, "unit": "Mbps"},
        MetricType. PACKET_LOSS: {"min": 0, "max": 0.1, "unit": "%"},
        MetricType. LATENCY: {"min": 0.5, "max": 3.0, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 15, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 35, "max": 55, "unit": "°C"},
    },
    NodeType.LOAD_BALANCER: {
        MetricType.CPU_UTILIZATION: {"min": 25, "max": 50, "unit": "%"},
        MetricType.MEMORY_UTILIZATION: {"min": 40, "max": 60, "unit": "%"},
        MetricType.BANDWIDTH_IN: {"min": 5000, "max": 30000, "unit": "Mbps"},
        MetricType.BANDWIDTH_OUT: {"min": 5000, "max": 30000, "unit": "Mbps"},
        MetricType. PACKET_LOSS: {"min": 0, "max": 0.05, "unit": "%"},
        MetricType. LATENCY: {"min": 0.2, "max": 2.0, "unit": "ms"},
        MetricType. ERROR_COUNT: {"min": 0, "max": 10, "unit": "count"},
        MetricType.TEMPERATURE: {"min": 35, "max": 50, "unit": "°C"},
    },
}

# Default baseline for unknown types
DEFAULT_BASELINE = {
    MetricType.CPU_UTILIZATION: {"min": 10, "max": 50, "unit": "%"},
    MetricType.MEMORY_UTILIZATION: {"min": 30, "max": 60, "unit": "%"},
    MetricType.BANDWIDTH_IN: {"min": 100, "max": 1000, "unit": "Mbps"},
    MetricType.BANDWIDTH_OUT: {"min": 100, "max": 1000, "unit": "Mbps"},
    MetricType.PACKET_LOSS: {"min": 0, "max": 0.1, "unit": "%"},
    MetricType. LATENCY: {"min": 0.5, "max": 5.0, "unit": "ms"},
    MetricType. ERROR_COUNT: {"min": 0, "max": 10, "unit": "count"},
    MetricType.TEMPERATURE: {"min": 30, "max": 50, "unit": "°C"},
}


class TelemetryGenerator:
    """
    Generates realistic network telemetry data.

    Example:
        >>> sim = NetworkSimulator()
        >>> sim.create_default_topology()
        >>> tel_gen = TelemetryGenerator(sim)
        >>> snapshot = tel_gen. generate_snapshot(sim.get_node("router_core_01"))
    """

    def __init__(self, network_sim: NetworkSimulator):
        self.network_sim = network_sim
        self._anomaly_overrides: dict[str, dict[MetricType, float]] = {}

    def get_baseline(self, node: Node) -> dict[MetricType, dict]:
        """Get baseline metrics for a node type."""
        return BASELINES. get(node.type, DEFAULT_BASELINE)

    def _add_noise(self, value: float, noise_percent: float = 5.0) -> float:
        """Add random noise to a value."""
        noise = value * (noise_percent / 100) * random.uniform(-1, 1)
        return value + noise

    def _add_time_pattern(self, base_value: float, hour: int) -> float:
        """
        Add time-of-day pattern to metrics.
        Higher values during business hours (9-17).
        """
        # Sinusoidal pattern peaking at 13:00
        time_factor = 0.3 * math.sin((hour - 7) * math.pi / 12)
        if 9 <= hour <= 17:
            time_factor = abs(time_factor) + 0.1
        return base_value * (1 + time_factor)

    def set_anomaly_override(
        self,
        node_id: str,
        metric_type: MetricType,
        value: float
    ) -> None:
        """Set an override value for a metric (used by anomaly injector)."""
        if node_id not in self._anomaly_overrides:
            self._anomaly_overrides[node_id] = {}
        self._anomaly_overrides[node_id][metric_type] = value

    def clear_anomaly_override(self, node_id: str, metric_type: Optional[MetricType] = None) -> None:
        """Clear anomaly overrides for a node."""
        if node_id in self._anomaly_overrides:
            if metric_type:
                self._anomaly_overrides[node_id]. pop(metric_type, None)
            else:
                del self._anomaly_overrides[node_id]

    def generate_metric(
        self,
        node: Node,
        metric_type: MetricType,
        timestamp: Optional[datetime] = None,
    ) -> MetricReading:
        """
        Generate a single metric reading for a node.

        Args:
            node: The network node
            metric_type: Type of metric to generate
            timestamp: Timestamp for the reading

        Returns:
            MetricReading object
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        baseline = self.get_baseline(node)
        metric_baseline = baseline.get(metric_type, DEFAULT_BASELINE. get(metric_type))

        if metric_baseline is None:
            metric_baseline = {"min": 0, "max": 100, "unit": "unknown"}

        # Check for anomaly override
        if node. id in self._anomaly_overrides:
            override = self._anomaly_overrides[node.id]. get(metric_type)
            if override is not None:
                return MetricReading(
                    timestamp=timestamp,
                    node_id=node.id,
                    metric_type=metric_type,
                    value=round(override, 2),
                    unit=metric_baseline["unit"],
                    oid=SNMP_OIDS.get(metric_type),
                    metadata={"anomaly_override": True}
                )

        # Generate base value
        base_value = random.uniform(metric_baseline["min"], metric_baseline["max"])

        # Add time-of-day pattern
        hour = timestamp.hour
        value = self._add_time_pattern(base_value, hour)

        # Add noise
        value = self._add_noise(value)

        # Clamp to reasonable bounds
        if metric_type in [MetricType.CPU_UTILIZATION, MetricType. MEMORY_UTILIZATION]:
            value = max(0, min(100, value))
        elif metric_type == MetricType.PACKET_LOSS:
            value = max(0, min(100, value))
        else:
            value = max(0, value)

        return MetricReading(
            timestamp=timestamp,
            node_id=node. id,
            metric_type=metric_type,
            value=round(value, 2),
            unit=metric_baseline["unit"],
            oid=SNMP_OIDS.get(metric_type),
            metadata={}
        )

    def generate_snapshot(
        self,
        node: Node,
        timestamp: Optional[datetime] = None,
        metric_types: Optional[list[MetricType]] = None,
    ) -> TelemetrySnapshot:
        """
        Generate a complete telemetry snapshot for a node.

        Args:
            node: The network node
            timestamp: Timestamp for the snapshot
            metric_types: Specific metrics to include (None = all)

        Returns:
            TelemetrySnapshot object
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        if metric_types is None:
            metric_types = [
                MetricType.CPU_UTILIZATION,
                MetricType. MEMORY_UTILIZATION,
                MetricType.BANDWIDTH_IN,
                MetricType.BANDWIDTH_OUT,
                MetricType. PACKET_LOSS,
                MetricType.LATENCY,
                MetricType.ERROR_COUNT,
                MetricType.TEMPERATURE,
            ]

        metrics = [
            self.generate_metric(node, mt, timestamp)
            for mt in metric_types
        ]

        # Determine status based on metrics
        status = self._determine_status(metrics)

        return TelemetrySnapshot(
            timestamp=timestamp,
            node_id=node.id,
            node_name=node.name,
            metrics=metrics,
            status=status,
            metadata={
                "node_type": node. type.value,
                "node_ip": node.ip_address,
            }
        )

    def _determine_status(self, metrics: list[MetricReading]) -> NodeStatus:
        """Determine node status based on metrics."""
        critical_count = 0
        warning_count = 0

        for metric in metrics:
            if metric.metric_type == MetricType.CPU_UTILIZATION:
                if metric.value > 95:
                    critical_count += 1
                elif metric.value > 80:
                    warning_count += 1
            elif metric.metric_type == MetricType. MEMORY_UTILIZATION:
                if metric.value > 95:
                    critical_count += 1
                elif metric. value > 85:
                    warning_count += 1
            elif metric.metric_type == MetricType.PACKET_LOSS:
                if metric.value > 5:
                    critical_count += 1
                elif metric.value > 1:
                    warning_count += 1
            elif metric.metric_type == MetricType. LATENCY:
                if metric.value > 100:
                    critical_count += 1
                elif metric.value > 50:
                    warning_count += 1

        if critical_count > 0:
            return NodeStatus. CRITICAL
        elif warning_count > 0:
            return NodeStatus.WARNING
        return NodeStatus. HEALTHY

    def generate_all_snapshots(
        self,
        timestamp: Optional[datetime] = None,
    ) -> list[TelemetrySnapshot]:
        """Generate snapshots for all nodes in the network."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        return [
            self. generate_snapshot(node, timestamp)
            for node in self. network_sim.get_all_nodes()
        ]

    def generate_timeseries(
        self,
        node: Node,
        duration_minutes: int = 60,
        interval_seconds: int = 60,
        metric_types: Optional[list[MetricType]] = None,
    ) -> list[TelemetrySnapshot]:
        """
        Generate a time series of telemetry snapshots.

        Args:
            node: The network node
            duration_minutes: Total duration in minutes
            interval_seconds: Interval between snapshots in seconds
            metric_types: Specific metrics to include

        Returns:
            List of TelemetrySnapshot objects
        """
        snapshots = []
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=duration_minutes)

        current_time = start_time
        while current_time <= now:
            snapshot = self.generate_snapshot(node, current_time, metric_types)
            snapshots.append(snapshot)
            current_time += timedelta(seconds=interval_seconds)

        return snapshots