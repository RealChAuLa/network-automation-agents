"""Tests for the Execution Agent."""

import pytest
from datetime import datetime

from src.agents.execution.agent import ExecutionAgent
from src.agents.execution.models import (
    ExecutionResult,
    ActionExecution,
    ExecutionStatus,
    VerificationResult,
    VerificationStatus,
)
from src.agents.compliance.models import (
    ComplianceResult,
    ActionValidation,
    ValidationStatus,
)


class TestActionExecution:
    """Test cases for ActionExecution model."""

    def test_create_execution(self):
        """Test creating an action execution."""
        execution = ActionExecution(
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
        )

        assert execution.action_type == "restart_service"
        assert execution.status == ExecutionStatus.PENDING
        assert execution.id.startswith("exec_")

    def test_start_execution(self):
        """Test starting an execution."""
        execution = ActionExecution()
        execution.start()

        assert execution.status == ExecutionStatus.IN_PROGRESS
        assert execution.started_at is not None

    def test_complete_success(self):
        """Test completing execution successfully."""
        execution = ActionExecution()
        execution.start()
        execution.complete_success(
            message="Action completed",
            details={"key": "value"}
        )

        assert execution.status == ExecutionStatus.SUCCESS
        assert execution.success is True
        assert execution.result_message == "Action completed"
        assert execution.completed_at is not None
        assert execution.duration_ms is not None

    def test_complete_failure(self):
        """Test completing execution with failure."""
        execution = ActionExecution()
        execution.start()
        execution.complete_failure(
            error="Something went wrong",
            details={"error_code": 500}
        )

        assert execution.status == ExecutionStatus.FAILED
        assert execution.success is False
        assert execution.error_message == "Something went wrong"

    def test_can_retry(self):
        """Test retry eligibility."""
        execution = ActionExecution(max_retries=3)
        execution.complete_failure(error="Error")

        assert execution.can_retry() is True

        # Exhaust retries
        execution.retry_count = 3
        assert execution.can_retry() is False

    def test_mark_skipped(self):
        """Test marking execution as skipped."""
        execution = ActionExecution()
        execution.mark_skipped("Not needed")

        assert execution.status == ExecutionStatus.SKIPPED
        assert execution.result_message == "Not needed"

    def test_mark_rolled_back(self):
        """Test marking execution as rolled back."""
        execution = ActionExecution()
        execution.mark_rolled_back("Rolled back successfully")

        assert execution.status == ExecutionStatus.ROLLED_BACK
        assert execution.rollback_executed is True

    def test_to_dict(self):
        """Test converting execution to dictionary."""
        execution = ActionExecution(
            action_type="restart_service",
            target_node_id="node_01",
            status=ExecutionStatus.SUCCESS,
        )

        data = execution.to_dict()

        assert data["action_type"] == "restart_service"
        assert data["status"] == "success"


class TestVerificationResult:
    """Test cases for VerificationResult model."""

    def test_create_verification(self):
        """Test creating a verification result."""
        verification = VerificationResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            improvement_detected=True,
            improvement_details="CPU reduced from 95% to 30%",
        )

        assert verification.status == VerificationStatus.VERIFIED_SUCCESS
        assert verification.improvement_detected is True

    def test_verification_to_dict(self):
        """Test converting verification to dictionary."""
        verification = VerificationResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            checks_performed=["metrics_comparison"],
            improvement_detected=True,
        )

        data = verification.to_dict()

        assert data["status"] == "verified_success"
        assert data["improvement_detected"] is True
        assert "metrics_comparison" in data["checks_performed"]


