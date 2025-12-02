"""
Log Generator

Generates realistic syslog-style logs for network devices.
"""

import random
from datetime import datetime, timedelta
from typing import Generator, Optional
from faker import Faker

from src.models. network import (
    Node,
    LogLevel,
    LogEntry,
    NodeType,
)
from src.simulator.network_sim import NetworkSimulator


fake = Faker()


# Log message templates by source type
LOG_TEMPLATES = {
    "system": {
        LogLevel.INFO: [
            "System startup completed successfully",
            "Configuration saved to startup-config",
            "NTP synchronized with {server}",
            "User '{user}' logged in from {ip}",
            "Scheduled backup completed successfully",
            "Memory utilization at {percent}%",
            "CPU utilization normalized",
        ],
        LogLevel.WARNING: [
            "High memory utilization detected: {percent}%",
            "Configuration change detected by user '{user}'",
            "NTP server {server} unreachable, switching to backup",
            "License expiring in {days} days",
            "Disk usage above threshold: {percent}%",
        ],
        LogLevel.ERROR: [
            "Failed to save configuration: {reason}",
            "NTP synchronization failed",
            "Authentication failure for user '{user}' from {ip}",
            "Process '{process}' crashed, restarting",
        ],
        LogLevel.CRITICAL: [
            "System memory critically low: {percent}%",
            "Kernel panic detected",
            "Hardware failure detected on module {module}",
            "System shutting down unexpectedly",
        ],
    },
    "interface": {
        LogLevel. INFO: [
            "Interface {interface} is up",
            "Interface {interface} speed negotiated to {speed}",
            "Link detected on {interface}",
            "Interface {interface} transitioned to forwarding state",
        ],
        LogLevel.WARNING: [
            "Interface {interface} flapping detected",
            "CRC errors detected on {interface}: {count} errors",
            "Interface {interface} experiencing packet drops",
            "Duplex mismatch detected on {interface}",
        ],
        LogLevel.ERROR: [
            "Interface {interface} is down",
            "Interface {interface} error rate exceeded threshold",
            "No link detected on {interface}",
            "Interface {interface} administratively disabled",
        ],
        LogLevel. CRITICAL: [
            "Multiple interfaces down on linecard {slot}",
            "Interface {interface} hardware failure",
        ],
    },
    "security": {
        LogLevel.INFO: [
            "SSH session established from {ip}",
            "Access list {acl} applied to interface {interface}",
            "User '{user}' privilege level changed to {level}",
            "Security audit completed successfully",
        ],
        LogLevel.WARNING: [
            "Multiple failed login attempts from {ip}",
            "SSH brute force attempt detected from {ip}",
            "Unusual traffic pattern detected from {ip}",
            "Access denied for user '{user}' on {resource}",
        ],
        LogLevel. ERROR: [
            "Authentication failure for user '{user}' from {ip}",
            "TACACS+ server {server} unreachable",
            "Certificate validation failed for {host}",
            "Unauthorized access attempt blocked from {ip}",
        ],
        LogLevel.CRITICAL: [
            "Security breach detected: unauthorized access from {ip}",
            "Root access attempted from unauthorized source {ip}",
            "Firewall rule bypass detected",
        ],
    },
    "protocol": {
        LogLevel.INFO: [
            "BGP neighbor {neighbor} established",
            "OSPF adjacency formed with {neighbor}",
            "BGP received {count} prefixes from {neighbor}",
            "SNMP trap sent to {server}",
            "LLDP neighbor discovered: {neighbor} on {interface}",
        ],
        LogLevel. WARNING: [
            "BGP neighbor {neighbor} state changed to Idle",
            "OSPF hello packet timeout from {neighbor}",
            "BGP max-prefix threshold reached for {neighbor}",
            "Spanning-tree topology change detected",
        ],
        LogLevel.ERROR: [
            "BGP neighbor {neighbor} down: {reason}",
            "OSPF adjacency lost with {neighbor}",
            "BGP update error from {neighbor}",
            "SNMP authentication failure from {ip}",
        ],
        LogLevel. CRITICAL: [
            "All BGP sessions down",
            "OSPF routing loop detected",
            "Core routing protocol failure",
        ],
    },
}


