"""HiveFlow - MCP (Model Context Protocol) Integration

Provides:
- MCPClient: Connect to MCP servers via stdio/SSE/HTTP
- MCPTool: Wrap MCP tools for use by ReActWorker and other agents
- MCPPlugin: Manage MCP plugin lifecycle (install/uninstall/configure)
- MCPServer: Make HiveFlow Agent tools available via MCP protocol

Implements the MCP specification (https://modelcontextprotocol.io) for tool discovery and invocation.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ======================== MCP Transport ========================

class MCPTransportType(str, Enum):
    """Supported MCP transport types."""
    STDIO = "stdio"       # Subprocess with stdin/stdout
    SSE = "sse"           # Server-Sent Events
    HTTP = "http"         # HTTP POST/GET
    STREAMABLE = "streamable_http"  # Streamable HTTP transport
    MOCK = "mock"         # Mock transport for testing


@dataclass
class MCPToolParam:
    """Parameter definition for an MCP tool."""
    name: str
    description: str
    type: str = "string"
    required: bool = False
    enum: Optional[List[str]] = None


@dataclass
class MCPTool:
    """A tool provided by an MCP server."""
    name: str
    description: str
    parameters: List[MCPToolParam]
    server_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                }
                for p in self.parameters
            ],
        }


@dataclass
class MCPResource:
    """A resource provided by an MCP server."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    server_name: str = ""


@dataclass
class MCPToolCallResult:
    """Result of calling an MCP tool."""
    tool_name: str
    success: bool
    content: str = ""
    error: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """
    Client for connecting to MCP servers.
    
    Supports stdio transport (subprocess) and mock mode for testing.
    
    Usage:
        # stdio mode
        client = MCPClient(
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/path"],
        )
        await client.initialize()
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "/path/file.txt"})
        
        # Mock mode (for testing)
        client = MCPClient(transport="mock")
        client.register_tool("echo", lambda args: {"content": args.get("text", "")})
    """

    def __init__(
        self,
        transport: str = "stdio",
        command: str = "",
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.transport = MCPTransportType(transport) if isinstance(transport, str) else transport
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._initialized = False
        self._tools: List[MCPTool] = []
        self._resources: List[MCPResource] = []
        self._mock_handlers: Dict[str, Callable] = {}
        self._request_id = 0

    async def initialize(self):
        """Initialize the MCP connection."""
        if self.transport == MCPTransportType.STDIO:
            await self._init_stdio()
        elif self.transport == MCPTransportType.MOCK:
            self._initialized = True
            self._refresh_tools_mock()
        else:
            raise NotImplementedError(f"Transport {self.transport.value} not implemented")

        if self._initialized:
            await self._refresh_tools()
            logger.info(f"MCP client initialized (transport={self.transport.value})")

    async def _init_stdio(self):
        """Initialize stdio transport."""
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**self.env},
            )
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to start MCP stdio process: {e}")
            raise

    async def close(self):
        """Close the MCP connection."""
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception:
                self._process.kill()
            self._process = None
        self._initialized = False
        self._tools = []

    async def list_tools(self) -> List[MCPTool]:
        """List available tools from the MCP server."""
        if not self._initialized:
            await self.initialize()
        return list(self._tools)

    async def _refresh_tools(self):
        """Refresh the list of available tools."""
        if self.transport == MCPTransportType.STDIO:
            await self._refresh_tools_stdio()
        elif self.transport == MCPTransportType.MOCK:
            self._refresh_tools_mock()

    async def _refresh_tools_stdio(self):
        """Refresh tools via stdio transport."""
        try:
            response = await self._send_request("tools/list", {})
            if response and "tools" in response:
                self._tools = []
                for tool_def in response["tools"]:
                    params = []
                    if "inputSchema" in tool_def:
                        schema = tool_def["inputSchema"]
                        required = set(schema.get("required", []))
                        for name, prop in schema.get("properties", {}).items():
                            params.append(MCPToolParam(
                                name=name,
                                description=prop.get("description", ""),
                                type=prop.get("type", "string"),
                                required=name in required,
                                enum=prop.get("enum"),
                            ))
                    self._tools.append(MCPTool(
                        name=tool_def["name"],
                        description=tool_def.get("description", ""),
                        parameters=params,
                    ))
        except Exception as e:
            logger.warning(f"Failed to refresh MCP tools: {e}")

    async def _send_request(self, method: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Send a JSON-RPC request via stdio and return the response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("MCP stdio transport not initialized")

        request_id = self._request_id
        self._request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str.encode())
        await self._process.stdin.drain()

        try:
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self.timeout,
            )
            response = json.loads(response_line.decode())
            if "error" in response:
                raise Exception(response["error"].get("message", "Unknown error"))
            return response.get("result")
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request timed out: {method}")

    def _refresh_tools_mock(self):
        """Refresh tools from mock handlers."""
        self._tools = []
        for name, handler in self._mock_handlers.items():
            params = []
            if hasattr(handler, "__doc__") and handler.__doc__:
                # Parse docstring for params
                for line in handler.__doc__.split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        parts = line[2:].split(": ", 1)
                        if len(parts) == 2:
                            param_name, desc = parts
                            params.append(MCPToolParam(
                                name=param_name,
                                description=desc,
                            ))
            self._tools.append(MCPTool(
                name=name,
                description=handler.__doc__ or f"Mock tool: {name}",
                parameters=params,
                server_name="mock",
            ))

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Call an MCP tool."""
        import time
        start = time.monotonic()

        try:
            if self.transport == MCPTransportType.MOCK:
                result = await self._call_mock(tool_name, arguments)
            elif self.transport == MCPTransportType.STDIO:
                result = await self._call_stdio(tool_name, arguments)
            else:
                return MCPToolCallResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Unsupported transport: {self.transport.value}",
                )

            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                success=True,
                content=json.dumps(result, default=str) if isinstance(result, dict) else str(result),
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def _call_mock(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a mock tool handler."""
        handler = self._mock_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Mock tool not found: {tool_name}")

        result = handler(arguments)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _call_stdio(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool via stdio transport."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP stdio transport not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        self._request_id += 1

        # Send request
        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str.encode())
        await self._process.stdin.drain()

        # Read response (simplified - in production, need proper async reading)
        try:
            stdout_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self.timeout,
            )
            response = json.loads(stdout_line.decode())
            if "error" in response:
                raise Exception(response["error"].get("message", "Unknown error"))
            return response.get("result", {})
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP tool call timed out after {self.timeout}s")

    def register_tool(self, name: str, handler: Callable):
        """Register a mock tool handler."""
        self._mock_handlers[name] = handler
        self._refresh_tools_mock()

    def register_tools(self, tools: Dict[str, Callable]):
        """Register multiple mock tool handlers."""
        for name, handler in tools.items():
            self._mock_handlers[name] = handler
        self._refresh_tools_mock()

    async def list_resources(self) -> List[MCPResource]:
        """List available resources from the MCP server."""
        return list(self._resources)

    def is_connected(self) -> bool:
        return self._initialized


