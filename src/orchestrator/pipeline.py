"""
Pipeline Executor (LangGraph-based)

Executes the full agent pipeline using LangGraph:
Discovery → Policy → Compliance → Execution
"""

import logging
from datetime import datetime
from typing import TypedDict, Optional, Annotated
import operator

from langgraph.graph import StateGraph, END

from src.orchestrator.models import (
    PipelineRun,
    PipelineConfig,
    PipelineStatus,
    StepResult,
    StepStatus,
)
from src.agents.discovery import DiscoveryAgent
from src.agents.discovery.models import DiagnosisReport
from src.agents.policy import PolicyAgent
from src.agents.policy.models import PolicyRecommendation
from src.agents.compliance import ComplianceAgent
from src.agents.compliance.models import ComplianceResult
from src.agents.execution import ExecutionAgent
from src.agents.execution.models import ExecutionResult
from src.audit.logger import AuditLogger
from src.audit.models import AuditRecord, AuditRecordType

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class PipelineState(TypedDict):
    """State that flows through the pipeline graph."""

    # Run metadata
    run_id: str
    trigger: str
    triggered_by: str

    # Configuration
    config: dict
    use_llm: bool
    dry_run: bool
    verify_execution: bool

    # Step results
    diagnosis: Optional[DiagnosisReport]
    recommendation: Optional[PolicyRecommendation]
    compliance_result: Optional[ComplianceResult]
    execution_result: Optional[ExecutionResult]

    # Step tracking
    steps: dict
    current_step: str

    # Counts
    issues_found: int
    actions_recommended: int
    actions_approved: int
    actions_executed: int
    actions_successful: int

    # Status
    status: str
    error: Optional[str]
    should_continue: bool

    # Timing
    started_at: str
    completed_at: Optional[str]


# =============================================================================
# Node Functions (Agent Steps)
# =============================================================================

async def discovery_node(state: PipelineState) -> PipelineState:
    """Discovery Agent node - detects network issues."""

    logger.info("🔍 Step 1: Running Discovery Agent...")

    step = StepResult(step_name="discovery")
    step.start()

    try:
        agent = DiscoveryAgent()
        result = await agent.run(use_llm=state["use_llm"])

        if result.success:
            diagnosis = result.result
            step.complete_success(
                result=diagnosis,
                items_processed=diagnosis.nodes_analyzed,
                items_passed=len(diagnosis.issues),
            )

            logger.info(f"✓ Discovery complete:  {len(diagnosis.issues)} issues found")

            return {
                **state,
                "diagnosis": diagnosis,
                "issues_found": len(diagnosis.issues),
                "steps": {**state["steps"], "discovery": step.to_dict()},
                "current_step": "discovery",
                "should_continue": len(diagnosis.issues) > 0,
            }
        else:
            step.complete_failure(error=result.error)
            logger.error(f"✗ Discovery failed: {result.error}")

            return {
                **state,
                "steps": {**state["steps"], "discovery": step.to_dict()},
                "current_step": "discovery",
                "should_continue": False,
                "error": result.error,
                "status": "failed",
            }

    except Exception as e:
        step.complete_failure(error=str(e))
        logger.error(f"✗ Discovery error: {e}")

        return {
            **state,
            "steps": {**state["steps"], "discovery": step.to_dict()},
            "should_continue": False,
            "error": str(e),
            "status": "failed",
        }


