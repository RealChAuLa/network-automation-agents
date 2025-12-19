"""
MCP Client

A client that directly calls MCP tool handlers.
This simulates what an LLM would do when calling MCP tools.
"""

import json
import logging
from typing import Any, Optional
from dataclasses import dataclass

# Import MCP tool handlers directly
from src.mcp_server.tools import telemetry_handlers
from src.mcp_server.tools import topology_handlers
from src.mcp_server.tools import policy_handlers
from src.mcp_server.tools import execution_handlers
from src.mcp_server.tools import diagnosis_handlers

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool call."""
    success: bool
    data: Any
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


class MCPClient:
    """
    Client to call MCP tools.

    This client provides a clean interface to call MCP tools,
    mimicking what an LLM would do through the MCP protocol.

    Example:
        client = MCPClient()
        result = await client.call_tool("get_node_metrics", {"node_id": "router_core_01"})
        print(result.data)
    """

    def __init__(self):
        """Initialize the MCP client."""
        self._handlers = {}
        self._register_handlers()
        logger.info(f"MCPClient initialized with {len(self._handlers)} tools")

    def _register_handlers(self):
        """Register all tool handlers."""
        # Telemetry tools
        self._handlers.update(telemetry_handlers.get_handlers())

        # Topology tools
        self._handlers.update(topology_handlers.get_handlers())

        # Policy tools
        self._handlers.update(policy_handlers.get_handlers())

        # Execution tools
        self._handlers.update(execution_handlers.get_handlers())

        # Diagnosis tools
        self._handlers.update(diagnosis_handlers.get_handlers())

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names."""
        return list(self._handlers.keys())

    def get_tool_descriptions(self) -> list[dict]:
        """Get descriptions of all available tools."""
        tools = []

        # Collect tool definitions from each handler module
        for tool in telemetry_handlers.get_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": tool.inputSchema,
            })

        for tool in topology_handlers.get_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": tool.inputSchema,
            })

        for tool in policy_handlers.get_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": tool.inputSchema,
            })

        for tool in execution_handlers.get_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": tool.inputSchema,
            })

        for tool in diagnosis_handlers.get_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": tool.inputSchema,
            })

        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] = None) -> ToolResult:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            ToolResult with the tool's response
        """
        arguments = arguments or {}

        if tool_name not in self._handlers:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}.  Available: {self.get_available_tools()}"
            )

        try:
            logger.debug(f"Calling tool: {tool_name} with args: {arguments}")

            handler = self._handlers[tool_name]
            result = await handler(arguments)

            # Parse the result (handlers return list[TextContent])
            if result and len(result) > 0:
                content = result[0].text
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = content

                # Check if result contains an error
                if isinstance(data, dict) and "error" in data:
                    return ToolResult(success=False, data=data, error=data["error"])

                return ToolResult(success=True, data=data)

            return ToolResult(success=True, data=None)

        except Exception as e:
            logger.error(f"Tool call failed: {tool_name} - {e}")
            return ToolResult(success=False, data=None, error=str(e))

    # ==========================================================================
    # Convenience methods for common operations
    # ==========================================================================

    async def get_node_metrics(self, node_id: Optional[str] = None) -> ToolResult:
        """Get metrics for a node or all nodes."""
        args = {}
        if node_id:
            args["node_id"] = node_id
        return await self.call_tool("get_node_metrics", args)

    async def get_network_logs(
            self,
            node_id: Optional[str] = None,
            level: Optional[str] = None,
            count: int = 50,
    ) -> ToolResult:
        """Get network logs."""
        args = {"count": count}
        if node_id:
            args["node_id"] = node_id
        if level:
            args["level"] = level
        return await self.call_tool("get_network_logs", args)

    async def get_alerts(
            self,
            severity: Optional[str] = None,
            node_id: Optional[str] = None,
    ) -> ToolResult:
        """Get active alerts."""
        args = {}
        if severity:
            args["severity"] = severity
        if node_id:
            args["node_id"] = node_id
        return await self.call_tool("get_alerts", args)

    async def get_network_topology(self, include_links: bool = True) -> ToolResult:
        """Get network topology."""
        return await self.call_tool("get_network_topology", {"include_links": include_links})

    async def get_node_details(self, node_id: str) -> ToolResult:
        """Get details for a specific node."""
        return await self.call_tool("get_node_details", {"node_id": node_id})

    async def get_connected_nodes(self, node_id: str, direction: str = "all") -> ToolResult:
        """Get nodes connected to a specific node."""
        return await self.call_tool("get_connected_nodes", {
            "node_id": node_id,
            "direction": direction,
        })

    async def find_network_path(self, source_id: str, target_id: str) -> ToolResult:
        """Find path between two nodes."""
        return await self.call_tool("find_network_path", {
            "source_node_id": source_id,
            "target_node_id": target_id,
        })

    async def get_node_impact(self, node_id: str) -> ToolResult:
        """Get impact analysis for a node."""
        return await self.call_tool("get_node_impact", {"node_id": node_id})

    async def get_policies(self, status: str = "active") -> ToolResult:
        """Get policies."""
        return await self.call_tool("get_policies", {"status": status})

    async def evaluate_policies(
            self,
            anomaly_type: str,
            severity: str,
            node_type: Optional[str] = None,
            **kwargs,
    ) -> ToolResult:
        """Evaluate policies for a given context."""
        args = {
            "anomaly_type": anomaly_type,
            "severity": severity,
        }
        if node_type:
            args["node_type"] = node_type
        args.update(kwargs)
        return await self.call_tool("evaluate_policies", args)

    async def validate_action(
            self,
            action_type: str,
            target_node_id: str,
            reason: str = "",
    ) -> ToolResult:
        """Validate if an action is allowed."""
        return await self.call_tool("validate_action", {
            "action_type": action_type,
            "target_node_id": target_node_id,
            "reason": reason,
        })

    async def execute_action(
            self,
            action_type: str,
            target_node_id: str,
            reason: str,
            parameters: dict = None,
            policy_ids: list = None,
    ) -> ToolResult:
        """Execute an action on a node."""
        args = {
            "action_type": action_type,
            "target_node_id": target_node_id,
            "reason": reason,
        }
        if parameters:
            args["parameters"] = parameters
        if policy_ids:
            args["policy_ids"] = policy_ids
        return await self.call_tool("execute_action", args)

    async def run_diagnosis(
            self,
            node_id: Optional[str] = None,
            check_types: list = None,
    ) -> ToolResult:
        """Run diagnosis on node(s)."""
        args = {}
        if node_id:
            args["node_id"] = node_id
        if check_types:
            args["check_types"] = check_types
        return await self.call_tool("run_diagnosis", args)

    async def get_anomalies(
            self,
            severity: Optional[str] = None,
            node_id: Optional[str] = None,
    ) -> ToolResult:
        """Get active anomalies."""
        args = {}
        if severity:
            args["severity"] = severity
        if node_id:
            args["node_id"] = node_id
        return await self.call_tool("get_anomalies", args)

    async def inject_test_anomaly(
            self,
            node_id: str,
            anomaly_type: str,
            severity: str = "medium",
    ) -> ToolResult:
        """Inject a test anomaly."""
        return await self.call_tool("inject_test_anomaly", {
            "node_id": node_id,
            "anomaly_type": anomaly_type,
            "severity": severity,
        })

    async def clear_anomaly(self, anomaly_id: Optional[str] = None) -> ToolResult:
        """Clear anomaly(s)."""
        args = {}
        if anomaly_id:
            args["anomaly_id"] = anomaly_id
        return await self.call_tool("clear_anomaly", args)