class TestExecutionResult:
    """Test cases for ExecutionResult model."""

    def test_create_result(self):
        """Test creating an execution result."""
        result = ExecutionResult(
            compliance_result_id="comp_123",
            recommendation_id="rec_456",
        )

        assert result.compliance_result_id == "comp_123"
        assert result.id.startswith("result_")
        assert result.total_actions == 0

    def test_add_execution_updates_counts(self):
        """Test that adding executions updates counts."""
        result = ExecutionResult()

        # Add successful execution
        e1 = ActionExecution(status=ExecutionStatus.SUCCESS)
        e1.success = True
        result.add_execution(e1)

        # Add failed execution
        e2 = ActionExecution(status=ExecutionStatus.FAILED)
        result.add_execution(e2)

        # Add skipped execution
        e3 = ActionExecution(status=ExecutionStatus.SKIPPED)
        result.add_execution(e3)

        assert result.total_actions == 3
        assert result.success_count == 1
        assert result.failed_count == 1
        assert result.skipped_count == 1
        assert result.all_successful is False
        assert result.has_failures is True

    def test_all_successful(self):
        """Test all_successful flag."""
        result = ExecutionResult()

        e1 = ActionExecution(status=ExecutionStatus.SUCCESS)
        e1.success = True
        e2 = ActionExecution(status=ExecutionStatus.SUCCESS)
        e2.success = True

        result.add_execution(e1)
        result.add_execution(e2)

        assert result.all_successful is True
        assert result.has_failures is False

    def test_get_successful_executions(self):
        """Test getting successful executions."""
        result = ExecutionResult()

        e1 = ActionExecution(action_type="action1", status=ExecutionStatus.SUCCESS)
        e2 = ActionExecution(action_type="action2", status=ExecutionStatus.FAILED)
        e3 = ActionExecution(action_type="action3", status=ExecutionStatus.SUCCESS)

        result.add_execution(e1)
        result.add_execution(e2)
        result.add_execution(e3)

        successful = result.get_successful_executions()

        assert len(successful) == 2
        assert all(e.status == ExecutionStatus.SUCCESS for e in successful)

    def test_get_failed_executions(self):
        """Test getting failed executions."""
        result = ExecutionResult()

        e1 = ActionExecution(action_type="action1", status=ExecutionStatus.SUCCESS)
        e2 = ActionExecution(action_type="action2", status=ExecutionStatus.FAILED)

        result.add_execution(e1)
        result.add_execution(e2)

        failed = result.get_failed_executions()

        assert len(failed) == 1
        assert failed[0].action_type == "action2"

    def test_get_summary(self):
        """Test getting result summary."""
        result = ExecutionResult(
            compliance_result_id="comp_123",
        )

        e1 = ActionExecution(status=ExecutionStatus.SUCCESS)
        e1.success = True
        result.add_execution(e1)

        summary = result.get_summary()

        assert "ALL SUCCESSFUL" in summary
        assert "Successful:  1" in summary