async def policy_node(state: PipelineState) -> PipelineState:
    """Policy Agent node - evaluates policies and recommends actions."""

    logger.info("📋 Step 2: Running Policy Agent...")

    step = StepResult(step_name="policy")
    step.start()

    try:
        diagnosis = state["diagnosis"]

        agent = PolicyAgent()
        result = await agent.evaluate(diagnosis, use_llm=state["use_llm"])

        if result.success:
            recommendation = result.result
            step.complete_success(
                result=recommendation,
                items_processed=recommendation.issues_evaluated,
                items_passed=len(recommendation.recommended_actions),
            )

            logger.info(f"✓ Policy complete: {len(recommendation.recommended_actions)} actions recommended")

            return {
                **state,
                "recommendation": recommendation,
                "actions_recommended": len(recommendation.recommended_actions),
                "steps": {**state["steps"], "policy": step.to_dict()},
                "current_step": "policy",
                "should_continue": len(recommendation.recommended_actions) > 0,
            }
        else:
            step.complete_failure(error=result.error)
            logger.error(f"✗ Policy failed: {result.error}")

            return {
                **state,
                "steps": {**state["steps"], "policy": step.to_dict()},
                "current_step": "policy",
                "should_continue": False,
                "error": result.error,
                "status": "failed",
            }

    except Exception as e:
        step.complete_failure(error=str(e))
        logger.error(f"✗ Policy error: {e}")

        return {
            **state,
            "steps": {**state["steps"], "policy": step.to_dict()},
            "should_continue": False,
            "error": str(e),
            "status": "failed",
        }


async def compliance_node(state: PipelineState) -> PipelineState:
    """Compliance Agent node - validates actions against rules."""

    logger.info("✅ Step 3: Running Compliance Agent...")

    step = StepResult(step_name="compliance")
    step.start()

    try:
        recommendation = state["recommendation"]

        agent = ComplianceAgent()
        result = await agent.validate(recommendation, use_llm=state["use_llm"])

        if result.success:
            compliance_result = result.result
            step.complete_success(
                result=compliance_result,
                items_processed=compliance_result.total_actions,
                items_passed=compliance_result.approved_count,
            )
            step.items_failed = compliance_result.denied_count

            logger.info(
                f"✓ Compliance complete: {compliance_result.approved_count}/{compliance_result.total_actions} approved")

            return {
                **state,
                "compliance_result": compliance_result,
                "actions_approved": compliance_result.approved_count,
                "steps": {**state["steps"], "compliance": step.to_dict()},
                "current_step": "compliance",
                "should_continue": compliance_result.approved_count > 0,
            }
        else:
            step.complete_failure(error=result.error)
            logger.error(f"✗ Compliance failed: {result.error}")

            return {
                **state,
                "steps": {**state["steps"], "compliance": step.to_dict()},
                "current_step": "compliance",
                "should_continue": False,
                "error": result.error,
                "status": "failed",
            }

    except Exception as e:
        step.complete_failure(error=str(e))
        logger.error(f"✗ Compliance error:  {e}")

        return {
            **state,
            "steps": {**state["steps"], "compliance": step.to_dict()},
            "should_continue": False,
            "error": str(e),
            "status": "failed",
        }


async def execution_node(state: PipelineState) -> PipelineState:
    """Execution Agent node - executes approved actions."""

    logger.info("🚀 Step 4: Running Execution Agent...")

    step = StepResult(step_name="execution")
    step.start()

    try:
        compliance_result = state["compliance_result"]

        agent = ExecutionAgent()
        result = await agent.execute(
            compliance_result,
            verify=state["verify_execution"],
            dry_run=state["dry_run"],
        )

        if result.success:
            execution_result = result.result
            step.complete_success(
                result=execution_result,
                items_processed=execution_result.total_actions,
                items_passed=execution_result.success_count,
            )
            step.items_failed = execution_result.failed_count

            logger.info(
                f"✓ Execution complete: {execution_result.success_count}/{execution_result.total_actions} successful")

            return {
                **state,
                "execution_result": execution_result,
                "actions_executed": execution_result.total_actions,
                "actions_successful": execution_result.success_count,
                "steps": {**state["steps"], "execution": step.to_dict()},
                "current_step": "execution",
                "status": "success" if execution_result.all_successful else "partial",
            }
        else:
            step.complete_failure(error=result.error)
            logger.error(f"✗ Execution failed: {result.error}")

            return {
                **state,
                "steps": {**state["steps"], "execution": step.to_dict()},
                "current_step": "execution",
                "error": result.error,
                "status": "failed",
            }

    except Exception as e:
        step.complete_failure(error=str(e))
        logger.error(f"✗ Execution error: {e}")

        return {
            **state,
            "steps": {**state["steps"], "execution": step.to_dict()},
            "error": str(e),
            "status": "failed",
        }


