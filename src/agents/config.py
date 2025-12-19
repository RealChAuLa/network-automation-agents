"""
Agent Configuration

Centralized configuration for all agents.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))

    # Gemini
    gemini_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

    # Claude (optional)
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229"))

    # OpenAI (optional)
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # LLM Settings
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "8192")))

    def is_llm_available(self) -> bool:
        """Check if any LLM is configured and available."""
        if self.provider == "none":
            return False
        if self.provider == "gemini" and self.gemini_api_key:
            return True
        if self.provider == "claude" and self.anthropic_api_key:
            return True
        if self.provider == "openai" and self.openai_api_key:
            return True
        return False


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection."""

    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))


@dataclass
class DiscoveryAgentConfig:
    """Configuration specific to Discovery Agent."""

    enabled: bool = field(default_factory=lambda: os.getenv("DISCOVERY_AGENT_ENABLED", "true").lower() == "true")
    interval_minutes: int = field(default_factory=lambda: int(os.getenv("DISCOVERY_AGENT_INTERVAL_MINUTES", "5")))

    # Thresholds for rule-based analysis
    cpu_warning_threshold: float = 80.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 90.0
    packet_loss_warning_threshold: float = 2.0
    packet_loss_critical_threshold: float = 5.0
    latency_warning_threshold: float = 30.0
    latency_critical_threshold: float = 50.0
    error_count_warning_threshold: int = 50
    error_count_critical_threshold: int = 100

    # Analysis settings
    log_analysis_count: int = 100
    log_time_range_minutes: int = 60
    include_topology_context: bool = True
    use_llm_for_root_cause: bool = True


@dataclass
class AgentConfig:
    """Main configuration container for all agents."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    discovery: DiscoveryAgentConfig = field(default_factory=DiscoveryAgentConfig)

    log_level: str = field(default_factory=lambda: os.getenv("AGENT_LOG_LEVEL", "INFO"))


# Global config instance
config = AgentConfig()