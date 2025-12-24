"""
Execution Agent (with Audit Logging)

The Execution Agent that executes approved actions on the network with immutable audit logging via immudb.
"""

import json
import logging
import time
import re
import asyncio
from datetime import datetime
from typing import Any, Optional

from src.agents.base import BaseAgent, AgentResult
from src.agents.config import AgentConfig, config as default_config
from src.agents.llm import create_llm, BaseLLM
from src.agents.mcp_client import MCPClient
from src.agents.execution.models import (
    ExecutionResult,
    ActionExecution,
    ExecutionStatus,
    VerificationResult,
    VerificationStatus,
)
from src.agents.execution.prompts import (
    EXECUTION_AGENT_SYSTEM_PROMPT,
    VERIFICATION_PROMPT,
    ERROR_ANALYSIS_PROMPT,
)
from src.agents.compliance.models import (
    ComplianceResult,
    ActionValidation,
    ValidationStatus,
)

# Import audit logger
from src.audit.logger import AuditLogger

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Execution Agent that executes approved actions on the network.

    This agent:
    1. Receives ComplianceResult with approved actions
    2. Logs intent to immudb (before execution)
    3. Executes each approved action via MCP tools
    4. Verifies execution success
    5. Logs result to immudb (after execution)
    6. Handles failures with retry/rollback
    7. Produces ExecutionResult with full audit trail

    Example:
         agent = ExecutionAgent()
         compliance_result = await compliance_agent.validate(recommendation)
         result = await agent.execute(compliance_result. result)
         print(result.result. get_summary())
    """

    def __init__(
            self,
            config: Optional[AgentConfig] = None,
            llm: Optional[BaseLLM] = None,
            audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize the Execution Agent.

        Args:
            config: Agent configuration
            llm: LLM instance (creates one based on config if not provided)
            audit_logger: Audit logger instance (creates one if not provided)
        """
        super().__init__(name="execution", config=config)

        # Initialize LLM
        self.llm = llm or create_llm(self.config.llm)
        self.llm_available = self.llm.is_available()

        # Initialize MCP Client
        self.mcp_client = MCPClient()

        # Initialize Audit Logger
        self.audit = audit_logger or AuditLogger()
        self._audit_connected = False

        # Execution settings
        self.verify_after_execution = True
        self.retry_on_failure = True
        self.max_retries = 3
        self.retry_delay_seconds = 5

        if self.llm_available:
            logger.info(f"Execution Agent initialized with LLM: {self.llm.provider_name}")
        else:
            logger.warning("Execution Agent:  No LLM available for verification analysis")

        logger.info(f"Execution Agent has access to {len(self.mcp_client.get_available_tools())} MCP tools")

    def _ensure_audit_connected(self):
        """Ensure audit logger is connected."""
        if not self._audit_connected:
            self.audit.connect()
            self._audit_connected = True

    async def run(
            self,
            compliance_result: Optional[ComplianceResult] = None,
            verify: bool = True,
            dry_run: bool = False,
    ) -> AgentResult:
        """
        Run the Execution Agent.

        If no compliance_result is provided, runs the full pipeline first.

        Args:
            compliance_result: ComplianceResult from Compliance Agent
            verify: Whether to verify execution results
            dry_run: If True, simulate execution without actually executing

        Returns:
            AgentResult containing the ExecutionResult
        """
        # If no compliance result provided, run full pipeline
        if compliance_result is None:
            from src.agents.compliance import ComplianceAgent
            compliance_agent = ComplianceAgent()
            compliance_agent_result = await compliance_agent.run()
            if not compliance_agent_result.success:
                result = self._create_result()
                result.complete(error=f"Compliance check failed: {compliance_agent_result.error}")
                return result
            compliance_result = compliance_agent_result.result

        return await self.execute(compliance_result, verify, dry_run)

    async def execute(
            self,
            compliance_result: ComplianceResult,
            verify: bool = True,
            dry_run: bool = False,
    ) -> AgentResult:
        """
        Execute approved actions from a compliance result.

        Args:
            compliance_result: ComplianceResult with approved actions
            verify: Whether to verify execution results
            dry_run: If True, simulate execution

        Returns:
            AgentResult containing the ExecutionResult
        """
        result = self._create_result()
        start_time = time.time()
        tool_calls = 0

        # Ensure audit is connected
        self._ensure_audit_connected()

        try:
            self.logger.info(f"Executing actions from compliance result: {compliance_result.id}")

            # Get approved actions
            approved_validations = compliance_result.get_approved_actions()
            self.logger.info(f"Approved actions to execute: {len(approved_validations)}")

            # Create execution result
            execution_result = ExecutionResult(
                compliance_result_id=compliance_result.id,
                recommendation_id=compliance_result.recommendation_id,
                diagnosis_id=compliance_result.diagnosis_id,
            )

            # Handle no approved actions
            if not approved_validations:
                self.logger.info("No approved actions to execute")
                execution_result.summary = "No approved actions to execute"
                execution_result.total_duration_ms = int((time.time() - start_time) * 1000)
                result.complete(result=execution_result)
                self._record_execution(result)
                return result

            # Execute each approved action
            for validation in approved_validations:
                execution = await self._execute_single_action(
                    validation=validation,
                    verify=verify,
                    dry_run=dry_run,
                )
                tool_calls += execution.metadata.get("tool_calls", 1)
                execution_result.add_execution(execution)

            # Generate summary
            execution_result.summary = self._generate_summary(execution_result)
            execution_result.total_duration_ms = int((time.time() - start_time) * 1000)
            execution_result.tool_calls_made = tool_calls

            self.logger.info(
                f"Execution complete.  Success: {execution_result.success_count}/{execution_result.total_actions}")
            self.logger.info(execution_result.get_summary())

            result.complete(result=execution_result)

        except Exception as e:
            self.logger.error(f"Execution agent error: {e}")
            result.complete(error=str(e))

        self._record_execution(result)
        return result

    async def _execute_single_action(
            self,
            validation: ActionValidation,
            compliance_result: Optional[ComplianceResult] = None,
            verify: bool = True,
            dry_run: bool = False,
    ) -> ActionExecution:
        """Execute a single approved action."""

        # Create execution record
        execution = ActionExecution(
            action_id=validation.action_id,
            action_type=validation.action_type,
            target_node_id=validation.target_node_id,
            target_node_name=validation.target_node_name,
        )

        tool_calls = 0
        intent_record_id = ""

        try:
            # Step 0: Log intent to audit (before execution)
            self.logger.info(f"Logging intent:  {execution.action_type} on {execution.target_node_id}")

            if not dry_run:
                intent_result = self.audit.log_intent(
                    action_type=execution.action_type,
                    target_node_id=execution.target_node_id,
                    target_node_name=execution.target_node_name,
                    target_node_type=execution.target_node_type,
                    reason=execution.reason or "Automated remediation",
                    original_issue_type=execution.source_issue_type,
                    policy_ids=[execution.source_policy_id] if execution.source_policy_id else [],
                    compliance_status="approved",
                    approved_by=validation.approved_by,
                    diagnosis_id=compliance_result.diagnosis_id if compliance_result else "",
                    recommendation_id=compliance_result.recommendation_id if compliance_result else "",
                    compliance_id=compliance_result.id if compliance_result else "",
                    action_id=execution.action_id,
                    execution_id=execution.id,
                    agent_name="execution",
                )
                intent_record_id = intent_result.get("record_id", "")
                self.logger.info(f"Intent logged: {intent_record_id}")

            # Step 1: Pre-execution check - get current metrics
            self.logger.info(f"Executing:  {execution.action_type} on {execution.target_node_id}")

            metrics_before = {}
            if verify:
                metrics_result = await self.mcp_client.get_node_metrics(execution.target_node_id)
                tool_calls += 1
                if metrics_result.success:
                    nodes = metrics_result.data.get("nodes", [])
                    if nodes:
                        metrics_before = nodes[0].get("metrics", {})
                        execution.verification.metrics_before = metrics_before

            # Step 2: Execute (or simulate)
            execution.start()

            if dry_run:
                # Simulate execution
                self.logger.info(f"DRY RUN: Would execute {execution.action_type}")
                await asyncio.sleep(0.1)  # Simulate delay
                execution.complete_success(
                    message=f"DRY RUN: {execution.action_type} simulated successfully",
                    details={"dry_run": True}
                )
            else:
                # Actual execution via MCP
                exec_result = await self.mcp_client.execute_action(
                    action_type=execution.action_type,
                    target_node_id=execution.target_node_id,
                    reason=execution.reason or f"Automated execution from compliance {validation.id}",
                    parameters=execution.parameters,
                    policy_ids=[execution.source_policy_id] if execution.source_policy_id else [],
                )
                tool_calls += 1

                if exec_result.success:
                    exec_data = exec_result.data
                    execution.mcp_execution_id = exec_data.get("execution_id", "")

                    if exec_data.get("success", False):
                        execution.complete_success(
                            message=exec_data.get("result", {}).get("message", "Action executed successfully"),
                            details=exec_data.get("result", {})
                        )
                        execution.rollback_available = True
                    else:
                        execution.complete_failure(
                            error=exec_data.get("result", {}).get("message", "Action execution failed"),
                            details=exec_data.get("result", {})
                        )
                else:
                    execution.complete_failure(
                        error=exec_result.error or "MCP execution failed"
                    )

            # Step 3: Verify execution if requested and successful
            if verify and execution.success and not dry_run:
                await self._verify_execution(execution, metrics_before)
                tool_calls += 1

            # Step 4: Handle failure with retry
            if not execution.success and self.retry_on_failure and not dry_run:
                execution = await self._retry_execution(execution, validation)
                tool_calls += execution.retry_count

            # Step 5: Log result to audit (after execution)
            if not dry_run:
                self.audit.log_result(
                    action_type=execution.action_type,
                    target_node_id=execution.target_node_id,
                    target_node_name=execution.target_node_name,
                    success=execution.success,
                    status=execution.status. value,
                    result_message=execution. result_message,
                    error_message=execution. error_message,
                    started_at=execution. started_at,
                    completed_at=execution.completed_at,
                    duration_ms=execution. duration_ms,
                    retry_count=execution. retry_count,
                    verified=execution.verification.status != VerificationStatus. NOT_VERIFIED,
                    verification_status=execution.verification. status.value,
                    metrics_before=execution. verification.metrics_before,
                    metrics_after=execution. verification.metrics_after,
                    improvement_detected=execution.verification.improvement_detected,
                    intent_record_id=intent_record_id,
                    diagnosis_id=compliance_result.diagnosis_id if compliance_result else "",
                    recommendation_id=compliance_result.recommendation_id if compliance_result else "",
                    compliance_id=compliance_result.id if compliance_result else "",
                    action_id=execution.action_id,
                    execution_id=execution.id,
                    agent_name="execution",
                )
                self.logger.info(f"Result logged for execution:  {execution.id}")

        except Exception as e:
            self.logger.error(f"Error executing action: {e}")
            execution.complete_failure(error=str(e))

            # Log failure to audit
            if not dry_run:
                self.audit.log_result(
                    action_type=execution.action_type,
                    target_node_id=execution.target_node_id,
                    success=False,
                    status="failed",
                    error_message=str(e),
                    intent_record_id=intent_record_id,
                    execution_id=execution. id,
                    agent_name="execution",
                )

        execution.metadata["tool_calls"] = tool_calls
        execution.metadata["intent_record_id"] = intent_record_id
        return execution

    async def _verify_execution(
            self,
            execution: ActionExecution,
            metrics_before: dict,
    ) -> None:
        """Verify that execution had the intended effect."""

        self.logger.info(f"Verifying execution: {execution.id}")

        try:
            # Wait a moment for changes to take effect
            await asyncio.sleep(1)

            # Get metrics after execution
            metrics_result = await self.mcp_client.get_node_metrics(execution.target_node_id)

            if not metrics_result.success:
                execution.verification.status = VerificationStatus.VERIFICATION_ERROR
                execution.verification.issues_found.append("Could not retrieve post-execution metrics")
                return

            nodes = metrics_result.data.get("nodes", [])
            metrics_after = {}
            if nodes:
                metrics_after = nodes[0].get("metrics", {})

            execution.verification.metrics_after = metrics_after
            execution.verification.verified_at = datetime.utcnow()
            execution.verification.checks_performed = ["metrics_comparison"]

            # Analyze improvement based on action type
            improvement = self._analyze_improvement(
                execution.action_type,
                metrics_before,
                metrics_after,
            )

            if improvement["improved"]:
                execution.verification.status = VerificationStatus.VERIFIED_SUCCESS
                execution.verification.improvement_detected = True
                execution.verification.improvement_details = improvement["details"]
            else:
                execution.verification.status = VerificationStatus.VERIFIED_FAILED
                execution.verification.improvement_detected = False
                execution.verification.improvement_details = improvement["details"]
                execution.verification.issues_found.append(improvement["details"])

        except Exception as e:
            self.logger.error(f"Verification error: {e}")
            execution.verification.status = VerificationStatus.VERIFICATION_ERROR
            execution.verification.issues_found.append(str(e))

    def _analyze_improvement(
            self,
            action_type: str,
            metrics_before: dict,
            metrics_after: dict,
    ) -> dict:
        """Analyze if metrics improved after action."""

        # Map action types to relevant metrics
        action_metrics = {
            "restart_service": ["cpu_utilization", "memory_utilization", "error_count"],
            "restart_node": ["cpu_utilization", "memory_utilization", "error_count"],
            "clear_cache": ["memory_utilization"],
            "rate_limit": ["bandwidth_in", "bandwidth_out", "cpu_utilization"],
            "scale_up": ["cpu_utilization", "memory_utilization", "latency"],
            "scale_down": ["cpu_utilization", "memory_utilization"],
        }

        relevant_metrics = action_metrics.get(action_type, ["cpu_utilization"])

        improvements = []
        regressions = []

        for metric in relevant_metrics:
            before_data = metrics_before.get(metric, {})
            after_data = metrics_after.get(metric, {})

            before_value = before_data.get("value")
            after_value = after_data.get("value")

            if before_value is not None and after_value is not None:
                # For most metrics, lower is better
                if metric in ["cpu_utilization", "memory_utilization", "latency", "error_count", "packet_loss"]:
                    if after_value < before_value:
                        improvements.append(f"{metric}:  {before_value} → {after_value} (improved)")
                    elif after_value > before_value:
                        regressions.append(f"{metric}: {before_value} → {after_value} (regressed)")
                else:
                    # For throughput metrics, higher might be better or just different
                    improvements.append(f"{metric}: {before_value} → {after_value}")

        if improvements and not regressions:
            return {
                "improved": True,
                "details": f"Metrics improved: {'; '.join(improvements)}"
            }
        elif regressions:
            return {
                "improved": False,
                "details": f"Metrics regressed: {'; '.join(regressions)}"
            }
        else:
            return {
                "improved": True,  # No regression is good
                "details": "No significant metric changes detected"
            }

    async def _retry_execution(
            self,
            execution: ActionExecution,
            validation: ActionValidation,
            compliance_result: Optional[ComplianceResult] = None,
    ) -> ActionExecution:
        """Retry a failed execution."""

        while execution.can_retry():
            execution.retry_count += 1
            self.logger.info(f"Retrying execution {execution.id} (attempt {execution.retry_count})")

            # Wait before retry
            await asyncio.sleep(self.retry_delay_seconds)

            # Reset status
            execution.status = ExecutionStatus.PENDING
            execution.error_message = ""

            # Retry execution
            exec_result = await self.mcp_client.execute_action(
                action_type=execution.action_type,
                target_node_id=execution.target_node_id,
                reason=f"Retry #{execution.retry_count}:  {execution.reason}",
                parameters=execution.parameters,
            )

            if exec_result.success and exec_result.data.get("success", False):
                execution.complete_success(
                    message=f"Succeeded on retry #{execution.retry_count}",
                    details=exec_result.data.get("result", {})
                )
                break
            else:
                execution.complete_failure(
                    error=exec_result.error or "Retry failed"
                )

        return execution

    def _generate_summary(self, execution_result: ExecutionResult) -> str:
        """Generate execution summary."""

        if execution_result.all_successful:
            return f"All {execution_result.total_actions} actions executed successfully"
        elif execution_result.has_failures:
            return (
                f"Execution completed with failures: "
                f"{execution_result.success_count} succeeded, "
                f"{execution_result.failed_count} failed, "
                f"{execution_result.skipped_count} skipped"
            )
        else:
            return f"Execution completed:  {execution_result.success_count}/{execution_result.total_actions} successful"

    # =========================================================================
    # Convenience methods
    # =========================================================================

    async def execute_single_action(
            self,
            action_type: str,
            target_node_id: str,
            reason: str = "",
            parameters: dict = None,
            verify: bool = True,
            dry_run: bool = False,
    ) -> AgentResult:
        """Execute a single action directly (bypasses compliance check)."""

        result = self._create_result()

        try:
            # Create a mock validation
            validation = ActionValidation(
                action_type=action_type,
                target_node_id=target_node_id,
                status=ValidationStatus.APPROVED,
            )

            # Execute
            execution = await self._execute_single_action(
                validation=validation,
                verify=verify,
                dry_run=dry_run,
            )
            execution.reason = reason
            execution.parameters = parameters or {}

            # Create result
            execution_result = ExecutionResult()
            execution_result.add_execution(execution)
            execution_result.summary = f"Single action: {execution.status.value}"

            result.complete(result=execution_result)

        except Exception as e:
            result.complete(error=str(e))

        return result

    async def get_execution_history(self, limit: int = 50) -> list[dict]:
        """Get execution history via MCP."""
        result = await self.mcp_client.call_tool("get_execution_history", {"limit": limit})
        if result.success:
            return result.data.get("executions", [])
        return []

    async def get_execution_status(self, execution_id: str) -> Optional[dict]:
        """Get status of a specific execution."""
        result = await self.mcp_client.call_tool("get_execution_status", {"execution_id": execution_id})
        if result.success:
            return result.data
        return None

    def get_audit_stats(self) -> dict:
        """Get audit statistics."""
        self._ensure_audit_connected()
        return self.audit.get_stats()