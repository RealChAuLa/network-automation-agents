"""Network anomaly injector."""

import random
from datetime import datetime
from src.models.network import NetworkDevice


class AnomalyInjector:
    """Injects anomalies into network simulation."""

    def __init__(self, anomaly_probability: float = 0.1):
        self.anomaly_probability = anomaly_probability
        self.anomaly_types = [
            "cpu_spike",
            "memory_leak",
            "packet_loss",
            "latency_spike",
            "interface_down",
            "bgp_flap",
        ]

    def should_inject_anomaly(self) -> bool:
        """Determine if an anomaly should be injected."""
        return random.random() < self.anomaly_probability

    def generate_anomaly(self, device: NetworkDevice) -> dict:
        """Generate an anomaly event."""
        anomaly_type = random.choice(self.anomaly_types)

        anomaly = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "device_id": device.device_id,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "anomaly_type": anomaly_type,
            "severity": self._get_severity(anomaly_type),
            "description": self._get_description(anomaly_type),
        }

        return anomaly

    def _get_severity(self, anomaly_type: str) -> str:
        """Get severity level for anomaly type."""
        severity_map = {
            "cpu_spike": "WARNING",
            "memory_leak": "WARNING",
            "packet_loss": "ERROR",
            "latency_spike": "WARNING",
            "interface_down": "CRITICAL",
            "bgp_flap": "ERROR",
        }
        return severity_map.get(anomaly_type, "WARNING")

    def _get_description(self, anomaly_type: str) -> str:
        """Get description for anomaly type."""
        descriptions = {
            "cpu_spike": "CPU utilization exceeded 90% threshold",
            "memory_leak": "Memory usage steadily increasing, possible leak detected",
            "packet_loss": "Significant packet loss detected on interface",
            "latency_spike": "Network latency increased beyond acceptable limits",
            "interface_down": "Critical interface went down unexpectedly",
            "bgp_flap": "BGP neighbor session flapping detected",
        }
        return descriptions.get(anomaly_type, "Unknown anomaly detected")
