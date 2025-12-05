"""Tests for the Discovery Agent."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.agents.discovery.agent import DiscoveryAgent
from src.agents.discovery.models import (
    DiagnosisReport,
    DetectedIssue,
    IssueSeverity,
    IssueType,
)
from src.agents.discovery.analyzers import MetricAnalyzer, LogAnalyzer
from src.agents.config import DiscoveryAgentConfig, AgentConfig


class TestDetectedIssue:
    """Test cases for DetectedIssue model."""

    def test_create_issue(self):
        """Test creating a detected issue."""
        issue = DetectedIssue(
            issue_type=IssueType.HIGH_CPU,
            severity=IssueSeverity.CRITICAL,
            node_id="router_core_01",
            node_name="core-rtr-01",
            description="High CPU detected",
        )

        assert issue.issue_type == IssueType.HIGH_CPU
        assert issue.severity == IssueSeverity.CRITICAL
        assert issue.node_id == "router_core_01"
        assert issue.id.startswith("issue_")

    def test_issue_to_dict(self):
        """Test converting issue to dictionary."""
        issue = DetectedIssue(
            issue_type=IssueType.HIGH_CPU,
            severity=IssueSeverity.CRITICAL,
            node_id="router_core_01",
            current_value=95.5,
        threshold_value = 90.0,
        unit = "%",
        )

        data = issue.to_dict()

        assert data["issue_type"] == "HIGH_CPU"
        assert data["severity"] == "critical"
        assert data["current_value"] == 95.5


class TestDiagnosisReport:
    """Test cases for DiagnosisReport model."""

    def test_create_report(self):
        """Test creating a diagnosis report."""
        report = DiagnosisReport(
            scope="network-wide",
            nodes_analyzed=10,
        )

        assert report.scope == "network-wide"
        assert report.nodes_analyzed == 10
        assert report.id.startswith("diag_")
        assert report.overall_status == IssueSeverity.INFO

    def test_add_issue_updates_counts(self):
        """Test that adding issues updates counts correctly."""
        report = DiagnosisReport()

        report.add_issue(DetectedIssue(severity=IssueSeverity.CRITICAL))
        report.add_issue(DetectedIssue(severity=IssueSeverity.HIGH))
        report.add_issue(DetectedIssue(severity=IssueSeverity.MEDIUM))

        assert report.critical_count == 1
        assert report.high_count == 1
        assert report.medium_count == 1
        assert report.overall_status == IssueSeverity.CRITICAL

    def test_overall_status_updates(self):
        """Test that overall status reflects highest severity."""
        report = DiagnosisReport()

        # Start with medium
        report.add_issue(DetectedIssue(severity=IssueSeverity.MEDIUM))
        assert report.overall_status == IssueSeverity.MEDIUM

        # Add high
        report.add_issue(DetectedIssue(severity=IssueSeverity.HIGH))
        assert report.overall_status == IssueSeverity.HIGH

        # Add critical
        report.add_issue(DetectedIssue(severity=IssueSeverity.CRITICAL))
        assert report.overall_status == IssueSeverity.CRITICAL

    def test_get_summary(self):
        """Test getting report summary."""
        report = DiagnosisReport(scope="router_core_01", nodes_analyzed=1)
        report.add_issue(DetectedIssue(severity=IssueSeverity.HIGH))

        summary = report.get_summary()

        assert "router_core_01" in summary
        assert "HIGH" in summary
        assert "Issues Found: 1" in summary


class TestMetricAnalyzer:
    """Test cases for MetricAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with default config."""
        config = DiscoveryAgentConfig()
        return MetricAnalyzer(config)

    def test_high_cpu_critical(self, analyzer):
        """Test detection of critical CPU."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={"cpu_utilization": {"value": 95, "unit": "%"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.HIGH_CPU
        assert issues[0].severity == IssueSeverity.CRITICAL
        assert issues[0].current_value == 95

    def test_high_cpu_warning(self, analyzer):
        """Test detection of warning-level CPU."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={"cpu_utilization": {"value": 85, "unit": "%"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.HIGH_CPU
        assert issues[0].severity == IssueSeverity.MEDIUM

    def test_normal_cpu_no_issues(self, analyzer):
        """Test that normal CPU doesn't create issues."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={"cpu_utilization": {"value": 50, "unit": "%"}}
        )

        assert len(issues) == 0

    def test_high_memory_critical(self, analyzer):
        """Test detection of critical memory."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="server",
            metrics={"memory_utilization": {"value": 95, "unit": "%"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.MEMORY_LEAK
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_packet_loss_critical(self, analyzer):
        """Test detection of critical packet loss."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={"packet_loss": {"value": 8, "unit": "%"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.PACKET_LOSS
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_high_latency(self, analyzer):
        """Test detection of high latency."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={"latency": {"value": 75, "unit": "ms"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.HIGH_LATENCY
        assert issues[0].severity == IssueSeverity.HIGH

    def test_interface_down(self, analyzer):
        """Test detection of interface down (zero bandwidth)."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={
                "bandwidth_in": {"value": 0, "unit": "Mbps"},
                "bandwidth_out": {"value": 0, "unit": "Mbps"},
            }
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.INTERFACE_DOWN
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_high_temperature(self, analyzer):
        """Test detection of high temperature."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="server",
            metrics={"temperature": {"value": 88, "unit": "°C"}}
        )

        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.TEMPERATURE_HIGH
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_multiple_issues(self, analyzer):
        """Test detection of multiple issues."""
        issues = analyzer.analyze_node_metrics(
            node_id="test_node",
            node_name="Test Node",
            node_type="router_core",
            metrics={
                "cpu_utilization": {"value": 95, "unit": "%"},
                "memory_utilization": {"value": 92, "unit": "%"},
                "packet_loss": {"value": 10, "unit": "%"},
            }
        )

        assert len(issues) == 3
        issue_types = {i.issue_type for i in issues}
        assert IssueType.HIGH_CPU in issue_types
        assert IssueType.MEMORY_LEAK in issue_types
        assert IssueType.PACKET_LOSS in issue_types


class TestLogAnalyzer:
    """Test cases for LogAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with default config."""
        config = DiscoveryAgentConfig()
        return LogAnalyzer(config)

    def test_detect_cpu_issue_from_logs(self, analyzer):
        """Test detecting CPU issues from logs."""
        logs = [
            {"node_id": "router_01", "node_name": "Router 1", "level": "ERROR",
             "message": "CPU high utilization detected on system"},
            {"node_id": "router_01", "node_name": "Router 1", "level": "WARNING",
             "message": "CPU spike detected on interface processor"},
        ]

        issues = analyzer.analyze_logs(logs)

        assert len(issues) >= 1
        cpu_issues = [i for i in issues if i.issue_type == IssueType.HIGH_CPU]
        assert len(cpu_issues) >= 1

    def test_detect_auth_failure(self, analyzer):
        """Test detecting authentication failures from logs."""
        logs = [
            {"node_id": "firewall_01", "node_name": "Firewall 1", "level": "ERROR",
             "message": "Authentication failed for user admin from 192.168.1.100"},
            {"node_id": "firewall_01", "node_name": "Firewall 1", "level": "ERROR",
             "message": "Login denied: invalid credentials"},
        ]

        issues = analyzer.analyze_logs(logs)

        auth_issues = [i for i in issues if i.issue_type == IssueType.AUTH_FAILURE]
        assert len(auth_issues) >= 1

    def test_detect_interface_down_from_logs(self, analyzer):
        """Test detecting interface down from logs."""
        logs = [
            {"node_id": "switch_01", "node_name": "Switch 1", "level": "CRITICAL",
             "message": "Interface GigabitEthernet0/1 is down"},
        ]

        issues = analyzer.analyze_logs(logs)

        interface_issues = [i for i in issues if i.issue_type == IssueType.INTERFACE_DOWN]
        assert len(interface_issues) >= 1

    def test_skip_info_logs(self, analyzer):
        """Test that INFO logs are skipped."""
        logs = [
            {"node_id": "router_01", "node_name": "Router 1", "level": "INFO",
             "message": "Interface GigabitEthernet0/1 is up"},
            {"node_id": "router_01", "node_name": "Router 1", "level": "DEBUG",
             "message": "Received packet on interface"},
        ]

        issues = analyzer.analyze_logs(logs)

        assert len(issues) == 0

    def test_aggregate_multiple_occurrences(self, analyzer):
        """Test that multiple log entries are aggregated."""
        logs = [
            {"node_id": "router_01", "node_name": "Router 1", "level": "ERROR", "message": "CPU spike detected"},
            {"node_id": "router_01", "node_name": "Router 1", "level": "ERROR", "message": "CPU utilization high"},
            {"node_id": "router_01", "node_name": "Router 1", "level": "ERROR", "message": "CPU threshold exceeded"},
        ]

        issues = analyzer.analyze_logs(logs)

        # Should be aggregated into one issue
        cpu_issues = [i for i in issues if i.issue_type == IssueType.HIGH_CPU]
        assert len(cpu_issues) == 1
        # Should have multiple related logs
        assert len(cpu_issues[0].related_logs) >= 1


class TestDiscoveryAgent:
    """Test cases for DiscoveryAgent."""

    @pytest.fixture
    def agent(self):
        """Create discovery agent."""
        return DiscoveryAgent()

    @pytest.mark.asyncio
    async def test_run_returns_result(self, agent):
        """Test that run returns an AgentResult."""
        result = await agent.run(use_llm=False)

        assert result is not None
        assert result.agent_name == "discovery"
        assert result.success is True
        assert result.result is not None

    @pytest.mark.asyncio
    async def test_run_creates_report(self, agent):
        """Test that run creates a DiagnosisReport."""
        result = await agent.run(use_llm=False)

        report = result.result
        assert isinstance(report, DiagnosisReport)
        assert report.nodes_analyzed > 0
        assert report.analysis_method == "rule-based"

    @pytest.mark.asyncio
    async def test_run_single_node(self, agent):
        """Test running diagnosis on a single node."""
        result = await agent.run_single_node("router_core_01")

        assert result.success is True
        report = result.result
        assert report.scope == "router_core_01"
        assert report.nodes_analyzed == 1

    @pytest.mark.asyncio
    async def test_run_quick(self, agent):
        """Test quick run without logs or LLM."""
        result = await agent.run_quick()

        assert result.success is True
        report = result.result
        assert report.analysis_method == "rule-based"

    def test_get_active_anomalies(self, agent):
        """Test getting active anomalies."""
        anomalies = agent.get_active_anomalies()

        # Should return a list (might be empty)
        assert isinstance(anomalies, list)

    def test_execution_history(self, agent):
        """Test execution history tracking."""
        import asyncio

        # Run once
        asyncio.run(agent.run(use_llm=False))

        history = agent.get_execution_history()
        assert len(history) >= 1

        last = agent.get_last_execution()
        assert last is not None
        assert last.success is True


class TestLLMIntegration:
    """Test cases for LLM integration (mocked)."""

    @pytest.mark.asyncio
    async def test_llm_not_available_uses_rule_based(self):
        """Test that rule-based is used when LLM is not available."""
        agent = DiscoveryAgent()

        # Force LLM unavailable
        agent.llm_available = False

        result = await agent.run()

        assert result.success is True
        assert result.result.analysis_method == "rule-based"

    @pytest.mark.asyncio
    async def test_use_llm_false_skips_llm(self):
        """Test that use_llm=False skips LLM analysis."""
        agent = DiscoveryAgent()

        result = await agent.run(use_llm=False)

        assert result.success is True
        assert result.result.analysis_method == "rule-based"
        assert result.result.llm_provider is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_nonexistent_node(self):
        """Test handling of non-existent node."""
        agent = DiscoveryAgent()

        result = await agent.run(node_id="nonexistent_node_xyz")

        # Should still succeed but with 0 nodes analyzed
        assert result.success is True
        assert result.result.nodes_analyzed == 0

    def test_empty_metrics(self):
        """Test handling of empty metrics."""
        config = DiscoveryAgentConfig()
        analyzer = MetricAnalyzer(config)

        issues = analyzer.analyze_node_metrics(
            node_id="test",
            node_name="Test",
            node_type="server",
            metrics={}
        )

        assert issues == []

    def test_empty_logs(self):
        """Test handling of empty logs."""
        config = DiscoveryAgentConfig()
        analyzer = LogAnalyzer(config)

        issues = analyzer.analyze_logs([])

        assert issues == []