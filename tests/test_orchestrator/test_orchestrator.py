"""Tests for the Orchestrator."""

import pytest
from datetime import datetime

from src.orchestrator.models import (
    PipelineRun,
    PipelineStatus,
    PipelineConfig,
    StepResult,
    StepStatus,
    OrchestratorStatus,
)
from src.orchestrator.pipeline import Pipeline
from src.orchestrator.scheduler import Scheduler
from src.orchestrator.orchestrator import Orchestrator


class TestStepResult:
    """Test cases for StepResult model."""

    def test_create_step(self):
        """Test creating a step result."""
        step = StepResult(step_name="discovery")

        assert step.step_name == "discovery"
        assert step.status == StepStatus.PENDING

    def test_start_step(self):
        """Test starting a step."""
        step = StepResult(step_name="discovery")
        step.start()

        assert step.status == StepStatus.RUNNING
        assert step.started_at is not None

    def test_complete_success(self):
        """Test completing a step successfully."""
        step = StepResult(step_name="discovery")
        step.start()
        step.complete_success(items_processed=10, items_passed=3)

        assert step.status == StepStatus.SUCCESS
        assert step.items_processed == 10
        assert step.items_passed == 3
        assert step.duration_ms is not None

    def test_complete_failure(self):
        """Test completing a step with failure."""
        step = StepResult(step_name="discovery")
        step.start()
        step.complete_failure(error="Something went wrong")

        assert step.status == StepStatus.FAILED
        assert step.error == "Something went wrong"

    def test_skip_step(self):
        """Test skipping a step."""
        step = StepResult(step_name="execution")
        step.skip("Not needed")

        assert step.status == StepStatus.SKIPPED


class TestPipelineRun:
    """Test cases for PipelineRun model."""

    def test_create_run(self):
        """Test creating a pipeline run."""
        run = PipelineRun()

        assert run.id.startswith("run_")
        assert run.status == PipelineStatus.PENDING

    def test_add_step(self):
        """Test adding steps to a run."""
        run = PipelineRun()
        step = run.add_step("discovery")

        assert "discovery" in run.steps
        assert step.step_name == "discovery"

    def test_start_run(self):
        """Test starting a run."""
        run = PipelineRun()
        run.start()

        assert run.status == PipelineStatus.RUNNING
        assert run.started_at is not None

    def test_complete_all_success(self):
        """Test completing a run with all steps successful."""
        run = PipelineRun()
        run.start()

        step1 = run.add_step("discovery")
        step1.status = StepStatus.SUCCESS

        step2 = run.add_step("policy")
        step2.status = StepStatus.SUCCESS

        run.complete()

        assert run.status == PipelineStatus.SUCCESS
        assert run.completed_at is not None

    def test_complete_with_failure(self):
        """Test completing a run with a failed step."""
        run = PipelineRun()
        run.start()

        step1 = run.add_step("discovery")
        step1.status = StepStatus.SUCCESS

        step2 = run.add_step("policy")
        step2.status = StepStatus.FAILED

        run.complete()

        assert run.status == PipelineStatus.PARTIAL

    def test_cancel_run(self):
        """Test cancelling a run."""
        run = PipelineRun()
        run.start()
        run.cancel("User requested")

        assert run.status == PipelineStatus.CANCELLED
        assert "User requested" in run.summary

    def test_get_summary(self):
        """Test getting run summary."""
        run = PipelineRun()
        run.status = PipelineStatus.SUCCESS
        run.issues_found = 3
        run.actions_executed = 2
        run.actions_successful = 2
        summary = run.get_summary()

        assert "SUCCESS" in summary
        assert "3" in summary  # issues found
        assert "2/2" in summary  # actions