# =============================================================================
# Routing Functions
# =============================================================================

def should_continue_to_policy(state: PipelineState) -> str:
    """Decide whether to continue to policy or end."""
    if state["should_continue"] and state.get("diagnosis"):
        return "policy"
    return "end"


def should_continue_to_compliance(state: PipelineState) -> str:
    """Decide whether to continue to compliance or end."""
    if state["should_continue"] and state.get("recommendation"):
        return "compliance"
    return "end"


def should_continue_to_execution(state: PipelineState) -> str:
    """Decide whether to continue to execution or end."""
    if state["should_continue"] and state.get("compliance_result"):
        # Check if execution should be skipped
        if state["config"].get("skip_execution", False):
            return "end"
        return "execution"
    return "end"


# =============================================================================
# Graph Builder
# =============================================================================

def build_pipeline_graph() -> StateGraph:
    """
    Build the LangGraph pipeline.

    Graph structure:

        [discovery]
             │
             ▼
        ◇ has issues?
        │         │
        No        Yes
        │         │
        ▼         ▼
       END    [policy]
                  │
                  ▼
             ◇ has actions?
             │         │
             No        Yes
             │         │
             ▼         ▼
            END   [compliance]
                       │
                       ▼
                  ◇ has approved?
                  │         │
                  No        Yes
                  │         │
                  ▼         ▼
                 END   [execution]
                            │
                            ▼
                           END
    """

    # Create the graph
    workflow = StateGraph(PipelineState)

    # Add nodes
    workflow.add_node("discovery", discovery_node)
    workflow.add_node("policy", policy_node)
    workflow.add_node("compliance", compliance_node)
    workflow.add_node("execution", execution_node)

    # Set entry point
    workflow.set_entry_point("discovery")

    # Add conditional edges
    workflow.add_conditional_edges(
        "discovery",
        should_continue_to_policy,
        {
            "policy": "policy",
            "end": END,
        }
    )

    workflow.add_conditional_edges(
        "policy",
        should_continue_to_compliance,
        {
            "compliance": "compliance",
            "end": END,
        }
    )

    workflow.add_conditional_edges(
        "compliance",
        should_continue_to_execution,
        {
            "execution": "execution",
            "end": END,
        }
    )

    # Execution always ends
    workflow.add_edge("execution", END)

    return workflow


# =============================================================================
# Pipeline Class
# =============================================================================

