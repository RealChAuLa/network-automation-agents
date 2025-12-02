"""Network telemetry generator."""

import random
from datetime import datetime, UTC
from src.models.network import NetworkDevice


class TelemetryGenerator:
    """Generates network device telemetry data."""

    def __init__(self):
        self.baseline_cpu = 30
        self.baseline_memory = 40
        self.baseline_bandwidth = 50

    def generate_telemetry(self, device: NetworkDevice, inject_anomaly: bool = False) -> dict:
        """Generate telemetry data for a network device."""
        if inject_anomaly:
            cpu_usage = random.randint(85, 99)
            memory_usage = random.randint(88, 98)
            bandwidth_usage = random.randint(90, 100)
        else:
            cpu_usage = self.baseline_cpu + random.randint(-10, 20)
            memory_usage = self.baseline_memory + random.randint(-10, 20)
            bandwidth_usage = self.baseline_bandwidth + random.randint(-20, 30)

        # Ensure values are within valid range
        cpu_usage = max(0, min(100, cpu_usage))
        memory_usage = max(0, min(100, memory_usage))
        bandwidth_usage = max(0, min(100, bandwidth_usage))

        telemetry = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "device_id": device.device_id,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "metrics": {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "bandwidth_usage": bandwidth_usage,
                "temperature": random.randint(35, 65),
                "uptime_seconds": random.randint(3600, 31536000),
                "packet_loss": (
                    round(random.uniform(0, 2), 2)
                    if inject_anomaly
                    else round(random.uniform(0, 0.5), 2)
                ),
                "latency_ms": random.randint(50, 200) if inject_anomaly else random.randint(1, 10),
            },
        }

        return telemetry

    def generate_batch(
        self, devices: list[NetworkDevice], count: int = 10, anomaly_rate: float = 0.1
    ) -> list[dict]:
        """Generate a batch of telemetry entries."""
        telemetry_data = []
        for _ in range(count):
            device = random.choice(devices)
            inject_anomaly = random.random() < anomaly_rate
            telemetry = self.generate_telemetry(device, inject_anomaly)
            telemetry_data.append(telemetry)
        return telemetry_data
