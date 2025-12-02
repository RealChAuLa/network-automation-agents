"""Network device models."""

from dataclasses import dataclass
from typing import Literal


DeviceType = Literal["router", "switch", "firewall"]


@dataclass
class NetworkDevice:
    """Represents a network device."""

    device_id: str
    device_type: DeviceType
    hostname: str
    ip_address: str
    location: str
    status: str = "active"

    def __str__(self):
        return (
            f"{self.device_type.upper()} {self.hostname} "
            f"({self.ip_address}) - {self.location} [{self.status}]"
        )


@dataclass
class NetworkTopology:
    """Represents the network topology."""

    routers: list[NetworkDevice]
    switches: list[NetworkDevice]
    firewalls: list[NetworkDevice]

    def get_all_devices(self) -> list[NetworkDevice]:
        """Get all devices in the topology."""
        return self.routers + self.switches + self.firewalls

    def get_device_by_id(self, device_id: str) -> NetworkDevice | None:
        """Get a device by its ID."""
        for device in self.get_all_devices():
            if device.device_id == device_id:
                return device
        return None

    def get_device_count(self) -> dict[str, int]:
        """Get count of devices by type."""
        return {
            "routers": len(self.routers),
            "switches": len(self.switches),
            "firewalls": len(self.firewalls),
            "total": len(self.get_all_devices()),
        }
