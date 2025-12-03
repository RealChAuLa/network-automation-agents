"""
MCP Server

Main entry point for the Model Context Protocol server.
"""

import asyncio
import logging
import json
from typing import Any

from mcp. server import Server
from mcp. server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.mcp_server.config import config

# Import tool handlers
from src.mcp_server.tools import telemetry_handlers
from src.mcp_server.tools import topology_handlers
from src.mcp_server.tools import policy_handlers
from src. mcp_server. tools import execution_handlers
from src.mcp_server.tools import diagnosis_handlers


# Configure logging
logging. basicConfig(
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

    # Collect all tools from all modules
    all_tools = []
    all_tools.extend(telemetry_handlers. get_tools())
    all_tools.extend(topology_handlers.get_tools())
    all_tools.extend(policy_handlers.get_tools())
    all_tools.extend(execution_handlers. get_tools())
    all_tools. extend(diagnosis_handlers.get_tools())

    logger.info(f"Registered {len(all_tools)} tools")

    # Create tool lookup
    tool_handlers = {}
    tool_handlers.update(telemetry_handlers. get_handlers())
    tool_handlers.update(topology_handlers.get_handlers())
    tool_handlers.update(policy_handlers.get_handlers())
    tool_handlers.update(execution_handlers. get_handlers())
    tool_handlers. update(diagnosis_handlers.get_handlers())

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Route tool calls to appropriate handlers."""
        logger.info(f"Tool called: {name} with arguments: {arguments}")

        if name in tool_handlers:
            try:
                result = await tool_handlers[name](arguments)
                return result
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=json.dumps({
                    "error": str(e),
                    "tool": name
                }, indent=2))]
        else:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Unknown tool: {name}",
                "available_tools": list(tool_handlers.keys())
            }, indent=2))]

    logger.info(f"MCP Server '{config.server_name}' configured successfully")

    return server


async def run_server():
    """Run the MCP server."""
    server = create_server()

    logger.info(f"Starting MCP Server v{config.server_version}...")
    logger. info(f"Server name: {config.server_name}")

    async with stdio_server() as (read_stream, write_stream):
        await server. run(
            read_stream,
            write_stream,
            server. create_initialization_options()
        )


def main():
    """Main entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger. error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()