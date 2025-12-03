"""
MCP Server

Main entry point for the Model Context Protocol server.
"""

import asyncio
import logging
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.mcp_server.config import config
from src.mcp_server.tools.telemetry import register_telemetry_tools
from src.mcp_server.tools.topology import register_topology_tools
from src.mcp_server.tools.policy import register_policy_tools
from src.mcp_server.tools.execution import register_execution_tools
from src.mcp_server.tools.diagnosis import register_diagnosis_tools

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_server() -> Server:
    """
    Create and configure the MCP server.

    Returns:
        Configured MCP Server instance
    """
    server = Server(config.server_name)

    # Register all tools
    logger.info("Registering telemetry tools...")
    register_telemetry_tools(server)

    logger.info("Registering topology tools...")
    register_topology_tools(server)

    logger.info("Registering policy tools...")
    register_policy_tools(server)

    logger.info("Registering execution tools...")
    register_execution_tools(server)

    logger.info("Registering diagnosis tools...")
    register_diagnosis_tools(server)

    logger.info(f"MCP Server '{config.server_name}' configured successfully")

    return server


async def run_server():
    """Run the MCP server."""
    server = create_server()

    logger.info(f"Starting MCP Server v{config.server_version}...")
    logger.info(f"Server name: {config.server_name}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """Main entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()