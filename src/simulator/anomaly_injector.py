"""
Anomaly Injector

Injects anomalies into the simulated network for testing agent responses.
"""

import random
from datetime import datetime, timedelta
from typing import Optional
from faker import Faker

from src.models.network import (
    Node,
    NodeStatus,
    MetricType,
    AnomalyType,
    AnomalySeverity,
    Anomaly,
    LogEntry,
)
from src.simulator.network_sim import NetworkSimulator
from src.simulator. log_generator import LogGenerator
from src.simulator. telemetry_generator import TelemetryGenerator


fake = Faker()


# Anomaly configurations
ANOMALY_CONFIGS = {
    AnomalyType. HIGH_CPU: {
        "affected_metrics": [MetricType.CPU_UTILIZATION],
        "metric_values": {
            AnomalySeverity.LOW: {"cpu_utilization": 75},
            AnomalySeverity. MEDIUM: {"cpu_utilization": 85},
            AnomalySeverity. HIGH: {"cpu_utilization": 92},
            AnomalySeverity.CRITICAL: {"cpu_utilization": 98},
        },
        "description": "High CPU utilization detected",
    },
    AnomalyType. MEMORY_LEAK: {
        "affected_metrics": [MetricType.MEMORY_UTILIZATION],
        "metric_values": {
            AnomalySeverity.LOW: {"memory_utilization": 78},
            AnomalySeverity. MEDIUM: {"memory_utilization": 85},
            AnomalySeverity. HIGH: {"memory_utilization": 92},
            AnomalySeverity. CRITICAL: {"memory_utilization": 97},
        },
        "description": "Memory leak detected - memory utilization increasing",
    },
    AnomalyType.INTERFACE_DOWN: {
        "affected_metrics": [MetricType. BANDWIDTH_IN, MetricType.BANDWIDTH_OUT],
        "metric_values": {
            AnomalySeverity. LOW: {"bandwidth_in": 0, "bandwidth_out": 0},
            AnomalySeverity.MEDIUM: {"bandwidth_in": 0, "bandwidth_out": 0},
            AnomalySeverity.HIGH: {"bandwidth_in": 0, "bandwidth_out": 0},
            AnomalySeverity.CRITICAL: {"bandwidth_in": 0, "bandwidth_out": 0},
        },
        "description": "Network interface is down",
    },
    AnomalyType.PACKET_LOSS: {
        "affected_metrics": [MetricType.PACKET_LOSS, MetricType.ERROR_COUNT],
        "metric_values": {
            AnomalySeverity. LOW: {"packet_loss": 2, "error_count": 50},
            AnomalySeverity. MEDIUM: {"packet_loss": 5, "error_count": 150},
            AnomalySeverity. HIGH: {"packet_loss": 10, "error_count": 500},
            AnomalySeverity. CRITICAL: {"packet_loss": 25, "error_count": 2000},
        },
        "description": "Significant packet loss detected",
    },
    AnomalyType. HIGH_LATENCY: {
        "affected_metrics": [MetricType.LATENCY],
        "metric_values": {
            AnomalySeverity.LOW: {"latency": 25},
            AnomalySeverity. MEDIUM: {"latency": 50},
            AnomalySeverity.HIGH: {"latency": 100},
            AnomalySeverity.CRITICAL: {"latency": 250},
        },
        "description": "High network latency detected",
    },
    AnomalyType. AUTH_FAILURE: {
        "affected_metrics": [],
        "metric_values": {},
        "description": "Multiple authentication failures detected",
    },
    AnomalyType.CONFIG_DRIFT: {
        "affected_metrics": [],
        "metric_values": {},
        "description": "Configuration drift detected - unexpected changes",
    },
    AnomalyType.SERVICE_DEGRADATION: {
        "affected_metrics": [
            MetricType. CPU_UTILIZATION,
            MetricType.LATENCY,
            MetricType.PACKET_LOSS,
        ],
        "metric_values": {
            AnomalySeverity.LOW: {"cpu_utilization": 70, "latency": 20, "packet_loss": 1},
            AnomalySeverity. MEDIUM: {"cpu_utilization": 80, "latency": 40, "packet_loss": 3},
            AnomalySeverity. HIGH: {"cpu_utilization": 88, "latency": 75, "packet_loss": 6},
            AnomalySeverity. CRITICAL: {"cpu_utilization": 95, "latency": 150, "packet_loss": 12},
        },
        "description": "Service degradation - multiple metrics affected",
    },
    AnomalyType.DISK_FULL: {
        "affected_metrics": [],
        "metric_values": {},
        "description": "Disk space critically low",
    },
    AnomalyType.TEMPERATURE_HIGH: {
        "affected_metrics": [MetricType. TEMPERATURE],
        "metric_values": {
            AnomalySeverity.LOW: {"temperature": 65},
            AnomalySeverity. MEDIUM: {"temperature": 75},
            AnomalySeverity.HIGH: {"temperature": 85},
            AnomalySeverity. CRITICAL: {"temperature": 95},
        },
        "description": "High temperature warning",
    },
}


