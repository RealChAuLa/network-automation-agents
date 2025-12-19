"""
Agents Package

Contains AI agents for network automation.
"""

from src.agents.config import AgentConfig
from src.agents. base import BaseAgent
from src.agents.mcp_client import MCPClient

# Import agents
from src.agents.discovery import DiscoveryAgent
from src.agents.policy import PolicyAgent
from src.agents.compliance import ComplianceAgent

__all__ = [
    "AgentConfig",
    "BaseAgent",
    "MCPClient",
    "DiscoveryAgent",
    "PolicyAgent",
    "ComplianceAgent",
]