class Pipeline:
    """
    LangGraph-based pipeline executor.

    Example:
        >>> pipeline = Pipeline()
        >>> run = await pipeline.execute()
        >>> print(run.get_summary())
    """

    def __init__(
            self,
            config: Optional[PipelineConfig] = None,
            audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize the pipeline.

        Args:
            config: Pipeline configuration
            audit_logger:  Audit logger instance
        """
        self.config = config or PipelineConfig.from_env()
        self.audit = audit_logger or AuditLogger()

        # Build the graph
        self._graph = build_pipeline_graph()
        self._compiled = self._graph.compile()

        # Connect audit
        self.audit.connect()

        logger.info("LangGraph Pipeline initialized")

    async def execute(
            self,
            config: Optional[PipelineConfig] = None,
            trigger: str = "manual",
            triggered_by: str = "system",
    ) -> PipelineRun:
        """
        Execute the pipeline.

        Args:
            config:  Override configuration for this run
            trigger:  What triggered this run
            triggered_by:  Who/what triggered the run

        Returns:
            PipelineRun with results
        """
        config = config or self.config

        # Create run record
        run = PipelineRun(
            config=config.to_dict(),
            trigger=trigger,
            triggered_by=triggered_by,
        )
        run.start()

        logger.info(f"🚀 Starting LangGraph pipeline run: {run.id}")
        self._log_pipeline_start(run)

        # Build initial state
        initial_state: PipelineState = {
            "run_id": run.id,
            "trigger": trigger,
            "triggered_by": triggered_by,
            "config": config.to_dict(),
            "use_llm": config.use_llm,
            "dry_run": config.dry_run,
            "verify_execution": config.verify_execution,
            "diagnosis": None,
            "recommendation": None,
            "compliance_result": None,
            "execution_result": None,
            "steps": {},
            "current_step": "",
            "issues_found": 0,
            "actions_recommended": 0,
            "actions_approved": 0,
            "actions_executed": 0,
            "actions_successful": 0,
            "status": "running",
            "error": None,
            "should_continue": True,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }

        try:
            # Execute the graph
            final_state = await self._compiled.ainvoke(initial_state)

            # Update run from final state
            run = self._state_to_run(run, final_state)

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            run.status = PipelineStatus.FAILED
            run.summary = f"Pipeline error: {str(e)}"
            run.completed_at = datetime.utcnow()

        # Complete the run
        run.complete()
        self._log_pipeline_end(run)

        logger.info(f"🏁 Pipeline run completed: {run.id} - {run.status.value}")

        return run

    def _state_to_run(self, run: PipelineRun, state: PipelineState) -> PipelineRun:
        """Convert final state to PipelineRun."""

        # Copy counts
        run.issues_found = state["issues_found"]
        run.actions_recommended = state["actions_recommended"]
        run.actions_approved = state["actions_approved"]
        run.actions_executed = state["actions_executed"]
        run.actions_successful = state["actions_successful"]

        # Copy steps
        for step_name, step_data in state["steps"].items():
            step = StepResult(step_name=step_name)
            step.status = StepStatus(step_data.get("status", "pending"))
            step.items_processed = step_data.get("items_processed", 0)
            step.items_passed = step_data.get("items_passed", 0)
            step.items_failed = step_data.get("items_failed", 0)
            step.error = step_data.get("error")
            step.duration_ms = step_data.get("duration_ms")
            run.steps[step_name] = step

        # Set status
        if state["error"]:
            run.status = PipelineStatus.FAILED
            run.summary = f"Error: {state['error']}"
        elif state["status"] == "success":
            run.status = PipelineStatus.SUCCESS
        elif state["status"] == "partial":
            run.status = PipelineStatus.PARTIAL

        return run

    def _log_pipeline_start(self, run: PipelineRun):
        """Log pipeline start to audit."""
        try:
            record = AuditRecord(
                record_type=AuditRecordType.SYSTEM,
                agent_name="orchestrator",
                execution_id=run.id,
                summary=f"LangGraph Pipeline started:  {run.id}",
                details={
                    "trigger": run.trigger,
                    "triggered_by": run.triggered_by,
                    "config": run.config,
                },
            )
            self.audit.log_record(record)
        except Exception as e:
            logger.warning(f"Failed to log pipeline start: {e}")

    def _log_pipeline_end(self, run: PipelineRun):
        """Log pipeline end to audit."""
        try:
            record = AuditRecord(
                record_type=AuditRecordType.SYSTEM,
                agent_name="orchestrator",
                execution_id=run.id,
                summary=f"LangGraph Pipeline completed: {run.id} - {run.status.value}",
                details={
                    "status": run.status.value,
                    "duration_ms": run.duration_ms,
                    "issues_found": run.issues_found,
                    "actions_executed": run.actions_executed,
                    "actions_successful": run.actions_successful,
                    "summary": run.summary,
                },
            )
            self.audit.log_record(record)
        except Exception as e:
            logger.warning(f"Failed to log pipeline end: {e}")

    def get_graph_visualization(self) -> str:
        """Get ASCII visualization of the graph."""
        return """
        ┌─────────────┐
        │  DISCOVERY  │
        └──────┬──────┘
               │
               ▼
         ◇ has issues?
         │         │
         No        Yes
         │         │
         ▼         ▼
        END   ┌─────────┐
              │ POLICY  │
              └────┬────┘
                   │
                   ▼
              ◇ has actions?
              │         │
              No        Yes
              │         │
              ▼         ▼
             END  ┌───────────┐
                  │COMPLIANCE │
                  └─────┬─────┘
                        │
                        ▼
                   ◇ approved?
                   │         │
                   No        Yes
                   │         │
                   ▼         ▼
                  END  ┌───────────┐
                       │ EXECUTION │
                       └─────┬─────┘
                             │
                             ▼
                            END
        """