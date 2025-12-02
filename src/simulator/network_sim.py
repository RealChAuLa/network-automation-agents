"""Network topology simulator."""

import os
from faker import Faker
from src.models.network import NetworkDevice, NetworkTopology


class NetworkSimulator:
    """Simulates a network topology."""

    def __init__(self):
        self.faker = Faker()
        self.topology = None

    def generate_topology(
        self, num_routers: int = 5, num_switches: int = 8, num_firewalls: int = 3
    ) -> NetworkTopology:
        """Generate a network topology with specified number of devices."""
        routers = [self._create_device("router", i) for i in range(num_routers)]
        switches = [self._create_device("switch", i) for i in range(num_switches)]
        firewalls = [self._create_device("firewall", i) for i in range(num_firewalls)]

        self.topology = NetworkTopology(routers=routers, switches=switches, firewalls=firewalls)
        return self.topology

    def _create_device(self, device_type: str, index: int) -> NetworkDevice:
        """Create a network device with random data."""
        device_id = f"{device_type[:3].upper()}-{index:03d}"
        hostname = f"{device_type}-{self.faker.word()}-{index:02d}"
        ip_address = self.faker.ipv4_private()
        location = f"{self.faker.city()}-{self.faker.building_number()}"

        return NetworkDevice(
            device_id=device_id,
            device_type=device_type,
            hostname=hostname,
            ip_address=ip_address,
            location=location,
            status="active",
        )

    def get_topology(self) -> NetworkTopology:
        """Get the current topology, generating one if it doesn't exist."""
        if self.topology is None:
            num_routers = int(os.getenv("NUM_ROUTERS", "5"))
            num_switches = int(os.getenv("NUM_SWITCHES", "8"))
            num_firewalls = int(os.getenv("NUM_FIREWALLS", "3"))
            self.generate_topology(num_routers, num_switches, num_firewalls)
        return self.topology

    def print_topology(self):
        """Print the network topology."""
        topology = self.get_topology()
        counts = topology.get_device_count()

        print("\n" + "=" * 80)
        print("NETWORK TOPOLOGY")
        print("=" * 80)
        print(f"Total Devices: {counts['total']}")
        print(f"  - Routers: {counts['routers']}")
        print(f"  - Switches: {counts['switches']}")
        print(f"  - Firewalls: {counts['firewalls']}")
        print("=" * 80)

        print("\nROUTERS:")
        print("-" * 80)
        for router in topology.routers:
            print(f"  {router}")

        print("\nSWITCHES:")
        print("-" * 80)
        for switch in topology.switches:
            print(f"  {switch}")

        print("\nFIREWALLS:")
        print("-" * 80)
        for firewall in topology.firewalls:
            print(f"  {firewall}")

        print("=" * 80 + "\n")
