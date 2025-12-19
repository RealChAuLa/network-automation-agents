"""
Compliance Agent

The Compliance Agent that validates actions against compliance rules.
"""

import json
import logging
import time
import re
from datetime import datetime
from typing import Any, Optional

from src.agents.base import BaseAgent, AgentResult
from src.agents.config import AgentConfig, config as default_config
from src.agents.llm import create_llm, BaseLLM
from src.agents.mcp_client import MCPClient
from src.agents.compliance.models import (
    ComplianceResult,
    ActionValidation,
    ValidationStatus,
    ComplianceViolation,
    ViolationType,
)
from src.agents.compliance.checks import ComplianceChecker
from src.agents.compliance.prompts import (
    COMPLIANCE_AGENT_SYSTEM_PROMPT,
    COMPLIANCE_VALIDATION_PROMPT,
    NO_ACTIONS_PROMPT,
)
from src.agents.policy.models import PolicyRecommendation, RecommendedAction

logger = logging.getLogger(__name__)


class ComplianceAgent(BaseAgent):
    """
    Compliance Agent that validates actions before execution.

    This agent:
    1. Receives PolicyRecommendation from Policy Agent
    2. Uses MCP tools to check compliance rules
    3. Validates each action against rules
    4. Approves or denies actions with reasons
    5. Produces a ComplianceResult for the Execution Agent

    Example:
        >>> agent = ComplianceAgent()
        >>> policy_result = await policy_agent.evaluate(diagnosis)
        >>> result = await agent.validate(policy_result. result)
        >>> print(result.result. get_summary())
    """

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            llm: Optional[BaseLLM] = None,
    ):
        """
        Initialize the Compliance Agent.

        Args:
            config: Agent configuration
            llm: LLM instance (creates one based on config if not provided)
        """
        super().__init__(name="compliance", config=config)

        # Initialize LLM
        self.llm = llm or create_llm(self.config.llm)
        self.llm_available = self.llm.is_available()

        # Initialize MCP Client
        self.mcp_client = MCPClient()

        # Initialize compliance checker
        self.checker = ComplianceChecker()

        if self.llm_available:
            logger.info(f"Compliance Agent initialized with LLM:  {self.llm.provider_name}")
        else:
            logger.warning("Compliance Agent:  No LLM available, using rule-based validation")

        logger.info(f"Compliance Agent has access to {len(self.mcp_client.get_available_tools())} MCP tools")

    async def run(
            self,
            recommendation: Optional[PolicyRecommendation] = None,
            use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Run the Compliance Agent.

        If no recommendation is provided, it will run Discovery and Policy agents first.

        Args:
            recommendation: PolicyRecommendation from Policy Agent (optional)
            use_llm: Override LLM usage

        Returns:
            AgentResult containing the ComplianceResult
        """
        # If no recommendation provided, run the full pipeline
        if recommendation is None:
            from src.agents.policy import PolicyAgent
            policy_agent = PolicyAgent()
            policy_result = await policy_agent.run()
            if not policy_result.success:
                result = self._create_result()
                result.complete(error=f"Policy evaluation failed: {policy_result.error}")
                return result
            recommendation = policy_result.result

        return await self.validate(recommendation, use_llm)

    async def validate(
            self,
            recommendation: PolicyRecommendation,
            use_llm: Optional[bool] = None,
    ) -> AgentResult:
        """
        Validate actions in a policy recommendation.

        Args:
            recommendation: PolicyRecommendation from Policy Agent
            use_llm: Override LLM usage

        Returns:
            AgentResult containing the ComplianceResult
        """
        result = self._create_result()
        start_time = time.time()
        tool_calls = 0

        try:
            self.logger.info(f"Validating compliance for recommendation: {recommendation.id}")
            self.logger.info(f"Actions to validate: {len(recommendation.recommended_actions)}")

            # Determine if we should use LLM
            should_use_llm = use_llm if use_llm is not None else self.llm_available

            # Create compliance result
            compliance_result = ComplianceResult(
                recommendation_id=recommendation.id,
                diagnosis_id=recommendation.diagnosis_id,
                analysis_method="llm-mcp" if should_use_llm else "mcp-rule-based",
            )

            # Handle no actions case
            if not recommendation.recommended_actions:
                self.logger.info("No actions to validate")
                compliance_result.summary = "No actions to validate"
                compliance_result.analysis_duration_ms = int((time.time() - start_time) * 1000)
                result.complete(result=compliance_result)
                self._record_execution(result)
                return result

            # Step 1: Get compliance rules from MCP
            self.logger.info("Step 1: Getting compliance rules via MCP...")
            rules_result = await self.mcp_client.call_tool("get_compliance_rules", {})
            tool_calls += 1

            compliance_rules = []
            if rules_result.success:
                compliance_rules = rules_result.data.get("rules", [])
                compliance_result.rules_evaluated = [r.get("id", "") for r in compliance_rules]

            # Step 2: Get execution history for rate limiting
            self.logger.info("Step 2: Getting execution history via MCP...")
            history_result = await self.mcp_client.call_tool("get_execution_history", {"limit": 50})
            tool_calls += 1

            recent_actions = []
            if history_result.success:
                recent_actions = history_result.data.get("executions", [])

            # Step 3: Validate each action
            if should_use_llm and self.llm_available:
                self.logger.info("Step 3: Running LLM compliance validation...")
                compliance_result = await self._run_with_llm(
                    recommendation,
                    compliance_rules,
                    recent_actions,
                    compliance_result,
                )
                compliance_result.llm_provider = self.llm.provider_name
            else:
                self.logger.info("Step 3: Running rule-based compliance validation...")
                compliance_result = await self._run_without_llm(
                    recommendation,
                    compliance_rules,
                    recent_actions,
                    compliance_result,
                )

            compliance_result.analysis_duration_ms = int((time.time() - start_time) * 1000)
            compliance_result.tool_calls_made = tool_calls

            self.logger.info(
                f"Compliance validation complete.  Approved: {compliance_result.approved_count}/{compliance_result.total_actions}")
            self.logger.info(compliance_result.get_summary())

            result.complete(result=compliance_result)

        except Exception as e:
            self.logger.error(f"Compliance agent error: {e}")
            result.complete(error=str(e))

        self._record_execution(result)
        return result

    async def _run_with_llm(
            self,
            recommendation: PolicyRecommendation,
            compliance_rules: list[dict],
            recent_actions: list[dict],
            compliance_result: ComplianceResult,
    ) -> ComplianceResult:
        """Run compliance validation using LLM."""

        current_time = datetime.utcnow()

        # Prepare data for LLM
        recommendation_summary = self._format_recommendation_for_llm(recommendation)
        rules_summary = self._format_rules_for_llm(compliance_rules)
        history_summary = self._format_history_for_llm(recent_actions)

        # Check maintenance window
        in_maintenance = self.checker.maintenance_window_start <= current_time.hour < self.checker.maintenance_window_end

        # Prepare prompt
        prompt = COMPLIANCE_VALIDATION_PROMPT.format(
            recommendation=recommendation_summary,
            compliance_rules=rules_summary,
            execution_history=history_summary,
            current_time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
            day_of_week=current_time.strftime("%A"),
            in_maintenance_window="Yes" if in_maintenance else "No",
        )

        tools_description = self._get_tools_description()
        system_prompt = COMPLIANCE_AGENT_SYSTEM_PROMPT.format(tools=tools_description)

        try:
            response = await self.llm.generate(prompt, system_prompt)

            # Parse LLM response
            parsed = self._parse_llm_response(response.content)

            if parsed:
                compliance_result = self._build_result_from_llm(
                    parsed,
                    recommendation,
                    compliance_result,
                )
                compliance_result.raw_llm_response = response.content
            else:
                # Fallback to rule-based
                self.logger.warning("LLM response parsing failed, using rule-based")
                compliance_result = await self._run_without_llm(
                    recommendation,
                    compliance_rules,
                    recent_actions,
                    compliance_result,
                )

        except Exception as e:
            self.logger.error(f"LLM compliance validation failed: {e}")
            compliance_result = await self._run_without_llm(
                recommendation,
                compliance_rules,
                recent_actions,
                compliance_result,
            )

        return compliance_result

    async def _run_without_llm(
            self,
            recommendation: PolicyRecommendation,
            compliance_rules: list[dict],
            recent_actions: list[dict],
            compliance_result: ComplianceResult,
    ) -> ComplianceResult:
        """Run compliance validation without LLM (rule-based)."""

        for action in recommendation.recommended_actions:
            validation = ActionValidation(
                action_id=action.id,
                action_type=action.action_type,
                target_node_id=action.target_node_id,
                target_node_name=action.target_node_name,
            )

            # Run compliance checks
            violations = self.checker.run_all_checks(
                action=action,
                node_type=action.target_node_type,
                recent_actions=recent_actions,
            )

            # Also check via MCP validate_action tool
            mcp_validation = await self.mcp_client.validate_action(
                action_type=action.action_type,
                target_node_id=action.target_node_id,
                reason=action.reason,
            )

            if mcp_validation.success:
                mcp_data = mcp_validation.data.get("validation_result", {})

                # Add MCP violations
                for v in mcp_data.get("violations", []):
                    violations.append(ComplianceViolation(
                        violation_type=ViolationType.REGULATORY_VIOLATION,
                        rule_id=v.get("rule_id", ""),
                        rule_name=v.get("rule_name", "MCP Rule"),
                        severity="high",
                        blocking=True,
                        description=v.get("reason", "MCP validation failed"),
                        reason=v.get("reason", ""),
                    ))

                # Add MCP warnings
                for w in mcp_data.get("warnings", []):
                    validation.add_warning(w.get("reason", str(w)))

            # Add violations to validation
            has_blocking = False
            for violation in violations:
                validation.violations.append(violation)
                if violation.blocking:
                    has_blocking = True

            # Determine final status
            if has_blocking:
                validation.status = ValidationStatus.DENIED
                validation.denial_reason = "Blocking compliance violation(s) found"
            elif violations:
                # Has violations but none blocking - pending approval
                validation.status = ValidationStatus.PENDING_APPROVAL
            else:
                validation.status = ValidationStatus.APPROVED
                validation.approved_by = "system"

            compliance_result.add_validation(validation)

        # Set summary
        if compliance_result.all_approved:
            compliance_result.summary = "All actions approved for execution"
        elif compliance_result.denied_count > 0:
            compliance_result.summary = f"{compliance_result.denied_count} action(s) denied due to compliance violations"
        else:
            compliance_result.summary = f"{compliance_result.pending_count} action(s) pending approval"

        return compliance_result

    def _build_result_from_llm(
            self,
            parsed: dict,
            recommendation: PolicyRecommendation,
            compliance_result: ComplianceResult,
    ) -> ComplianceResult:
        """Build ComplianceResult from parsed LLM response."""

        compliance_result.summary = parsed.get("summary", "")
        compliance_result.reasoning = parsed.get("reasoning", "")
        compliance_result.rules_evaluated = parsed.get("rules_evaluated", [])

        # Map action IDs to actions for lookup
        action_map = {a.id: a for a in recommendation.recommended_actions}

        for val_data in parsed.get("validations", []):
            validation = ActionValidation(
                action_id=val_data.get("action_id", ""),
                action_type=val_data.get("action_type", ""),
                target_node_id=val_data.get("target_node_id", ""),
                target_node_name=val_data.get("target_node_name", ""),
            )

            # Set status
            status_str = val_data.get("status", "pending_approval")
            try:
                validation.status = ValidationStatus(status_str.lower())
            except ValueError:
                validation.status = ValidationStatus.PENDING_APPROVAL

            # Add violations
            for v_data in val_data.get("violations", []):
                violation_type_str = v_data.get("violation_type", "regulatory_violation")
                try:
                    violation_type = ViolationType(violation_type_str)
                except ValueError:
                    violation_type = ViolationType.REGULATORY_VIOLATION

                violation = ComplianceViolation(
                    violation_type=violation_type,
                    rule_id=v_data.get("rule_id", ""),
                    rule_name=v_data.get("rule_name", ""),
                    severity=v_data.get("severity", "medium"),
                    blocking=v_data.get("blocking", True),
                    description=v_data.get("description", ""),
                    reason=v_data.get("reason", ""),
                    resolution_options=v_data.get("resolution_options", []),
                )
                validation.violations.append(violation)

            # Add warnings
            validation.warnings = val_data.get("warnings", [])

            # Set approval/denial info
            validation.approved_by = val_data.get("approved_by", "system")
            validation.denial_reason = val_data.get("denial_reason", "")
            validation.defer_reason = val_data.get("defer_reason", "")

            compliance_result.add_validation(validation)

        return compliance_result

    def _format_recommendation_for_llm(self, recommendation: PolicyRecommendation) -> str:
        """Format recommendation for LLM consumption."""
        lines = [
            f"Recommendation ID: {recommendation.id}",
            f"Diagnosis ID:  {recommendation.diagnosis_id}",
            f"Issues Evaluated: {recommendation.issues_evaluated}",
            f"Overall Priority: {recommendation.overall_priority.value}",
            f"Summary: {recommendation.summary}",
            "",
            "Recommended Actions:",
        ]

        for i, action in enumerate(recommendation.recommended_actions, 1):
            lines.append(f"\n{i}. {action.action_type}")
            lines.append(f"   ID: {action.id}")
            lines.append(f"   Target:  {action.target_node_name} ({action.target_node_id})")
            lines.append(f"   Node Type: {action.target_node_type}")
            lines.append(f"   Priority: {action.priority.value}")
            lines.append(f"   Reason: {action.reason}")
            lines.append(f"   Requires Approval: {action.requires_approval}")

        return "\n".join(lines)

    def _format_rules_for_llm(self, rules: list[dict]) -> str:
        """Format compliance rules for LLM consumption."""
        if not rules:
            return "No specific compliance rules loaded from MCP."

        lines = [f"Total Rules: {len(rules)}", ""]

        for rule in rules[: 10]:  # Limit to first 10
            lines.append(f"- {rule.get('name', 'Unknown')} ({rule.get('id', '')})")
            lines.append(f"  Type: {rule.get('check_type', 'unknown')}")
            lines.append(f"  Enforcement: {rule.get('enforcement', 'unknown')}")

        return "\n".join(lines)

    def _format_history_for_llm(self, actions: list[dict]) -> str:
        """Format execution history for LLM consumption."""
        if not actions:
            return "No recent execution history."

        lines = [f"Recent Actions:  {len(actions)}", ""]

        for action in actions[:10]:  # Limit to first 10
            lines.append(f"- {action.get('action_type', 'unknown')} on {action.get('target_node_id', 'unknown')}")
            lines.append(f"  Status: {action.get('status', 'unknown')}")
            lines.append(f"  Time: {action.get('completed_at', 'unknown')}")

        return "\n".join(lines)

    def _get_tools_description(self) -> str:
        """Get relevant tools description for system prompt."""
        relevant_tools = [
            "validate_action",
            "get_compliance_rules",
            "get_execution_history",
            "get_node_details",
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
            json_match = re.search(r'```json\s*(.*? )\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None

            return json.loads(json_str)

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return None

    # =========================================================================
    # Convenience methods
    # =========================================================================

    async def validate_single_action(
            self,
            action_type: str,
            target_node_id: str,
            reason: str = "",
    ) -> AgentResult:
        """Validate a single action directly."""

        # Create a minimal recommendation with one action
        from src.agents.policy.models import PolicyRecommendation, ActionPriority

        action = RecommendedAction(
            action_type=action_type,
            target_node_id=target_node_id,
            reason=reason,
            priority=ActionPriority.NORMAL,
        )

        recommendation = PolicyRecommendation()
        recommendation.recommended_actions.append(action)

        return await self.validate(recommendation)

    async def get_compliance_rules(self) -> list[dict]:
        """Get all compliance rules via MCP."""
        result = await self.mcp_client.call_tool("get_compliance_rules", {})
        if result.success:
            return result.data.get("rules", [])
        return []

    async def check_maintenance_window(self) -> bool:
        """Check if we're currently in maintenance window."""
        current_hour = datetime.utcnow().hour
        return self.checker.maintenance_window_start <= current_hour < self.checker.maintenance_window_end