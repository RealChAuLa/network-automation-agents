"""Network log generator."""

import json
import random
from datetime import datetime, UTC
from faker import Faker
from src.models.network import NetworkDevice


class LogGenerator:
    """Generates network device logs."""

    def __init__(self):
        self.faker = Faker()

    def generate_log(self, device: NetworkDevice) -> dict:
        """Generate a log entry for a network device."""
        log_levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        log_messages = {
            "INFO": [
                "Interface GigabitEthernet0/1 is up",
                "BGP neighbor established",
                "OSPF adjacency formed",
                "Configuration saved",
                "System health check passed",
            ],
            "WARNING": [
                "High CPU utilization detected",
                "Memory usage above threshold",
                "Interface flapping detected",
                "Packet loss detected",
                "Temperature rising",
            ],
            "ERROR": [
                "Interface GigabitEthernet0/2 is down",
                "BGP neighbor down",
                "OSPF adjacency lost",
                "Authentication failed",
                "Hardware failure detected",
            ],
            "DEBUG": [
                "Routing table updated",
                "ARP cache refreshed",
                "SNMP poll completed",
                "Configuration backup initiated",
                "Keepalive received",
            ],
        }

        level = random.choice(log_levels)
        message = random.choice(log_messages[level])

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "device_id": device.device_id,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "level": level,
            "message": message,
            "facility": self._get_facility(device.device_type),
        }

        return log_entry

    def _get_facility(self, device_type: str) -> str:
        """Get the syslog facility based on device type."""
        facilities = {
            "router": ["ROUTING", "BGP", "OSPF", "INTERFACE"],
            "switch": ["VLAN", "STP", "PORT", "INTERFACE"],
            "firewall": ["SECURITY", "POLICY", "VPN", "IPS"],
        }
        return random.choice(facilities.get(device_type, ["SYSTEM"]))

    def generate_batch(self, devices: list[NetworkDevice], count: int = 10) -> list[dict]:
        """Generate a batch of log entries."""
        logs = []
        for _ in range(count):
            device = random.choice(devices)
            log = self.generate_log(device)
            logs.append(log)
        return logs

    def print_logs(self, logs: list[dict]):
        """Print logs in a formatted way."""
        for log in logs:
            print(json.dumps(log, indent=2))