# Pre-defined incident scenarios
INCIDENT_SCENARIOS = {
    "datacenter_cooling_failure": {
        "description": "Datacenter cooling system failure affecting multiple nodes",
        "anomalies": [
            {"node_pattern": "server_*", "type": AnomalyType. TEMPERATURE_HIGH, "severity": AnomalySeverity. CRITICAL},
            {"node_pattern": "switch_*", "type": AnomalyType.TEMPERATURE_HIGH, "severity": AnomalySeverity.HIGH},
            {"node_pattern": "router_*", "type": AnomalyType. TEMPERATURE_HIGH, "severity": AnomalySeverity.MEDIUM},
        ],
    },
    "ddos_attack": {
        "description": "DDoS attack causing high load on edge devices",
        "anomalies": [
            {"node_pattern": "firewall_*", "type": AnomalyType.HIGH_CPU, "severity": AnomalySeverity.CRITICAL},
            {"node_pattern": "router_edge_*", "type": AnomalyType.HIGH_CPU, "severity": AnomalySeverity.HIGH},
            {"node_pattern": "lb_*", "type": AnomalyType.HIGH_CPU, "severity": AnomalySeverity.HIGH},
        ],
    },
    "network_congestion": {
        "description": "Network congestion causing packet loss and latency",
        "anomalies": [
            {"node_pattern": "router_core_*", "type": AnomalyType.PACKET_LOSS, "severity": AnomalySeverity.HIGH},
            {"node_pattern": "switch_dist_*", "type": AnomalyType.HIGH_LATENCY, "severity": AnomalySeverity. MEDIUM},
        ],
    },
    "memory_leak_outbreak": {
        "description": "Memory leak affecting multiple servers",
        "anomalies": [
            {"node_pattern": "server_*", "type": AnomalyType. MEMORY_LEAK, "severity": AnomalySeverity.HIGH},
        ],
    },
    "link_failure": {
        "description": "Core link failure causing connectivity issues",
        "anomalies": [
            {"node_pattern": "router_core_01", "type": AnomalyType. INTERFACE_DOWN, "severity": AnomalySeverity. CRITICAL},
        ],
    },
    "security_breach_attempt": {
        "description": "Multiple authentication failures indicating breach attempt",
        "anomalies": [
            {"node_pattern": "firewall_*", "type": AnomalyType.AUTH_FAILURE, "severity": AnomalySeverity.CRITICAL},
            {"node_pattern": "router_*", "type": AnomalyType.AUTH_FAILURE, "severity": AnomalySeverity.HIGH},
            {"node_pattern": "server_*", "type": AnomalyType.AUTH_FAILURE, "severity": AnomalySeverity.HIGH},
        ],
    },
}


