"""
Policy Agent

The Policy Agent that evaluates policies and recommends actions using MCP tools.
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
from src.agents.policy.models import (
    PolicyRecommendation,
    RecommendedAction,
    MatchedPolicy,
    ActionPriority,
)
from src.agents.policy.prompts import (
    POLICY_AGENT_SYSTEM_PROMPT,
    POLICY_EVALUATION_PROMPT,
    NO_ISSUES_PROMPT,
)
from src.agents.discovery.models import DiagnosisReport, DetectedIssue

logger = logging.getLogger(__name__)


class PolicyAgent(BaseAgent):
    """
    Policy Agent that evaluates policies and recommends actions.

    This agent:
    1. Receives diagnosis reports from the Discovery Agent
    2. Uses MCP tools to query applicable policies
    3. Uses LLM to analyze and prioritize recommendations
    4. Produces a PolicyRecommendation for the Compliance Agent

    Example: 
        agent = PolicyAgent()
        diagnosis = await discovery_agent.run()
        result = await agent.evaluate(diagnosis. result)
        print(result.result. get_summary())
    """

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            llm: Optional[BaseLLM] = None,
    ):
        """
        Initialize the Policy Agent.

        Args:
            config:  Agent configuration
            llm: LLM instance (creates one based on config if not provided)
        """
        super().__init__(name="policy", config=config)

        # Initialize LLM
        self.llm = llm or create_llm(self.config.llm)
        self.llm_available = self.llm.is_available()

        # Initialize MCP Client
        self.mcp_client = MCPClient()

        if self.llm_available:
            logger.info(f"Policy Agent initialized with LLM: {self.llm.provider_name}")
        else:
            logger.warning("Policy Agent:  No LLM available, will use simplified evaluation")

        logger.info(f"Policy Agent has access to {len(self.mcp_client.get_available_tools())} MCP tools")

    async def run(
            self,
            diagnosis: Optional[DiagnosisReport] = None,
            use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Run the Policy Agent.

        This is the main entry point.  If no diagnosis is provided,
        it will run the Discovery Agent first.

        Args:
            diagnosis: DiagnosisReport from Discovery Agent (optional)
            use_llm: Override LLM usage

        Returns:
            AgentResult containing the PolicyRecommendation
        """
        # If no diagnosis provided, run discovery first
        if diagnosis is None:
            from src.agents.discovery import DiscoveryAgent
            discovery = DiscoveryAgent()
            discovery_result = await discovery.run()
            if not discovery_result.success:
                result = self._create_result()
                result.complete(error=f"Discovery failed: {discovery_result.error}")
                return result
            diagnosis = discovery_result.result

        return await self.evaluate(diagnosis, use_llm)

    async def evaluate(
            self,
            diagnosis: DiagnosisReport,
            use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Evaluate policies for a diagnosis report.

        Args:
            diagnosis: DiagnosisReport from Discovery Agent
            use_llm: Override LLM usage

        Returns:
            AgentResult containing the PolicyRecommendation
        """
        result = self._create_result()
        start_time = time.time()
        tool_calls = 0

        try:
            self.logger.info(f"Evaluating policies for diagnosis: {diagnosis.id}")
            self.logger.info(f"Issues to evaluate: {len(diagnosis.issues)}")

            # Determine if we should use LLM
            should_use_llm = use_llm if use_llm is not None else self.llm_available

            # Create recommendation
            recommendation = PolicyRecommendation(
                diagnosis_id=diagnosis.id,
                diagnosis_summary=diagnosis.summary,
                issues_evaluated=len(diagnosis.issues),
                analysis_method="llm-mcp" if should_use_llm else "mcp-rule-based",
            )

            # Handle no issues case
            if not diagnosis.issues:
                self.logger.info("No issues in diagnosis, no actions needed")
                recommendation.summary = "No issues detected, no actions required"
                recommendation.analysis_duration_ms = int((time.time() - start_time) * 1000)
                result.complete(result=recommendation)
                self._record_execution(result)
                return result

            # Step 1: Get available policies
            self.logger.info("Step 1: Getting available policies via MCP...")
            policies_result = await self.mcp_client.get_policies(status="active")
            tool_calls += 1

            if not policies_result.success:
                self.logger.error(f"Failed to get policies: {policies_result.error}")
                result.complete(error=f"Failed to get policies:  {policies_result.error}")
                return result

            policies_data = policies_result.data
            recommendation.total_policies_evaluated = policies_data.get("total_policies", 0)

            # Step 2: Evaluate policies for each issue
            self.logger.info("Step 2: Evaluating policies for each issue...")

            all_matching_policies = []
            for issue in diagnosis.issues:
                eval_result = await self.mcp_client.evaluate_policies(
                    anomaly_type=issue.issue_type.value,
                    severity=issue.severity.value,
                    node_type=issue.node_type if issue.node_type else None,
                )
                tool_calls += 1

                if eval_result.success:
                    eval_data = eval_result.data
                    all_matching_policies.append({
                        "issue": issue,
                        "matched_policies": eval_data.get("matched_policies", []),
                        "recommended_actions": eval_data.get("recommended_actions", []),
                    })

            # Step 3: Use LLM or rule-based analysis
            if should_use_llm and self.llm_available:
                self.logger.info("Step 3: Running LLM policy analysis...")
                recommendation = await self._run_with_llm(
                    diagnosis,
                    policies_data,
                    all_matching_policies,
                    recommendation,
                )
                recommendation.llm_provider = self.llm.provider_name
            else:
                self.logger.info("Step 3: Running rule-based policy analysis...")
                recommendation = self._run_without_llm(
                    diagnosis,
                    all_matching_policies,
                    recommendation,
                )

            recommendation.analysis_duration_ms = int((time.time() - start_time) * 1000)
            recommendation.tool_calls_made = tool_calls

            self.logger.info(f"Policy evaluation complete. Actions:  {len(recommendation.recommended_actions)}")
            self.logger.info(recommendation.get_summary())

            result.complete(result=recommendation)

        except Exception as e:
            self.logger.error(f"Policy agent error: {e}")
            result.complete(error=str(e))

        self._record_execution(result)
        return result

    async def _run_with_llm(
            self,
            diagnosis: DiagnosisReport,
            policies_data: dict,
            matching_results: list[dict],
            recommendation: PolicyRecommendation,
    ) -> PolicyRecommendation:
        """Run policy evaluation using LLM."""

        # Prepare diagnosis summary for LLM
        diagnosis_summary = self._format_diagnosis_for_llm(diagnosis)

        # Prepare policies summary
        policies_summary = self._format_policies_for_llm(policies_data, matching_results)

        # Prepare prompt
        prompt = POLICY_EVALUATION_PROMPT.format(
            diagnosis_report=diagnosis_summary,
            policies=policies_summary,
        )

        tools_description = self._get_tools_description()
        system_prompt = POLICY_AGENT_SYSTEM_PROMPT.format(tools=tools_description)

        try:
            response = await self.llm.generate(prompt, system_prompt)

            # Parse LLM response
            parsed = self._parse_llm_response(response.content)

            if parsed:
                recommendation = PolicyRecommendation.from_llm_response(
                    parsed,
                    diagnosis_id=diagnosis.id,
                    diagnosis_summary=diagnosis.summary,
                    issues_evaluated=len(diagnosis.issues),
                    total_policies_evaluated=policies_data.get("total_policies", 0),
                    analysis_method="llm-mcp",
                )
                recommendation.raw_llm_response = response.content
            else:
                # Fallback to rule-based if parsing fails
                self.logger.warning("LLM response parsing failed, using rule-based")
                recommendation = self._run_without_llm(diagnosis, matching_results, recommendation)

        except Exception as e:
            self.logger.error(f"LLM policy analysis failed: {e}")
            recommendation = self._run_without_llm(diagnosis, matching_results, recommendation)

        return recommendation

    def _run_without_llm(
            self,
            diagnosis: DiagnosisReport,
            matching_results: list[dict],
            recommendation: PolicyRecommendation,
    ) -> PolicyRecommendation:
        """Run policy evaluation without LLM (rule-based)."""

        for match_data in matching_results:
            issue = match_data["issue"]
            matched_policies = match_data["matched_policies"]
            recommended_actions = match_data["recommended_actions"]

            # Create MatchedPolicy objects
            for policy_data in matched_policies:
                matched = MatchedPolicy(
                    policy_id=policy_data.get("policy_id", ""),
                    policy_name=policy_data.get("policy_name", ""),
                    conditions_matched=policy_data.get("conditions_met", []),
                )
                recommendation.matched_policies.append(matched)

            # Create RecommendedAction objects
            for action_data in recommended_actions:
                action = RecommendedAction(
                    action_type=action_data.get("action_type", ""),
                    target_node_id=issue.node_id,
                    target_node_name=issue.node_name,
                    target_node_type=issue.node_type,
                    parameters=action_data.get("parameters", {}),
                    source_policy_id=action_data.get("policy_id", ""),
                    source_policy_name=action_data.get("policy_name", ""),
                    source_issue_id=issue.id,
                    source_issue_type=issue.issue_type.value,
                    priority=self._determine_priority(issue.severity.value),
                    reason=f"Policy {action_data.get('policy_name', 'Unknown')} recommends this action for {issue.issue_type.value}",
                    requires_approval=action_data.get("requires_approval", False),
                )
                recommendation.recommended_actions.append(action)

        # Set summary
        if recommendation.recommended_actions:
            recommendation.summary = f"Found {len(recommendation.recommended_actions)} actions from {len(recommendation.matched_policies)} matching policies"
        else:
            recommendation.summary = "No matching policies found for the detected issues"

        # Update overall priority
        recommendation._update_overall_priority()

        return recommendation

    def _format_diagnosis_for_llm(self, diagnosis: DiagnosisReport) -> str:
        """Format diagnosis report for LLM consumption."""
        lines = [
            f"Diagnosis ID: {diagnosis.id}",
            f"Overall Status: {diagnosis.overall_status.value}",
            f"Nodes Analyzed: {diagnosis.nodes_analyzed}",
            f"Total Issues: {len(diagnosis.issues)}",
            "",
            "Issues:",
        ]

        for i, issue in enumerate(diagnosis.issues, 1):
            lines.append(f"\n{i}. {issue.issue_type.value} ({issue.severity.value})")
            lines.append(f"   Node: {issue.node_name} ({issue.node_id})")
            lines.append(f"   Type: {issue.node_type}")
            lines.append(f"   Description: {issue.description}")
            if issue.current_value is not None:
                lines.append(f"   Value: {issue.current_value}{issue.unit or ''}")

        return "\n".join(lines)

    def _format_policies_for_llm(self, policies_data: dict, matching_results: list[dict]) -> str:
        """Format policies for LLM consumption."""
        lines = [
            f"Total Active Policies: {policies_data.get('total_policies', 0)}",
            "",
            "Matching Policies by Issue:",
        ]

        for match_data in matching_results:
            issue = match_data["issue"]
            matched = match_data["matched_policies"]
            actions = match_data["recommended_actions"]

            lines.append(f"\nFor {issue.issue_type.value} on {issue.node_name}:")

            if matched:
                for policy in matched:
                    lines.append(f"  - {policy.get('policy_name', 'Unknown')} ({policy.get('policy_id', '')})")
                    lines.append(f"    Conditions: {policy.get('conditions_met', [])}")
            else:
                lines.append("  - No matching policies")

            if actions:
                lines.append("  Recommended Actions:")
                for action in actions:
                    lines.append(f"    - {action.get('action_type', 'Unknown')}")

        return "\n".join(lines)

    def _get_tools_description(self) -> str:
        """Get relevant tools description for system prompt."""
        relevant_tools = [
            "get_policies",
            "get_policy_details",
            "evaluate_policies",
            "validate_action",
            "get_compliance_rules",
        ]

        all_tools = self.mcp_client.get_tool_descriptions()

        lines = []
        for tool in all_tools:
            if tool["name"] in relevant_tools:
                lines.append(f"- {tool['name']}:  {tool['description'][: 80]}...")

        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse LLM response into dictionary."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'```json\s*(.*? )\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None

            return json.loads(json_str)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return None

    def _determine_priority(self, severity: str) -> ActionPriority:
        """Determine action priority from issue severity."""
        mapping = {
            "critical": ActionPriority.IMMEDIATE,
            "high": ActionPriority.HIGH,
            "medium": ActionPriority.NORMAL,
            "low": ActionPriority.LOW,
        }
        return mapping.get(severity.lower(), ActionPriority.NORMAL)

    # =========================================================================
    # Convenience methods
    # =========================================================================

    async def evaluate_single_issue(
            self,
            issue_type: str,
            severity: str,
            node_id: str,
            node_type: str = "",
    ) -> AgentResult:
        """Evaluate policies for a single issue."""
        # Create a minimal diagnosis with one issue
        diagnosis = DiagnosisReport(
            scope=node_id,
            nodes_analyzed=1,
        )

        from src.agents.discovery.models import IssueType, IssueSeverity

        issue = DetectedIssue(
            issue_type=IssueType(issue_type),
            severity=IssueSeverity(severity.lower()),
            node_id=node_id,
            node_type=node_type,
        )
        diagnosis.add_issue(issue)

        return await self.evaluate(diagnosis)

    async def get_all_policies(self) -> list[dict]:
        """Get all active policies via MCP."""
        result = await self.mcp_client.get_policies(status="active")
        if result.success:
            return result.data.get("policies", [])
        return []

    async def get_policy_details(self, policy_id: str) -> Optional[dict]:
        """Get details for a specific policy."""
        result = await self.mcp_client.call_tool("get_policy_details", {"policy_id": policy_id})
        if result.success:
            return result.data
        return None