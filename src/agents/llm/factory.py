"""
LLM Factory

Creates the appropriate LLM instance based on configuration.
"""

import logging
from typing import Optional

from src.agents.llm.base import BaseLLM
from src.agents.config import LLMConfig, config as default_config

logger = logging.getLogger(__name__)


class RuleBasedFallback(BaseLLM):
    """
    Fallback when no LLM is available.

    This doesn't actually use an LLM - it just returns a message
    indicating that LLM analysis is not available.
    """

    def __init__(self):
        super().__init__(model="none", temperature=0, max_tokens=0)

    @property
    def provider_name(self) -> str:
        return "none"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None):
        from src.agents.llm.base import LLMResponse
        return LLMResponse(
            content="LLM analysis not available. Using rule-based analysis only.",
            model="none",
            provider="none",
        )

    async def generate_structured(self, prompt: str, output_schema: dict, system_prompt: Optional[str] = None) -> dict:
        return {
            "llm_available": False,
            "message": "LLM analysis not available. Using rule-based analysis only.",
        }

    def is_available(self) -> bool:
        return False


def create_llm(llm_config: Optional[LLMConfig] = None) -> BaseLLM:
    """
    Create an LLM instance based on configuration.

    Args:
        llm_config: LLM configuration (uses default if not provided)

    Returns:
        BaseLLM instance
    """
    config = llm_config or default_config.llm

    provider = config.provider.lower()

    # Check if provider is explicitly disabled
    if provider == "none":
        logger.info("LLM disabled by configuration, using rule-based fallback")
        return RuleBasedFallback()

    # Try Gemini
    if provider == "gemini":
        if config.gemini_api_key:
            from src.agents.llm.gemini_llm import GeminiLLM
            logger.info(f"Creating Gemini LLM with model: {config.gemini_model}")
            return GeminiLLM(
                api_key=config.gemini_api_key,
                model=config.gemini_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        else:
            logger.warning("Gemini API key not found, falling back to rule-based")
            return RuleBasedFallback()

    # Try Claude (optional - for future use)
    if provider == "claude":
        if config.anthropic_api_key:
            logger.warning("Claude LLM not yet implemented, falling back to rule-based")
            # Future: from src.agents.llm.claude_llm import ClaudeLLM
            return RuleBasedFallback()
        else:
            logger.warning("Anthropic API key not found, falling back to rule-based")
            return RuleBasedFallback()

    # Try OpenAI (optional - for future use)
    if provider == "openai":
        if config.openai_api_key:
            logger.warning("OpenAI LLM not yet implemented, falling back to rule-based")
            # Future: from src. agents.llm.openai_llm import OpenAILLM
            return RuleBasedFallback()
        else:
            logger.warning("OpenAI API key not found, falling back to rule-based")
            return RuleBasedFallback()

    # Unknown provider
    logger.warning(f"Unknown LLM provider: {provider}, falling back to rule-based")
    return RuleBasedFallback()


def get_available_providers() -> list[str]:
    """Get list of available LLM providers based on configuration."""
    cfg = default_config.llm
    available = []

    if cfg.gemini_api_key:
        available.append("gemini")
    if cfg.anthropic_api_key:
        available.append("claude")
    if cfg.openai_api_key:
        available.append("openai")

    available.append("none")  # Rule-based is always available

    return available