# ======================== MCP Plugin Manager ========================

@dataclass
class MCPPlugin:
    """An MCP plugin configuration."""
    plugin_id: str
    name: str
    description: str = ""
    transport: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    tools: List[MCPTool] = field(default_factory=list)
    resources: List[MCPResource] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "description": self.description,
            "transport": self.transport,
            "command": self.command,
            "args": self.args,
            "enabled": self.enabled,
            "tool_count": len(self.tools),
            "resource_count": len(self.resources),
        }


class MCPPluginManager:
    """
    Manages MCP plugins (servers).
    
    Usage:
        mgr = MCPPluginManager()
        
        # Register a plugin
        plugin = await mgr.register_plugin(
            plugin_id="filesystem",
            name="Filesystem Server",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
        )
        
        # Initialize and discover tools
        await mgr.initialize_plugin("filesystem")
        tools = await mgr.get_plugin_tools("filesystem")
        
        # Call a tool
        result = await mgr.call_tool("filesystem", "read_file", {"path": "/workspace/file.txt"})
    """

    def __init__(self):
        self._plugins: Dict[str, MCPPlugin] = {}
        self._clients: Dict[str, MCPClient] = {}

    async def register_plugin(
        self,
        plugin_id: str,
        name: str,
        description: str = "",
        transport: str = "stdio",
        command: str = "",
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> MCPPlugin:
        """Register an MCP plugin."""
        plugin = MCPPlugin(
            plugin_id=plugin_id,
            name=name,
            description=description,
            transport=transport,
            command=command,
            args=args or [],
            env=env or {},
        )
        self._plugins[plugin_id] = plugin
        logger.info(f"MCP plugin registered: {plugin_id} ({name})")
        return plugin

    async def initialize_plugin(self, plugin_id: str):
        """Initialize an MCP plugin (connect to server)."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_id}")

        if plugin.transport == "mock":
            client = MCPClient(transport="mock")
            await client.initialize()
        else:
            client = MCPClient(
                transport=plugin.transport,
                command=plugin.command,
                args=plugin.args,
                env=plugin.env,
            )
            await client.initialize()

        self._clients[plugin_id] = client
        plugin.tools = await client.list_tools()
        plugin.resources = await client.list_resources()
        logger.info(f"MCP plugin initialized: {plugin_id} ({len(plugin.tools)} tools)")

    async def close_plugin(self, plugin_id: str):
        """Close an MCP plugin connection."""
        client = self._clients.get(plugin_id)
        if client:
            await client.close()
            del self._clients[plugin_id]
        if plugin_id in self._plugins:
            self._plugins[plugin_id].tools = []

    async def get_plugin(self, plugin_id: str) -> Optional[MCPPlugin]:
        """Get a plugin by ID."""
        return self._plugins.get(plugin_id)

    async def list_plugins(self) -> List[MCPPlugin]:
        """List all registered plugins."""
        return list(self._plugins.values())

    async def get_plugin_tools(self, plugin_id: str) -> List[MCPTool]:
        """Get tools from a specific plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin not found: {plugin_id}")
        return plugin.tools

    async def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all enabled plugins."""
        all_tools = []
        for plugin in self._plugins.values():
            if plugin.enabled:
                all_tools.extend(plugin.tools)
        return all_tools

    async def call_tool(
        self,
        plugin_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> MCPToolCallResult:
        """Call a tool from a specific plugin."""
        client = self._clients.get(plugin_id)
        if not client:
            # Auto-initialize
            await self.initialize_plugin(plugin_id)
            client = self._clients[plugin_id]

        return await client.call_tool(tool_name, arguments)

    async def remove_plugin(self, plugin_id: str) -> bool:
        """Remove a plugin."""
        await self.close_plugin(plugin_id)
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        total_tools = sum(len(p.tools) for p in self._plugins.values())
        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": sum(1 for p in self._plugins.values() if p.enabled),
            "total_tools": total_tools,
            "plugins": [
                {
                    "name": p.name,
                    "transport": p.transport,
                    "tools": len(p.tools),
                    "enabled": p.enabled,
                }
                for p in self._plugins.values()
            ],
        }