class TestExecutionAgent:
    """Test cases for ExecutionAgent."""

    @pytest.fixture
    def agent(self):
        """Create execution agent."""
        return ExecutionAgent()

    @pytest.fixture
    def sample_compliance_result(self):
        """Create a sample compliance result with approved actions."""
        result = ComplianceResult(
            recommendation_id="rec_123",
            diagnosis_id="diag_456",
        )

        validation = ActionValidation(
            action_id="action_001",
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
            status=ValidationStatus.APPROVED,
        )
        validation.approved_by = "system"

        result.add_validation(validation)

        return result

    @pytest.mark.asyncio
    async def test_execute_returns_result(self, agent, sample_compliance_result):
        """Test that execute returns an AgentResult."""
        result = await agent.execute(sample_compliance_result, verify=False, dry_run=True)

        assert result is not None
        assert result.agent_name == "execution"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_creates_execution_result(self, agent, sample_compliance_result):
        """Test that execute creates an ExecutionResult."""
        result = await agent.execute(sample_compliance_result, verify=False, dry_run=True)

        execution_result = result.result
        assert isinstance(execution_result, ExecutionResult)
        assert execution_result.compliance_result_id == sample_compliance_result.id
        assert execution_result.total_actions == 1

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, agent, sample_compliance_result):
        """Test dry run execution."""
        result = await agent.execute(sample_compliance_result, verify=False, dry_run=True)

        execution_result = result.result
        assert execution_result.all_successful is True

        # Check that it was a dry run
        for execution in execution_result.executions:
            assert "DRY RUN" in execution.result_message

    @pytest.mark.asyncio
    async def test_execute_no_approved_actions(self, agent):
        """Test execution with no approved actions."""
        compliance_result = ComplianceResult()
        # No approved validations

        result = await agent.execute(compliance_result, verify=False)

        assert result.success is True
        assert result.result.total_actions == 0
        assert "No approved actions" in result.result.summary

    @pytest.mark.asyncio
    async def test_execute_single_action(self, agent):
        """Test executing a single action directly."""
        result = await agent.execute_single_action(
            action_type="restart_service",
            target_node_id="router_core_01",
            reason="Test execution",
            verify=False,
            dry_run=True,
        )

        assert result.success is True
        assert result.result.total_actions == 1

    @pytest.mark.asyncio
    async def test_get_execution_history(self, agent):
        """Test getting execution history."""
        history = await agent.get_execution_history(limit=10)

        assert isinstance(history, list)

    def test_analyze_improvement_cpu(self, agent):
        """Test improvement analysis for CPU."""
        metrics_before = {"cpu_utilization": {"value": 95}}
        metrics_after = {"cpu_utilization": {"value": 30}}

        result = agent._analyze_improvement("restart_service", metrics_before, metrics_after)

        assert result["improved"] is True
        assert "improved" in result["details"].lower()

    def test_analyze_improvement_no_change(self, agent):
        """Test improvement analysis with no change."""
        metrics_before = {"cpu_utilization": {"value": 50}}
        metrics_after = {"cpu_utilization": {"value": 50}}

        result = agent._analyze_improvement("restart_service", metrics_before, metrics_after)

        # No change is considered "improved" (no regression)
        assert result["improved"] is True

    def test_analyze_improvement_regression(self, agent):
        """Test improvement analysis with regression."""
        metrics_before = {"cpu_utilization": {"value": 50}}
        metrics_after = {"cpu_utilization": {"value": 80}}

        result = agent._analyze_improvement("restart_service", metrics_before, metrics_after)

        assert result["improved"] is False
        assert "regressed" in result["details"].lower()


class TestIntegration:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dry_run(self):
        """Test the full agent pipeline with dry run."""
        from src.agents.discovery import DiscoveryAgent
        from src.agents.policy import PolicyAgent
        from src.agents.compliance import ComplianceAgent

        # Run discovery
        discovery = DiscoveryAgent()
        discovery_result = await discovery.run(use_llm=False)
        assert discovery_result.success is True

        # Run policy
        policy = PolicyAgent()
        policy_result = await policy.evaluate(discovery_result.result, use_llm=False)
        assert policy_result.success is True

        # Run compliance
        compliance = ComplianceAgent()
        compliance_result = await compliance.validate(policy_result.result, use_llm=False)
        assert compliance_result.success is True

        # Run execution (dry run)
        execution = ExecutionAgent()
        execution_result = await execution.execute(
            compliance_result.result,
            verify=False,
            dry_run=True,
        )
        assert execution_result.success is True

        # Verify the chain
        result = execution_result.result
        assert result.compliance_result_id == compliance_result.result.id

    @pytest.mark.asyncio
    async def test_execution_with_verification_dry_run(self):
        """Test execution with verification in dry run mode."""
        agent = ExecutionAgent()

        result = await agent.execute_single_action(
            action_type="restart_service",
            target_node_id="router_core_01",
            reason="Test with verification",
            verify=True,
            dry_run=True,
        )

        assert result.success is True
        # In dry run, verification is skipped
        execution = result.result.executions[0]
        assert execution.status == ExecutionStatus.SUCCESS