class AnomalyInjector:
    """
    Injects anomalies into the simulated network. 
    
    Example:
        >>> sim = NetworkSimulator()
        >>> sim.create_default_topology()
        >>> log_gen = LogGenerator(sim)
        >>> tel_gen = TelemetryGenerator(sim)
        >>> injector = AnomalyInjector(sim, tel_gen, log_gen)
        >>> anomaly = injector.inject_anomaly("router_core_01", AnomalyType.HIGH_CPU)
    """
    
    def __init__(
        self,
        network_sim: NetworkSimulator,
        telemetry_gen: TelemetryGenerator,
        log_gen: LogGenerator,
    ):
        self.network_sim = network_sim
        self.telemetry_gen = telemetry_gen
        self.log_gen = log_gen
        self._active_anomalies: dict[str, Anomaly] = {}
    
    def inject_anomaly(
        self,
        node_id: str,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity = AnomalySeverity.MEDIUM,
        duration_seconds: Optional[int] = None,
    ) -> Optional[Anomaly]:
        """
        Inject an anomaly on a specific node. 
        
        Args:
            node_id: Target node ID
            anomaly_type: Type of anomaly to inject
            severity: Severity level
            duration_seconds: How long the anomaly lasts (None = until cleared)
        
        Returns:
            Anomaly object if successful, None otherwise
        """
        node = self.network_sim.get_node(node_id)
        if node is None:
            return None
        
        config = ANOMALY_CONFIGS. get(anomaly_type)
        if config is None:
            return None
        
        # Create anomaly record
        anomaly = Anomaly(
            anomaly_type=anomaly_type,
            severity=severity,
            node_id=node_id,
            duration_seconds=duration_seconds,
            description=config["description"],
            affected_metrics=config["affected_metrics"],
            metadata={
                "node_name": node.name,
                "node_type": node.type.value,
            }
        )
        
        # Apply metric overrides
        metric_values = config["metric_values"]. get(severity, {})
        for metric_name, value in metric_values.items():
            # Convert metric name to MetricType
            try:
                metric_type = MetricType(metric_name)
                self.telemetry_gen.set_anomaly_override(node_id, metric_type, value)
            except ValueError:
                pass
        
        # Update node status
        if severity == AnomalySeverity.CRITICAL:
            self.network_sim. update_node_status(node_id, NodeStatus.CRITICAL)
        elif severity in [AnomalySeverity.HIGH, AnomalySeverity.MEDIUM]:
            self.network_sim.update_node_status(node_id, NodeStatus.WARNING)
        
        # Store active anomaly
        self._active_anomalies[anomaly. id] = anomaly
        
        return anomaly
    
    def clear_anomaly(self, anomaly_id: str) -> bool:
        """
        Clear an active anomaly. 
        
        Args:
            anomaly_id: ID of the anomaly to clear
        
        Returns:
            True if cleared, False if not found
        """
        anomaly = self._active_anomalies. get(anomaly_id)
        if anomaly is None:
            return False
        
        # Clear metric overrides
        self.telemetry_gen.clear_anomaly_override(anomaly.node_id)
        
        # Reset node status
        self.network_sim. update_node_status(anomaly.node_id, NodeStatus.HEALTHY)
        
        # Mark anomaly as ended
        anomaly. end()
        
        # Remove from active
        del self._active_anomalies[anomaly_id]
        
        return True
    
    def clear_all_anomalies(self) -> int:
        """
        Clear all active anomalies. 
        
        Returns:
            Number of anomalies cleared
        """
        count = len(self._active_anomalies)
        anomaly_ids = list(self._active_anomalies.keys())
        for anomaly_id in anomaly_ids:
            self.clear_anomaly(anomaly_id)
        return count
    
    def get_active_anomalies(self) -> list[Anomaly]:
        """Get all currently active anomalies."""
        return list(self._active_anomalies.values())
    
    def get_anomaly(self, anomaly_id: str) -> Optional[Anomaly]:
        """Get a specific anomaly by ID."""
        return self._active_anomalies.get(anomaly_id)
    
    def inject_random_anomaly(
        self,
        severity: Optional[AnomalySeverity] = None,
        node_types: Optional[list] = None,
    ) -> Optional[Anomaly]:
        """
        Inject a random anomaly on a random node. 
        
        Args:
            severity: Specific severity (random if None)
            node_types: Limit to specific node types (all if None)
        
        Returns:
            Anomaly object if successful
        """
        nodes = self.network_sim.get_all_nodes()
        if node_types:
            nodes = [n for n in nodes if n.type in node_types]
        
        if not nodes:
            return None
        
        node = random.choice(nodes)
        anomaly_type = random.choice(list(AnomalyType))
        
        if severity is None:
            severity = random. choice(list(AnomalySeverity))
        
        return self.inject_anomaly(node.id, anomaly_type, severity)
    
    def _match_node_pattern(self, node_id: str, pattern: str) -> bool:
        """Check if a node ID matches a pattern (supports * wildcard)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return node_id.startswith(prefix)
        return node_id == pattern
    
    def create_incident_scenario(
        self,
        scenario_name: str,
    ) -> list[Anomaly]:
        """
        Create a pre-defined incident scenario. 
        
        Args:
            scenario_name: Name of the scenario
        
        Returns:
            List of created anomalies
        """
        scenario = INCIDENT_SCENARIOS.get(scenario_name)
        if scenario is None:
            return []
        
        created_anomalies = []
        nodes = self.network_sim.get_all_nodes()
        
        for anomaly_config in scenario["anomalies"]:
            pattern = anomaly_config["node_pattern"]
            anomaly_type = anomaly_config["type"]
            severity = anomaly_config["severity"]
            
            # Find matching nodes
            matching_nodes = [
                n for n in nodes
                if self._match_node_pattern(n.id, pattern)
            ]
            
            # Inject anomaly on each matching node
            for node in matching_nodes:
                anomaly = self.inject_anomaly(node. id, anomaly_type, severity)
                if anomaly:
                    anomaly.metadata["scenario"] = scenario_name
                    anomaly. metadata["scenario_description"] = scenario["description"]
                    created_anomalies. append(anomaly)
        
        return created_anomalies
    
    def get_available_scenarios(self) -> dict[str, str]:
        """Get available incident scenarios with descriptions."""
        return {
            name: config["description"]
            for name, config in INCIDENT_SCENARIOS.items()
        }
    
    def generate_anomaly_logs(
        self,
        anomaly: Anomaly,
        count: int = 5,
    ) -> list[LogEntry]:
        """
        Generate logs related to an anomaly. 
        
        Args:
            anomaly: The anomaly to generate logs for
            count: Number of logs to generate
        
        Returns:
            List of LogEntry objects
        """
        node = self.network_sim.get_node(anomaly.node_id)
        if node is None:
            return []
        
        return self.log_gen. generate_anomaly_logs(
            node,
            anomaly. anomaly_type. value,
            count
        )