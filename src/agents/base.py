"""
Base Agent

Abstract base class for all agents.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field
import uuid

from src.agents.config import AgentConfig, config as default_config


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_name: str
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    success: bool = True
    started_at: datetime = field(default_factory=lambda:datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def complete(self, result: Any = None, error: Optional[str] = None):
        """Mark the execution as complete."""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        if error:
            self.success = False
            self.error = error
        else:
            self.result = result

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "execution_id": self.execution_id,
            "success": self.success,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    All agents should inherit from this class and implement the run() method.
    """

    def __init__(
            self,
            name: str,
            config: Optional[AgentConfig] = None,
            logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the agent.

        Args:
            name: Agent name
            config: Agent configuration (uses default if not provided)
            logger: Logger instance (creates one if not provided)
        """
        self.name = name
        self.config = config or default_config
        self.logger = logger or logging.getLogger(f"agent.{name}")

        # Set log level
        self.logger.setLevel(getattr(logging, self.config.log_level))

        # Execution history
        self._execution_history: list[AgentResult] = []

    @abstractmethod
    async def run(self, **kwargs) -> AgentResult:
        """
        Execute the agent's main task.

        This method should be implemented by subclasses.

        Returns:
            AgentResult with the execution outcome
        """
        pass

    def _create_result(self) -> AgentResult:
        """Create a new AgentResult for this execution."""
        return AgentResult(agent_name=self.name)

    def _record_execution(self, result: AgentResult):
        """Record an execution in history."""
        self._execution_history.append(result)

        # Keep only last 100 executions
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]

    def get_execution_history(self, limit: int = 10) -> list[AgentResult]:
        """Get recent execution history."""
        return list(reversed(self._execution_history))[:limit]

    def get_last_execution(self) -> Optional[AgentResult]:
        """Get the last execution result."""
        return self._execution_history[-1] if self._execution_history else None