class TestPipelineConfig:
    """Test cases for PipelineConfig model."""

    def test_create_config(self):
        """Test creating a pipeline config."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
        )

        assert config.use_llm is False
        assert config.dry_run is True
        assert config.verify_execution is True  # default

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = PipelineConfig(
            use_llm=True,
            skip_execution=True,
        )

        data = config.to_dict()

        assert data["use_llm"] is True
        assert data["skip_execution"] is True


class TestScheduler:
    """Test cases for Scheduler."""

    def test_create_scheduler(self):
        """Test creating a scheduler."""
        scheduler = Scheduler(interval_minutes=5)

        assert scheduler.interval_minutes == 5
        assert scheduler.is_running() is False

    def test_set_interval(self):
        """Test setting interval."""
        scheduler = Scheduler(interval_minutes=5)
        scheduler.set_interval(10)

        assert scheduler.interval_minutes == 10
        assert scheduler.interval_seconds == 600

    def test_pause_resume(self):
        """Test pausing and resuming."""
        scheduler = Scheduler()

        scheduler.pause()
        assert scheduler.is_paused() is True

        scheduler.resume()
        assert scheduler.is_paused() is False

    def test_get_status(self):
        """Test getting scheduler status."""
        scheduler = Scheduler(interval_minutes=5)

        status = scheduler.get_status()

        assert status["running"] is False
        assert status["interval_minutes"] == 5


class TestPipeline:
    """Test cases for Pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create a pipeline."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
        )
        return Pipeline(config=config)

    @pytest.mark.asyncio
    async def test_execute_pipeline(self, pipeline):
        """Test executing the pipeline."""
        run = await pipeline.execute(trigger="test")

        assert run is not None
        assert run.id.startswith("run_")
        assert run.trigger == "test"
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_with_skip_execution(self):
        """Test executing with skip_execution."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
            skip_execution=True,
        )
        pipeline = Pipeline(config=config)

        run = await pipeline.execute()

        assert run is not None
        if "execution" in run.steps:
            assert run.steps["execution"].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_execute_dry_run(self):
        """Test executing in dry run mode."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
        )
        pipeline = Pipeline(config=config)

        run = await pipeline.execute()

        assert run is not None
        assert run.config["dry_run"] is True


class TestOrchestrator:
    """Test cases for Orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
        )
        return Orchestrator(
            interval_minutes=1,
            config=config,
        )

    def test_create_orchestrator(self, orchestrator):
        """Test creating an orchestrator."""
        assert orchestrator.interval_minutes == 1
        assert orchestrator.config.dry_run is True

    @pytest.mark.asyncio
    async def test_run_now(self, orchestrator):
        """Test running pipeline immediately."""
        run = await orchestrator.run_now(trigger="test")

        assert run is not None
        assert run.trigger == "test"

    def test_get_status(self, orchestrator):
        """Test getting orchestrator status."""
        status = orchestrator.get_status()

        assert isinstance(status, OrchestratorStatus)
        assert status.running is False
        assert status.total_runs == 0

    @pytest.mark.asyncio
    async def test_run_updates_statistics(self, orchestrator):
        """Test that running updates statistics."""
        await orchestrator.run_now()

        stats = orchestrator.get_statistics()

        assert stats["total_runs"] == 1

    @pytest.mark.asyncio
    async def test_run_history(self, orchestrator):
        """Test run history tracking."""
        await orchestrator.run_now()
        await orchestrator.run_now()

        history = orchestrator.get_run_history(limit=10)

        assert len(history) == 2

    def test_set_interval(self, orchestrator):
        """Test setting interval."""
        orchestrator.set_interval(10)

        assert orchestrator.interval_minutes == 10

    def test_get_last_run(self, orchestrator):
        """Test getting last run when no runs exist."""
        last = orchestrator.get_last_run()

        assert last is None

    @pytest.mark.asyncio
    async def test_get_last_run_after_run(self, orchestrator):
        """Test getting last run after a run."""
        await orchestrator.run_now()

        last = orchestrator.get_last_run()

        assert last is not None
        assert last.id.startswith("run_")

    def test_pause_resume(self, orchestrator):
        """Test pausing and resuming."""
        orchestrator.pause()
        status = orchestrator.get_status()
        assert status.paused is True

        orchestrator.resume()
        status = orchestrator.get_status()
        assert status.paused is False


class TestIntegration:
    """Integration tests for the full orchestrator flow."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dry_run(self):
        """Test running the full pipeline in dry run mode."""
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
            verify_execution=False,
        )

        orchestrator = Orchestrator(config=config)
        run = await orchestrator.run_now()

        assert run is not None
        assert run.status in [
            PipelineStatus.SUCCESS,
            PipelineStatus.PARTIAL,
            PipelineStatus.SKIPPED,
        ]

        # Check steps were executed
        assert "discovery" in run.steps

    @pytest.mark.asyncio
    async def test_pipeline_with_injected_anomaly(self):
        """Test pipeline detects and handles injected anomaly."""
        from src.agents.mcp_client import MCPClient

        # Inject an anomaly
        mcp = MCPClient()
        await mcp.inject_test_anomaly(
            node_id="router_core_01",
            anomaly_type="HIGH_CPU",
            severity="critical",
        )

        # Run pipeline
        config = PipelineConfig(
            use_llm=False,
            dry_run=True,
        )

        orchestrator = Orchestrator(config=config)
        run = await orchestrator.run_now()

        # Should find the issue
        assert run.issues_found >= 1

        # Clean up
        await mcp.clear_anomaly()