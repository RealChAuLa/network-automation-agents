"""
Discovery Agent Analyzers

Rule-based analyzers for network metrics and logs.
"""

import re
import logging
from typing import Optional
from datetime import datetime

from src.agents.config import DiscoveryAgentConfig
from src.agents.discovery.models import (
    DetectedIssue,
    IssueSeverity,
    IssueType,
)

logger = logging.getLogger(__name__)


class MetricAnalyzer:
    """
    Analyzes network metrics against thresholds.

    This is the rule-based analyzer that works without an LLM.
    """

    def __init__(self, config: DiscoveryAgentConfig):
        """Initialize with configuration."""
        self.config = config

    def analyze_node_metrics(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            metrics: dict,
    ) -> list[DetectedIssue]:
        """
        Analyze metrics for a single node.

        Args:
            node_id: Node identifier
            node_name: Human-readable node name
            node_type: Type of node (router_core, switch, etc.)
            metrics: Dictionary of metric name -> {value, unit}

        Returns:
            List of detected issues
        """
        issues = []

        # Check CPU
        cpu = metrics.get("cpu_utilization", {})
        if cpu:
            cpu_value = cpu.get("value", 0)
            issue = self._check_cpu(node_id, node_name, node_type, cpu_value)
            if issue:
                issues.append(issue)

        # Check Memory
        memory = metrics.get("memory_utilization", {})
        if memory:
            mem_value = memory.get("value", 0)
            issue = self._check_memory(node_id, node_name, node_type, mem_value)
            if issue:
                issues.append(issue)

        # Check Packet Loss
        packet_loss = metrics.get("packet_loss", {})
        if packet_loss:
            loss_value = packet_loss.get("value", 0)
            issue = self._check_packet_loss(node_id, node_name, node_type, loss_value)
            if issue:
                issues.append(issue)

        # Check Latency
        latency = metrics.get("latency", {})
        if latency:
            lat_value = latency.get("value", 0)
            issue = self._check_latency(node_id, node_name, node_type, lat_value)
            if issue:
                issues.append(issue)

        # Check Error Count
        error_count = metrics.get("error_count", {})
        if error_count:
            err_value = error_count.get("value", 0)
            issue = self._check_error_count(node_id, node_name, node_type, err_value)
            if issue:
                issues.append(issue)

        # Check Temperature
        temperature = metrics.get("temperature", {})
        if temperature:
            temp_value = temperature.get("value", 0)
            issue = self._check_temperature(node_id, node_name, node_type, temp_value)
            if issue:
                issues.append(issue)

        # Check Bandwidth (for interface down)
        bandwidth_in = metrics.get("bandwidth_in", {})
        bandwidth_out = metrics.get("bandwidth_out", {})
        if bandwidth_in and bandwidth_out:
            bw_in = bandwidth_in.get("value", 0)
            bw_out = bandwidth_out.get("value", 0)
            issue = self._check_bandwidth(node_id, node_name, node_type, bw_in, bw_out)
            if issue:
                issues.append(issue)

        return issues

    def _check_cpu(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check CPU utilization."""
        if value >= self.config.cpu_critical_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_CPU,
                severity=IssueSeverity.CRITICAL,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="cpu_utilization",
                current_value=value,
                threshold_value=self.config.cpu_critical_threshold,
                unit="%",
                description=f"CPU utilization is critically high at {value}%",
                potential_causes=[
                    "Traffic spike or DDoS attack",
                    "Runaway process",
                    "Insufficient hardware capacity",
                    "Software bug causing high CPU",
                ],
                recommended_actions=[
                    "Identify top processes consuming CPU",
                    "Check for traffic anomalies",
                    "Consider restarting affected services",
                    "Evaluate need for hardware upgrade",
                ],
            )
        elif value >= self.config.cpu_warning_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_CPU,
                severity=IssueSeverity.MEDIUM,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="cpu_utilization",
                current_value=value,
                threshold_value=self.config.cpu_warning_threshold,
                unit="%",
                description=f"CPU utilization is elevated at {value}%",
                potential_causes=[
                    "Increased traffic load",
                    "Background processes",
                ],
                recommended_actions=[
                    "Monitor for further increase",
                    "Review recent changes",
                ],
            )
        return None

    def _check_memory(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check memory utilization."""
        if value >= self.config.memory_critical_threshold:
            return DetectedIssue(
                issue_type=IssueType.MEMORY_LEAK,
                severity=IssueSeverity.CRITICAL,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="memory_utilization",
                current_value=value,
                threshold_value=self.config.memory_critical_threshold,
                unit="%",
                description=f"Memory utilization is critically high at {value}%",
                potential_causes=[
                    "Memory leak in application",
                    "Insufficient memory allocation",
                    "Too many concurrent connections",
                ],
                recommended_actions=[
                    "Clear caches if possible",
                    "Restart affected services",
                    "Analyze memory usage patterns",
                    "Consider memory upgrade",
                ],
            )
        elif value >= self.config.memory_warning_threshold:
            return DetectedIssue(
                issue_type=IssueType.MEMORY_LEAK,
                severity=IssueSeverity.MEDIUM,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="memory_utilization",
                current_value=value,
                threshold_value=self.config.memory_warning_threshold,
                unit="%",
                description=f"Memory utilization is elevated at {value}%",
                potential_causes=[
                    "Growing cache usage",
                    "Increased workload",
                ],
                recommended_actions=[
                    "Monitor memory trend",
                    "Review memory allocation",
                ],
            )
        return None

    def _check_packet_loss(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check packet loss."""
        if value >= self.config.packet_loss_critical_threshold:
            return DetectedIssue(
                issue_type=IssueType.PACKET_LOSS,
                severity=IssueSeverity.CRITICAL,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="packet_loss",
                current_value=value,
                threshold_value=self.config.packet_loss_critical_threshold,
                unit="%",
                description=f"Packet loss is critically high at {value}%",
                potential_causes=[
                    "Network congestion",
                    "Faulty hardware (NIC, cable, port)",
                    "Buffer overflow",
                    "QoS misconfiguration",
                ],
                recommended_actions=[
                    "Check interface errors and drops",
                    "Verify physical connectivity",
                    "Review QoS policies",
                    "Consider traffic engineering",
                ],
            )
        elif value >= self.config.packet_loss_warning_threshold:
            return DetectedIssue(
                issue_type=IssueType.PACKET_LOSS,
                severity=IssueSeverity.MEDIUM,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="packet_loss",
                current_value=value,
                threshold_value=self.config.packet_loss_warning_threshold,
                unit="%",
                description=f"Packet loss detected at {value}%",
                potential_causes=[
                    "Light network congestion",
                    "Intermittent connectivity issues",
                ],
                recommended_actions=[
                    "Monitor for increase",
                    "Check interface statistics",
                ],
            )
        return None

    def _check_latency(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check latency."""
        if value >= self.config.latency_critical_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_LATENCY,
                severity=IssueSeverity.HIGH,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="latency",
                current_value=value,
                threshold_value=self.config.latency_critical_threshold,
                unit="ms",
                description=f"Latency is high at {value}ms",
                potential_causes=[
                    "Network congestion",
                    "Routing issues",
                    "Overloaded device",
                    "Geographic distance",
                ],
                recommended_actions=[
                    "Check routing paths",
                    "Review traffic patterns",
                    "Consider traffic optimization",
                ],
            )
        elif value >= self.config.latency_warning_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_LATENCY,
                severity=IssueSeverity.MEDIUM,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="latency",
                current_value=value,
                threshold_value=self.config.latency_warning_threshold,
                unit="ms",
                description=f"Latency is elevated at {value}ms",
                potential_causes=[
                    "Increased traffic",
                    "Suboptimal routing",
                ],
                recommended_actions=[
                    "Monitor latency trend",
                    "Review routing configuration",
                ],
            )
        return None

    def _check_error_count(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check error count."""
        if value >= self.config.error_count_critical_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_ERROR_RATE,
                severity=IssueSeverity.HIGH,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="error_count",
                current_value=value,
                threshold_value=self.config.error_count_critical_threshold,
                unit="errors",
                description=f"High error count: {int(value)} errors",
                potential_causes=[
                    "Hardware issues",
                    "Protocol errors",
                    "Configuration problems",
                ],
                recommended_actions=[
                    "Review error logs",
                    "Check hardware status",
                    "Verify configuration",
                ],
            )
        elif value >= self.config.error_count_warning_threshold:
            return DetectedIssue(
                issue_type=IssueType.HIGH_ERROR_RATE,
                severity=IssueSeverity.LOW,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="error_count",
                current_value=value,
                threshold_value=self.config.error_count_warning_threshold,
                unit="errors",
                description=f"Elevated error count: {int(value)} errors",
                potential_causes=[
                    "Intermittent issues",
                    "Minor configuration issues",
                ],
                recommended_actions=[
                    "Monitor error trend",
                    "Review recent changes",
                ],
            )
        return None

    def _check_temperature(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            value: float,
    ) -> Optional[DetectedIssue]:
        """Check temperature."""
        if value >= 85:
            return DetectedIssue(
                issue_type=IssueType.TEMPERATURE_HIGH,
                severity=IssueSeverity.CRITICAL,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="temperature",
                current_value=value,
                threshold_value=85,
                unit="°C",
                description=f"Temperature is critically high at {value}°C",
                potential_causes=[
                    "Cooling system failure",
                    "Blocked airflow",
                    "High ambient temperature",
                    "Overloaded device",
                ],
                recommended_actions=[
                    "Check cooling systems immediately",
                    "Reduce workload if possible",
                    "Verify airflow paths",
                    "Consider emergency shutdown if continues",
                ],
            )
        elif value >= 70:
            return DetectedIssue(
                issue_type=IssueType.TEMPERATURE_HIGH,
                severity=IssueSeverity.MEDIUM,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="temperature",
                current_value=value,
                threshold_value=70,
                unit="°C",
                description=f"Temperature is elevated at {value}°C",
                potential_causes=[
                    "Increased workload",
                    "Reduced cooling efficiency",
                ],
                recommended_actions=[
                    "Monitor temperature trend",
                    "Check cooling system status",
                ],
            )
        return None

    def _check_bandwidth(
            self,
            node_id: str,
            node_name: str,
            node_type: str,
            bw_in: float,
            bw_out: float,
    ) -> Optional[DetectedIssue]:
        """Check for interface down (zero bandwidth)."""
        if bw_in == 0 and bw_out == 0:
            return DetectedIssue(
                issue_type=IssueType.INTERFACE_DOWN,
                severity=IssueSeverity.CRITICAL,
                node_id=node_id,
                node_name=node_name,
                node_type=node_type,
                metric_name="bandwidth",
                current_value=0,
                threshold_value=0,
                unit="Mbps",
                description="Interface appears to be down (zero bandwidth)",
                potential_causes=[
                    "Physical link failure",
                    "Interface administratively down",
                    "Cable disconnection",
                    "Remote end failure",
                ],
                recommended_actions=[
                    "Check physical connectivity",
                    "Verify interface status",
                    "Check remote end",
                    "Initiate failover if available",
                ],
            )
        return None


class LogAnalyzer:
    """
    Analyzes network logs for issues.

    This is the rule-based log analyzer that works without an LLM.
    """

    # Patterns to detect in logs
    ERROR_PATTERNS = [
        (r"(critical|fatal|emergency)", IssueSeverity.CRITICAL),
        (r"(error|failed|failure|down)", IssueSeverity.HIGH),
        (r"(warning|warn|degraded)", IssueSeverity.MEDIUM),
        (r"(notice|info)", IssueSeverity.LOW),
    ]

    ISSUE_PATTERNS = [
        (r"cpu. *(high|spike|critical|exceed)", IssueType.HIGH_CPU),
        (r"memory.*(high|leak|critical|exceed)", IssueType.MEMORY_LEAK),
        (r"interface.*(down|failed|error)", IssueType.INTERFACE_DOWN),
        (r"(packet. ? loss|dropped|discarded)", IssueType.PACKET_LOSS),
        (r"(latency|delay|timeout|slow)", IssueType.HIGH_LATENCY),
        (r"(auth|login|password|credential). *(fail|denied|invalid)", IssueType.AUTH_FAILURE),
        (r"(config|configuration). *(change|drift|mismatch)", IssueType.CONFIG_DRIFT),
        (r"(temperature|thermal|overheat)", IssueType.TEMPERATURE_HIGH),
    ]

    def __init__(self, config: DiscoveryAgentConfig):
        """Initialize with configuration."""
        self.config = config

    def analyze_logs(self, logs: list[dict]) -> list[DetectedIssue]:
        """
        Analyze a list of logs for issues.

        Args:
            logs: List of log entries (dict with timestamp, node_id, level, message, etc.)

        Returns:
            List of detected issues
        """
        issues = []
        issue_counts = {}  # Track issues by node to avoid duplicates

        for log in logs:
            message = log.get("message", "").lower()
            node_id = log.get("node_id", "unknown")
            node_name = log.get("node_name", "unknown")
            level = log.get("level", "INFO")

            # Skip low-level logs
            if level in ["DEBUG", "INFO"]:
                continue

            # Try to match issue patterns
            for pattern, issue_type in self.ISSUE_PATTERNS:
                if re.search(pattern, message, re.IGNORECASE):
                    # Determine severity from log level and content
                    severity = self._determine_severity(level, message)

                    # Create a key to avoid duplicate issues
                    key = f"{node_id}:{issue_type.value}"

                    if key not in issue_counts:
                        issue_counts[key] = {
                            "count": 0,
                            "messages": [],
                            "severity": severity,
                            "node_id": node_id,
                            "node_name": node_name,
                            "issue_type": issue_type,
                        }

                    issue_counts[key]["count"] += 1
                    if len(issue_counts[key]["messages"]) < 5:  # Keep max 5 sample messages
                        issue_counts[key]["messages"].append(message[:100])

                    # Upgrade severity if this log is more severe
                    if self._severity_rank(severity) > self._severity_rank(issue_counts[key]["severity"]):
                        issue_counts[key]["severity"] = severity

                    break  # Only match first pattern per log

        # Convert aggregated counts to issues
        for key, data in issue_counts.items():
            if data["count"] >= 1:  # At least 1 occurrence
                issue = DetectedIssue(
                    issue_type=data["issue_type"],
                    severity=data["severity"],
                    node_id=data["node_id"],
                    node_name=data["node_name"],
                    description=f"Detected {data['count']} log entries indicating {data['issue_type'].value}",
                    related_logs=data["messages"],
                    potential_causes=self._get_causes_for_type(data["issue_type"]),
                    recommended_actions=self._get_actions_for_type(data["issue_type"]),
                )
                issues.append(issue)

        return issues

    def _determine_severity(self, level: str, message: str) -> IssueSeverity:
        """Determine severity from log level and content."""
        level_upper = level.upper()

        if level_upper == "CRITICAL":
            return IssueSeverity.CRITICAL
        elif level_upper == "ERROR":
            # Check message for additional severity hints
            if any(word in message.lower() for word in ["critical", "fatal", "emergency", "down"]):
                return IssueSeverity.CRITICAL
            return IssueSeverity.HIGH
        elif level_upper == "WARNING":
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW

    def _severity_rank(self, severity: IssueSeverity) -> int:
        """Get numeric rank for severity comparison."""
        ranks = {
            IssueSeverity.CRITICAL: 4,
            IssueSeverity.HIGH: 3,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 1,
            IssueSeverity.INFO: 0,
        }
        return ranks.get(severity, 0)

    def _get_causes_for_type(self, issue_type: IssueType) -> list[str]:
        """Get potential causes for an issue type."""
        causes = {
            IssueType.HIGH_CPU: ["Traffic spike", "Runaway process", "DDoS attack"],
            IssueType.MEMORY_LEAK: ["Memory leak", "Cache overflow", "Resource exhaustion"],
            IssueType.INTERFACE_DOWN: ["Physical failure", "Cable issue", "Remote end down"],
            IssueType.PACKET_LOSS: ["Congestion", "Hardware issue", "QoS problem"],
            IssueType.HIGH_LATENCY: ["Congestion", "Routing issue", "Overload"],
            IssueType.AUTH_FAILURE: ["Brute force attack", "Credential issue", "Config error"],
            IssueType.CONFIG_DRIFT: ["Unauthorized change", "Sync failure", "Human error"],
            IssueType.TEMPERATURE_HIGH: ["Cooling failure", "Overload", "Environment issue"],
        }
        return causes.get(issue_type, ["Unknown cause"])

    def _get_actions_for_type(self, issue_type: IssueType) -> list[str]:
        """Get recommended actions for an issue type."""
        actions = {
            IssueType.HIGH_CPU: ["Check processes", "Review traffic", "Consider restart"],
            IssueType.MEMORY_LEAK: ["Clear cache", "Restart service", "Analyze memory"],
            IssueType.INTERFACE_DOWN: ["Check physical", "Verify config", "Failover"],
            IssueType.PACKET_LOSS: ["Check interface", "Review QoS", "Check hardware"],
            IssueType.HIGH_LATENCY: ["Check routing", "Review traffic", "Optimize paths"],
            IssueType.AUTH_FAILURE: ["Check source IPs", "Review credentials", "Block attackers"],
            IssueType.CONFIG_DRIFT: ["Review changes", "Restore config", "Audit access"],
            IssueType.TEMPERATURE_HIGH: ["Check cooling", "Reduce load", "Check environment"],
        }
        return actions.get(issue_type, ["Investigate further"])