class LogGenerator:
    """
    Generates realistic network device logs.
    
    Example:
        >>> sim = NetworkSimulator()
        >>> sim. create_default_topology()
        >>> log_gen = LogGenerator(sim)
        >>> logs = log_gen. generate_batch(count=100)
    """
    
    def __init__(self, network_sim: NetworkSimulator):
        self.network_sim = network_sim
        self._log_weights = {
            LogLevel.DEBUG: 5,
            LogLevel.INFO: 60,
            LogLevel.WARNING: 25,
            LogLevel.ERROR: 8,
            LogLevel.CRITICAL: 2,
        }
    
    def _get_random_level(self) -> LogLevel:
        """Get a random log level based on weights."""
        levels = list(self._log_weights.keys())
        weights = list(self._log_weights.values())
        return random.choices(levels, weights=weights, k=1)[0]
    
    def _get_random_source(self, node: Node) -> str:
        """Get a random log source appropriate for the node type."""
        sources = ["system", "interface", "security"]
        
        # Add protocol logs for routers and switches
        if node.type in [NodeType. ROUTER_CORE, NodeType.ROUTER_EDGE, 
                         NodeType.SWITCH_DISTRIBUTION, NodeType.SWITCH_ACCESS]:
            sources.append("protocol")
        
        return random.choice(sources)
    
    def _fill_template(self, template: str, node: Node) -> str:
        """Fill in template placeholders with realistic values."""
        interface = random.choice(node. interfaces) if node.interfaces else "eth0"
        
        replacements = {
            "{server}": fake.ipv4(),
            "{ip}": fake.ipv4(),
            "{user}": fake.user_name(),
            "{percent}": str(random.randint(75, 99)),
            "{days}": str(random.randint(1, 30)),
            "{reason}": random.choice(["disk full", "permission denied", "timeout", "connection refused"]),
            "{process}": random.choice(["bgpd", "ospfd", "snmpd", "sshd", "ntpd"]),
            "{module}": str(random.randint(1, 8)),
            "{interface}": interface,
            "{speed}": random.choice(["1Gbps", "10Gbps", "25Gbps", "40Gbps", "100Gbps"]),
            "{count}": str(random.randint(1, 1000)),
            "{slot}": str(random.randint(0, 7)),
            "{acl}": f"ACL-{random.randint(100, 199)}",
            "{level}": str(random.randint(1, 15)),
            "{resource}": random.choice(["config", "exec", "interface", "routing"]),
            "{host}": fake.hostname(),
            "{neighbor}": fake.ipv4(),
        }
        
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    def generate_log(
        self,
        node: Node,
        source: Optional[str] = None,
        level: Optional[LogLevel] = None,
        timestamp: Optional[datetime] = None,
    ) -> LogEntry:
        """
        Generate a single log entry for a node.
        
        Args:
            node: The network node generating the log
            source: Log source (system, interface, security, protocol)
            level: Log level (if None, randomly selected)
            timestamp: Log timestamp (if None, current time)
        
        Returns:
            LogEntry object
        """
        if source is None:
            source = self._get_random_source(node)
        
        if level is None:
            level = self._get_random_level()
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Get appropriate templates
        templates = LOG_TEMPLATES.get(source, LOG_TEMPLATES["system"])
        level_templates = templates.get(level, templates. get(LogLevel.INFO, ["Event occurred"]))
        
        template = random.choice(level_templates)
        message = self._fill_template(template, node)
        
        return LogEntry(
            timestamp=timestamp,
            node_id=node.id,
            node_name=node.name,
            level=level,
            source=source,
            message=message,
            metadata={
                "node_type": node. type.value,
                "node_ip": node.ip_address,
                "location": node.location,
            }
        )
    
    def generate_batch(
        self,
        count: int = 100,
        time_range_minutes: int = 60,
        nodes: Optional[list[Node]] = None,
    ) -> list[LogEntry]:
        """
        Generate a batch of log entries. 
        
        Args:
            count: Number of logs to generate
            time_range_minutes: Time range to spread logs across
            nodes: Specific nodes to generate logs for (if None, use all)
        
        Returns:
            List of LogEntry objects sorted by timestamp
        """
        if nodes is None:
            nodes = self.network_sim.get_all_nodes()
        
        if not nodes:
            return []
        
        logs = []
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=time_range_minutes)
        
        for _ in range(count):
            node = random.choice(nodes)
            # Random timestamp within the time range
            random_seconds = random.randint(0, time_range_minutes * 60)
            timestamp = start_time + timedelta(seconds=random_seconds)
            
            log = self.generate_log(node, timestamp=timestamp)
            logs.append(log)
        
        # Sort by timestamp
        logs.sort(key=lambda x: x.timestamp)
        return logs
    
    def generate_continuous(
        self,
        interval_seconds: float = 1.0,
        nodes: Optional[list[Node]] = None,
    ) -> Generator[LogEntry, None, None]:
        """
        Generate logs continuously.
        
        Args:
            interval_seconds: Average time between logs
            nodes: Specific nodes to generate logs for
        
        Yields:
            LogEntry objects
        """
        if nodes is None:
            nodes = self.network_sim.get_all_nodes()
        
        while True:
            node = random.choice(nodes)
            yield self.generate_log(node)
    
    def generate_anomaly_logs(
        self,
        node: Node,
        anomaly_type: str,
        count: int = 5,
    ) -> list[LogEntry]:
        """
        Generate logs related to an anomaly.
        
        Args:
            node: Affected node
            anomaly_type: Type of anomaly
            count: Number of logs to generate
        
        Returns:
            List of LogEntry objects
        """
        logs = []
        now = datetime.utcnow()
        
        anomaly_messages = {
            "HIGH_CPU": [
                (LogLevel.WARNING, "system", "CPU utilization at 92%"),
                (LogLevel.ERROR, "system", "CPU utilization critical: 96%"),
                (LogLevel.CRITICAL, "system", "CPU utilization exceeded threshold: 98%"),
                (LogLevel.ERROR, "system", "Process scheduling delayed due to high CPU"),
                (LogLevel.WARNING, "system", "Background tasks queued due to CPU pressure"),
            ],
            "MEMORY_LEAK": [
                (LogLevel. WARNING, "system", "Memory utilization increasing: 78%"),
                (LogLevel.WARNING, "system", "Memory utilization at 85%"),
                (LogLevel.ERROR, "system", "Memory utilization high: 92%"),
                (LogLevel. CRITICAL, "system", "Memory critically low, OOM killer activated"),
                (LogLevel.ERROR, "system", "Process terminated due to out of memory"),
            ],
            "INTERFACE_DOWN": [
                (LogLevel.WARNING, "interface", f"Interface {node.interfaces[0] if node.interfaces else 'eth0'} link unstable"),
                (LogLevel.ERROR, "interface", f"Interface {node. interfaces[0] if node.interfaces else 'eth0'} is down"),
                (LogLevel.ERROR, "protocol", "BGP neighbor unreachable"),
                (LogLevel.WARNING, "protocol", "OSPF adjacency lost"),
                (LogLevel.ERROR, "interface", "No carrier detected"),
            ],
            "PACKET_LOSS": [
                (LogLevel.WARNING, "interface", "Packet drops detected: 2%"),
                (LogLevel.WARNING, "interface", "Input queue overflow"),
                (LogLevel.ERROR, "interface", "Packet loss exceeded threshold: 5%"),
                (LogLevel. WARNING, "interface", "CRC errors increasing"),
                (LogLevel.ERROR, "interface", "Significant packet loss detected: 8%"),
            ],
            "HIGH_LATENCY": [
                (LogLevel.WARNING, "protocol", "Increased RTT to neighbor: 50ms"),
                (LogLevel.WARNING, "system", "Network latency above baseline"),
                (LogLevel.ERROR, "protocol", "BGP keepalive delayed"),
                (LogLevel.WARNING, "protocol", "OSPF hello timeout approaching"),
                (LogLevel.ERROR, "system", "Service response time degraded"),
            ],
            "AUTH_FAILURE": [
                (LogLevel.WARNING, "security", f"Failed login attempt from {fake.ipv4()}"),
                (LogLevel.ERROR, "security", f"Authentication failure for user 'admin' from {fake.ipv4()}"),
                (LogLevel. WARNING, "security", "Multiple authentication failures detected"),
                (LogLevel. CRITICAL, "security", f"Possible brute force attack from {fake.ipv4()}"),
                (LogLevel.ERROR, "security", "Account locked due to failed attempts"),
            ],
        }
        
        messages = anomaly_messages.get(anomaly_type, [
            (LogLevel. ERROR, "system", f"Anomaly detected: {anomaly_type}"),
        ])
        
        for i in range(min(count, len(messages))):
            level, source, message = messages[i]
            timestamp = now + timedelta(seconds=i * 2)
            
            logs.append(LogEntry(
                timestamp=timestamp,
                node_id=node. id,
                node_name=node. name,
                level=level,
                source=source,
                message=message,
                metadata={
                    "node_type": node. type.value,
                    "anomaly_type": anomaly_type,
                    "anomaly_related": True,
                }
            ))
        
        return logs