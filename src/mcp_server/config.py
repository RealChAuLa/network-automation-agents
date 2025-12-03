"""
MCP Server Configuration
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class MCPConfig:
    """Configuration for the MCP server."""

    # Server info
    server_name: str = os.getenv("MCP_SERVER_NAME", "network-automation-mcp")
    server_version: str = os.getenv("MCP_SERVER_VERSION", "0.1.0")

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # Logging
    log_level: str = os.getenv("MCP_LOG_LEVEL", "INFO")


# Global config instance
config = MCPConfig()