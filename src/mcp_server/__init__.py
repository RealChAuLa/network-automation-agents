"""
MCP Server Package

Provides Model Context Protocol server for network automation tools.
"""

from src.mcp_server.server import create_server, main

__all__ = [
    "create_server",
    "main",
]