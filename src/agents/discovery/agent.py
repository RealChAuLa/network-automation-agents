"""
Discovery Agent (Refactored)

The Discovery Agent that uses MCP tools via LLM to monitor the network.
"""

import json
import logging
import time
import re
from typing import Any, Optional
from datetime import datetime

from src.agents.base import BaseAgent, AgentResult
from src.agents.config import AgentConfig, config as default_config
from src.agents.llm import create_llm, BaseLLM
from src.agents.mcp_client import MCPClient
from src.agents.discovery. models import (
    DiagnosisReport,
    DetectedIssue,
    IssueSeverity,
    IssueType,
)
from src.agents.discovery.prompts import (
    DISCOVERY_AGENT_SYSTEM_PROMPT,
    DISCOVERY_TASK_PROMPT,
    ANALYSIS_PROMPT,
)

logger = logging.getLogger(__name__)


class DiscoveryAgent(BaseAgent):
    """
    Discovery Agent that monitors the network using MCP tools.

    This agent:
    1. Uses an LLM (Gemini) as its "brain"
    2.  Calls MCP tools to gather network data
    3.  Analyzes the data to detect anomalies
    4. Produces a structured diagnosis report

    Example:
        agent = DiscoveryAgent()
        result = await agent.run()
        print(result.result. get_summary())
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseLLM] = None,
    ):
        """
        Initialize the Discovery Agent.

        Args:
            config: Agent configuration
            llm: LLM instance (creates one based on config if not provided)
        """
        super().__init__(name="discovery", config=config)

        # Initialize LLM
        self.llm = llm or create_llm(self.config. llm)
        self.llm_available = self.llm. is_available()

        # Initialize MCP Client
        self.mcp_client = MCPClient()

        if self.llm_available:
            logger.info(f"Discovery Agent initialized with LLM: {self.llm.provider_name}")
        else:
            logger. warning("Discovery Agent: No LLM available, will use simplified analysis")

        logger.info(f"Discovery Agent has access to {len(self.mcp_client.get_available_tools())} MCP tools")

    async def run(
        self,
        node_id: Optional[str] = None,
        use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Run the Discovery Agent.

        Args:
            node_id: Optional specific node to analyze (None = all nodes)
            use_llm: Override LLM usage (None = use if available)

        Returns:
            AgentResult containing the DiagnosisReport
        """
        result = self._create_result()
        start_time = time. time()
        tool_calls = 0

        try:
            scope = node_id or "network-wide"
            self.logger.info(f"Starting discovery.  Scope: {scope}")

            # Determine if we should use LLM
            should_use_llm = use_llm if use_llm is not None else self.llm_available

            if should_use_llm and self.llm_available:
                # LLM-based analysis
                report, tool_calls = await self._run_with_llm(node_id)
            else:
                # Simplified analysis without LLM
                report, tool_calls = await self._run_without_llm(node_id)

            report.analysis_duration_ms = int((time.time() - start_time) * 1000)
            report.tool_calls_made = tool_calls

            self.logger.info(f"Discovery complete. Status: {report.overall_status.value}")
            self.logger.info(report.get_summary())

            result.complete(result=report)

        except Exception as e:
            self. logger.error(f"Discovery agent error: {e}")
            result. complete(error=str(e))

        self._record_execution(result)
        return result

    async def _run_with_llm(self, node_id: Optional[str] = None) -> tuple[DiagnosisReport, int]:
        """Run discovery using LLM for analysis."""
        tool_calls = 0
        scope = node_id or "network-wide"

        # Step 1: Gather data using MCP tools
        self.logger.info("Step 1: Gathering data via MCP tools...")

        # Get metrics
        if node_id:
            metrics_result = await self.mcp_client.get_node_metrics(node_id)
        else:
            metrics_result = await self.mcp_client.get_node_metrics()
        tool_calls += 1

        # Get logs
        logs_result = await self.mcp_client.get_network_logs(
            node_id=node_id,
            count=50,
        )
        tool_calls += 1

        # Get alerts
        alerts_result = await self.mcp_client.get_alerts(node_id=node_id)
        tool_calls += 1

        # Get topology
        topology_result = await self.mcp_client.get_network_topology(include_links=False)
        tool_calls += 1

        # Step 2: Prepare data for LLM
        self.logger.info("Step 2: Preparing data for LLM analysis...")

        metrics_data = json.dumps(metrics_result.data, indent=2) if metrics_result. success else "No metrics available"
        log_data = self._summarize_logs(logs_result.data) if logs_result. success else "No logs available"
        alerts_data = json. dumps(alerts_result.data, indent=2) if alerts_result.success else "No alerts"
        topology_data = self._summarize_topology(topology_result. data) if topology_result.success else "No topology data"

        nodes_analyzed = 0
        if metrics_result.success and isinstance(metrics_result. data, dict):
            nodes_analyzed = metrics_result.data. get("node_count", 0)

        # Step 3: Ask LLM to analyze
        self.logger.info("Step 3: Running LLM analysis...")

        analysis_prompt = ANALYSIS_PROMPT. format(
            metrics_data=metrics_data,
            log_data=log_data,
            alerts_data=alerts_data,
            topology_data=topology_data,
        )

        tools_description = self._get_tools_description()
        system_prompt = DISCOVERY_AGENT_SYSTEM_PROMPT. format(tools=tools_description)

        try:
            response = await self.llm.generate(analysis_prompt, system_prompt)

            #print(f"\n{'=' * 60}\nLLM RESPONSE:\n{'=' * 60}\n{response.content}\n{'=' * 60}\n")

            # Parse LLM response
            report = self._parse_llm_response(
                response.content,
                scope=scope,
                nodes_analyzed=nodes_analyzed,
            )
            report.llm_provider = self.llm.provider_name
            report.raw_llm_response = response.content

        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            # Fall back to simple analysis
            report = await self._create_simple_report(
                metrics_result. data if metrics_result.success else {},
                alerts_result.data if alerts_result.success else {},
                scope,
                nodes_analyzed,
            )

        return report, tool_calls

    async def _run_without_llm(self, node_id: Optional[str] = None) -> tuple[DiagnosisReport, int]:
        """Run discovery without LLM (uses MCP diagnosis tool)."""
        tool_calls = 0
        scope = node_id or "network-wide"

        # Use the MCP run_diagnosis tool directly
        self.logger.info("Running diagnosis via MCP tool...")

        diagnosis_result = await self.mcp_client.run_diagnosis(node_id=node_id)
        tool_calls += 1

        if not diagnosis_result.success:
            return DiagnosisReport(
                scope=scope,
                summary=f"Diagnosis failed: {diagnosis_result.error}",
            ), tool_calls

        # Convert MCP diagnosis result to our report format
        data = diagnosis_result. data

        report = DiagnosisReport(
            scope=scope,
            nodes_analyzed=data. get("nodes_analyzed", 0),
            analysis_method="mcp-rule-based",
        )

        # Parse issues from MCP result
        for issue_data in data.get("issues", []):
            issue = DetectedIssue(
                issue_type=self._parse_issue_type(issue_data. get("type", "UNKNOWN")),
                severity=self._parse_severity(issue_data. get("severity", "medium")),
                node_id=issue_data.get("node_id", ""),
                current_value=issue_data.get("value"),
                description=f"{issue_data.get('type', 'Unknown')} detected",
            )
            report. add_issue(issue)

        # Set overall status
        status_str = data.get("overall_status", "healthy")
        try:
            report. overall_status = IssueSeverity(status_str.lower())
        except ValueError:
            report. overall_status = IssueSeverity. HEALTHY

        return report, tool_calls

    def _parse_llm_response(
        self,
        response: str,
        scope: str,
        nodes_analyzed: int,
    ) -> DiagnosisReport:
        """Parse LLM response into a DiagnosisReport."""
        try:
            # Try to extract JSON from response
            json_match = re. search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match. group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")

            data = json.loads(json_str)

            report = DiagnosisReport. from_llm_response(
                data,
                scope=scope,
                nodes_analyzed=nodes_analyzed,
                analysis_method="llm-mcp",
            )

            return report

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")

            # Create a basic report
            return DiagnosisReport(
                scope=scope,
                nodes_analyzed=nodes_analyzed,
                summary=f"LLM response parsing failed: {str(e)[:100]}",
                analysis_method="llm-mcp-failed",
            )

    async def _create_simple_report(
        self,
        metrics_data: dict,
        alerts_data: dict,
        scope: str,
        nodes_analyzed: int,
    ) -> DiagnosisReport:
        """Create a simple report from raw data (fallback)."""
        report = DiagnosisReport(
            scope=scope,
            nodes_analyzed=nodes_analyzed,
            analysis_method="mcp-simple",
        )

        # Check alerts
        alerts = alerts_data. get("alerts", [])
        for alert in alerts:
            issue = DetectedIssue(
                issue_type=self._parse_issue_type(alert.get("type", "UNKNOWN")),
                severity=self._parse_severity(alert. get("severity", "medium")),
                node_id=alert.get("node_id", ""),
                description=alert.get("description", "Alert detected"),
            )
            report.add_issue(issue)

        if not report.issues:
            report.summary = "No issues detected"
            report.overall_status = IssueSeverity.HEALTHY
        else:
            report.summary = f"Detected {len(report.issues)} issues"

        return report

    def _summarize_logs(self, log_data: dict) -> str:
        """Summarize logs for LLM context."""
        if not log_data:
            return "No logs available"

        logs = log_data. get("logs", [])
        if not logs:
            return "No logs in the specified time range"

        # Count by level
        level_counts = {}
        for log in logs:
            level = log.get("level", "UNKNOWN")
            level_counts[level] = level_counts. get(level, 0) + 1

        # Get sample error/warning logs
        important_logs = [l for l in logs if l.get("level") in ["ERROR", "CRITICAL", "WARNING"]][:10]

        summary = f"Total logs: {len(logs)}\n"
        summary += f"By level: {level_counts}\n"
        summary += "\nSample important logs:\n"
        for log in important_logs:
            summary += f"- [{log. get('level')}] {log.get('node_name')}: {log.get('message', '')[:80]}\n"

        return summary

    def _summarize_topology(self, topology_data: dict) -> str:
        """Summarize topology for LLM context."""
        if not topology_data:
            return "No topology data"

        summary_data = topology_data.get("summary", {})
        nodes = topology_data.get("nodes", [])

        summary = f"Network has {summary_data.get('nodes', 0)} nodes and {summary_data. get('links', 0)} links.\n"
        summary += f"Node types: {summary_data.get('types', [])}\n"
        summary += f"Locations: {summary_data.get('locations', [])}\n"

        # Node status summary
        status_counts = {}
        for node in nodes:
            status = node.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        summary += f"Node status: {status_counts}"

        return summary

    def _get_tools_description(self) -> str:
        """Get description of available tools for the system prompt."""
        tools = self.mcp_client.get_tool_descriptions()

        lines = []
        for tool in tools:
            lines.append(f"- {tool['name']}: {tool['description'][:100]}...")

        return "\n".join(lines)

    def _parse_issue_type(self, type_str: str) -> IssueType:
        """Parse issue type string to enum."""
        try:
            return IssueType(type_str. upper())
        except ValueError:
            return IssueType. UNKNOWN

    def _parse_severity(self, severity_str: str) -> IssueSeverity:
        """Parse severity string to enum."""
        try:
            return IssueSeverity(severity_str.lower())
        except ValueError:
            return IssueSeverity. MEDIUM

    # =========================================================================
    # Convenience methods
    # =========================================================================

    async def run_single_node(self, node_id: str) -> AgentResult:
        """Run diagnosis on a single node."""
        return await self.run(node_id=node_id)

    async def run_quick(self) -> AgentResult:
        """Run quick diagnosis without LLM."""
        return await self. run(use_llm=False)

    async def get_active_anomalies(self) -> list[dict]:
        """Get currently active anomalies via MCP."""
        result = await self.mcp_client.get_anomalies()
        if result.success:
            return result.data. get("anomalies", [])
        return []

    async def inject_test_anomaly(
        self,
        node_id: str,
        anomaly_type: str,
        severity: str = "medium",
    ) -> dict:
        """Inject a test anomaly via MCP."""
        result = await self.mcp_client.inject_test_anomaly(node_id, anomaly_type, severity)
        return result. data if result.success else {"error": result.error}

    async def clear_anomalies(self) -> dict:
        """Clear all anomalies via MCP."""
        result = await self. mcp_client. clear_anomaly()
        return result.data if result. success else {"error": result.error}