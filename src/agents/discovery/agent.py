"""
Discovery Agent

The main Discovery Agent that monitors the network and creates diagnosis reports.
"""

import json
import logging
import time
from typing import Any, Optional
from datetime import datetime

from src.agents.base import BaseAgent, AgentResult
from src.agents.config import AgentConfig, config as default_config
from src.agents.llm import create_llm, BaseLLM
from src.agents.discovery.models import (
    DiagnosisReport,
    DetectedIssue,
    IssueSeverity,
    IssueType,
)
from src.agents.discovery.analyzers import MetricAnalyzer, LogAnalyzer
from src.agents.discovery.prompts import (
    SYSTEM_PROMPT,
    ROOT_CAUSE_ANALYSIS_PROMPT,
    ROOT_CAUSE_SCHEMA,
)

# Import simulator components for data collection
from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector

# Import knowledge graph for topology context
from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.topology import TopologyManager

logger = logging.getLogger(__name__)


class DiscoveryAgent(BaseAgent):
    """
    Discovery Agent for network monitoring and anomaly detection.

    This agent:
    1. Collects telemetry and logs from the network
    2. Analyzes data using rule-based and LLM-based methods
    3. Creates diagnosis reports with detected issues
    4. Provides root cause analysis when LLM is available

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
            config: Agent configuration (uses default if not provided)
            llm: LLM instance (creates one based on config if not provided)
        """
        super().__init__(name="discovery", config=config)

        # Initialize LLM
        self.llm = llm or create_llm(self.config.llm)
        self.llm_available = self.llm.is_available()

        if self.llm_available:
            logger.info(f"Discovery Agent initialized with LLM: {self.llm.provider_name}")
        else:
            logger.info("Discovery Agent initialized in rule-based mode (no LLM)")

        # Initialize analyzers
        self.metric_analyzer = MetricAnalyzer(self.config.discovery)
        self.log_analyzer = LogAnalyzer(self.config.discovery)

        # Initialize simulator components (lazy loading)
        self._network_sim: Optional[NetworkSimulator] = None
        self._log_generator: Optional[LogGenerator] = None
        self._telemetry_generator: Optional[TelemetryGenerator] = None
        self._anomaly_injector: Optional[AnomalyInjector] = None

        # Initialize knowledge graph (lazy loading)
        self._neo4j_client: Optional[Neo4jClient] = None
        self._topology_manager: Optional[TopologyManager] = None

    def _get_simulator_components(self):
        """Get or initialize simulator components."""
        if self._network_sim is None:
            self._network_sim = NetworkSimulator()
            self._network_sim.create_default_topology()
            self._log_generator = LogGenerator(self._network_sim)
            self._telemetry_generator = TelemetryGenerator(self._network_sim)
            self._anomaly_injector = AnomalyInjector(
                self._network_sim,
                self._telemetry_generator,
                self._log_generator
            )

        return (
            self._network_sim,
            self._log_generator,
            self._telemetry_generator,
            self._anomaly_injector
        )

    def _get_topology_manager(self) -> Optional[TopologyManager]:
        """Get or initialize topology manager."""
        if self._topology_manager is None:
            try:
                self._neo4j_client = Neo4jClient(
                    uri=self.config.neo4j.uri,
                    user=self.config.neo4j.user,
                    password=self.config.neo4j.password,
                    database=self.config.neo4j.database,
                )
                self._neo4j_client.connect()
                self._topology_manager = TopologyManager(self._neo4j_client)
                logger.info("Connected to Neo4j for topology context")
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j: {e}. Topology context disabled.")
                return None

        return self._topology_manager

    async def run(
            self,
            node_id: Optional[str] = None,
            include_logs: bool = True,
            use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Run the Discovery Agent to analyze the network.

        Args:
            node_id: Optional specific node to analyze (None = all nodes)
            include_logs: Whether to analyze logs
            use_llm: Override LLM usage (None = use if available)

        Returns:
            AgentResult containing the DiagnosisReport
        """
        result = self._create_result()
        start_time = time.time()

        try:
            self.logger.info(f"Starting discovery run.  Scope: {node_id or 'network-wide'}")

            # Determine if we should use LLM
            should_use_llm = use_llm if use_llm is not None else self.llm_available

            # Create diagnosis report
            report = DiagnosisReport(
                scope=node_id or "network-wide",
                analysis_method="llm-enhanced" if should_use_llm else "rule-based",
                llm_provider=self.llm.provider_name if should_use_llm else None,
            )

            # Step 1: Collect data
            self.logger.info("Step 1: Collecting telemetry and logs...")
            metrics_data, logs_data = await self._collect_data(node_id, include_logs)

            report.nodes_analyzed = len(metrics_data)
            self.logger.info(f"Collected data from {len(metrics_data)} nodes")

            # Step 2: Rule-based analysis
            self.logger.info("Step 2: Running rule-based analysis...")
            rule_based_issues = self._run_rule_based_analysis(metrics_data, logs_data)

            for issue in rule_based_issues:
                report.add_issue(issue)

            self.logger.info(f"Rule-based analysis found {len(rule_based_issues)} issues")

            # Step 3: LLM-enhanced analysis (if available)
            if should_use_llm and report.issues:
                self.logger.info("Step 3: Running LLM root cause analysis...")
                await self._run_llm_analysis(report, metrics_data, logs_data)

            # Step 4: Add topology context
            if self.config.discovery.include_topology_context:
                self.logger.info("Step 4: Adding topology context...")
                await self._add_topology_context(report)

            # Finalize report
            report.analysis_duration_ms = int((time.time() - start_time) * 1000)

            self.logger.info(f"Discovery complete. Status: {report.overall_status.value}")
            self.logger.info(report.get_summary())

            result.complete(result=report)

        except Exception as e:
            self.logger.error(f"Discovery agent error: {e}")
            result.complete(error=str(e))

        self._record_execution(result)
        return result

    async def _collect_data(
            self,
            node_id: Optional[str],
            include_logs: bool,
    ) -> tuple[list[dict], list[dict]]:
        """Collect telemetry and log data."""
        network_sim, log_gen, tel_gen, _ = self._get_simulator_components()

        # Collect metrics
        metrics_data = []

        if node_id:
            node = network_sim.get_node(node_id)
            if node:
                snapshot = tel_gen.generate_snapshot(node)
                metrics_data.append({
                    "node_id": snapshot.node_id,
                    "node_name": snapshot.node_name,
                    "node_type": node.type.value,
                    "status": snapshot.status.value,
                    "metrics": {
                        m.metric_type.value: {"value": m.value, "unit": m.unit}
                        for m in snapshot.metrics
                    }
                })
        else:
            for node in network_sim.get_all_nodes():
                snapshot = tel_gen.generate_snapshot(node)
                metrics_data.append({
                    "node_id": snapshot.node_id,
                    "node_name": snapshot.node_name,
                    "node_type": node.type.value,
                    "status": snapshot.status.value,
                    "metrics": {
                        m.metric_type.value: {"value": m.value, "unit": m.unit}
                        for m in snapshot.metrics
                    }
                })

        # Collect logs
        logs_data = []
        if include_logs:
            nodes = None
            if node_id:
                node = network_sim.get_node(node_id)
                nodes = [node] if node else None

            logs = log_gen.generate_batch(
                count=self.config.discovery.log_analysis_count,
                time_range_minutes=self.config.discovery.log_time_range_minutes,
                nodes=nodes,
            )

            logs_data = [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "node_id": log.node_id,
                    "node_name": log.node_name,
                    "level": log.level.value,
                    "source": log.source,
                    "message": log.message,
                }
                for log in logs
            ]

        return metrics_data, logs_data

    def _run_rule_based_analysis(
            self,
            metrics_data: list[dict],
            logs_data: list[dict],
    ) -> list[DetectedIssue]:
        """Run rule-based analysis on collected data."""
        issues = []

        # Analyze metrics for each node
        for node_data in metrics_data:
            node_issues = self.metric_analyzer.analyze_node_metrics(
                node_id=node_data["node_id"],
                node_name=node_data["node_name"],
                node_type=node_data["node_type"],
                metrics=node_data["metrics"],
            )
            issues.extend(node_issues)

        # Analyze logs
        if logs_data:
            log_issues = self.log_analyzer.analyze_logs(logs_data)

            # Merge log issues with metric issues (avoid duplicates)
            existing_keys = {f"{i.node_id}:{i.issue_type.value}" for i in issues}
            for log_issue in log_issues:
                key = f"{log_issue.node_id}:{log_issue.issue_type.value}"
                if key not in existing_keys:
                    issues.append(log_issue)
                else:
                    # Add log info to existing issue
                    for existing in issues:
                        if f"{existing.node_id}:{existing.issue_type.value}" == key:
                            existing.related_logs.extend(log_issue.related_logs)
                            break

        return issues

    async def _run_llm_analysis(
            self,
            report: DiagnosisReport,
            metrics_data: list[dict],
            logs_data: list[dict],
    ) -> None:
        """Run LLM-based root cause analysis."""
        if not self.llm_available:
            return

        try:
            # Prepare issues summary for LLM
            issues_summary = "\n".join([
                f"- {i.issue_type.value} ({i.severity.value}) on {i.node_name}: {i.description}"
                for i in report.issues
            ])

            # Prepare topology context
            topology_context = "Topology context not available"
            topo_mgr = self._get_topology_manager()
            if topo_mgr:
                try:
                    summary = topo_mgr.get_topology_summary()
                    topology_context = f"Network has {summary['nodes']} nodes and {summary['links']} links."

                    # Add affected node details
                    affected_nodes = set(i.node_id for i in report.issues)
                    for node_id in list(affected_nodes)[:3]:  # Limit to 3 nodes
                        node = topo_mgr.get_node(node_id)
                        if node:
                            connected = topo_mgr.get_connected_nodes(node_id)
                            topology_context += f"\n{node.name} ({node.type.value}) connects to {len(connected)} nodes."
                except Exception as e:
                    logger.warning(f"Could not get topology context: {e}")

            # Prepare logs summary
            logs_summary = "No significant log entries"
            if logs_data:
                error_logs = [l for l in logs_data if l["level"] in ["ERROR", "CRITICAL"]]
                if error_logs:
                    logs_summary = f"Found {len(error_logs)} error/critical logs.  Sample:\n"
                    logs_summary += "\n".join([
                        f"- [{l['level']}] {l['node_name']}: {l['message'][:80]}"
                        for l in error_logs[:5]
                    ])

            # Create prompt
            prompt = ROOT_CAUSE_ANALYSIS_PROMPT.format(
                issues=issues_summary,
                topology_context=topology_context,
                logs_summary=logs_summary,
            )

            # Call LLM
            response = await self.llm.generate_structured(
                prompt=prompt,
                output_schema=ROOT_CAUSE_SCHEMA,
                system_prompt=SYSTEM_PROMPT,
            )

            # Update report with LLM analysis
            if "error" not in response:
                report.root_cause_analysis = response.get("root_cause", "")
                report.overall_recommendations = response.get("remediation_steps", [])

                # Update issue priorities based on LLM recommendation
                priority_ranking = response.get("priority_ranking", [])
                for ranking in priority_ranking:
                    issue_id = ranking.get("issue_id", "")
                    # Find matching issue and add priority info
                    for issue in report.issues:
                        if issue.issue_type.value.lower() in issue_id.lower():
                            issue.metadata["llm_priority"] = ranking.get("priority", 0)
                            issue.metadata["priority_reason"] = ranking.get("reason", "")

                self.logger.info("LLM root cause analysis completed")
            else:
                self.logger.warning(f"LLM analysis returned error: {response.get('error')}")

        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")

    async def _add_topology_context(self, report: DiagnosisReport) -> None:
        """Add topology context to issues (affected downstream nodes)."""
        topo_mgr = self._get_topology_manager()
        if not topo_mgr:
            return

        try:
            for issue in report.issues:
                if issue.node_id:
                    # Get downstream dependencies
                    dependencies = topo_mgr.get_node_dependencies(issue.node_id)
                    issue.affected_downstream_nodes = [
                        f"{d.name} ({d.type.value})" for d in dependencies[:5]
                    ]

                    if dependencies:
                        issue.metadata["impact_count"] = len(dependencies)
        except Exception as e:
            self.logger.warning(f"Could not add topology context: {e}")

    async def run_single_node(self, node_id: str) -> AgentResult:
        """Convenience method to run diagnosis on a single node."""
        return await self.run(node_id=node_id)

    async def run_quick(self) -> AgentResult:
        """Run a quick diagnosis without logs or LLM (fastest)."""
        return await self.run(include_logs=False, use_llm=False)

    def get_active_anomalies(self) -> list[dict]:
        """Get currently active anomalies from the simulator."""
        _, _, _, anomaly_inj = self._get_simulator_components()

        return [
            {
                "id": a.id,
                "type": a.anomaly_type.value,
                "severity": a.severity.value,
                "node_id": a.node_id,
                "description": a.description,
                "started_at": a.started_at.isoformat(),
            }
            for a in anomaly_inj.get_active_anomalies()
        ]