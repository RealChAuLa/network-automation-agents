"""
Base LLM

Abstract base class for LLM implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timezone


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    provider: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda:datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BaseLLM(ABC):
    """
    Abstract base class for LLM implementations.

    All LLM providers should inherit from this class.
    """

    def __init__(self, model: str, temperature: float = 0.1, max_tokens: int = 4096):
        """
        Initialize the LLM.

        Args:
            model: Model name/identifier
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'gemini', 'claude', 'openai')."""
        pass

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context

        Returns:
            LLMResponse with the generated content
        """
        pass

    @abstractmethod
    async def generate_structured(
            self,
            prompt: str,
            output_schema: dict,
            system_prompt: Optional[str] = None
    ) -> dict:
        """
        Generate a structured response matching a schema.

        Args:
            prompt: The user prompt
            output_schema: JSON schema for the expected output
            system_prompt: Optional system prompt

        Returns:
            Dictionary matching the output schema
        """
        pass

    def is_available(self) -> bool:
        """Check if the LLM is available and properly configured."""
        return True