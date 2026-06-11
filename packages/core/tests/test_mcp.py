"""Tests for hiveflow MCP module."""
import pytest

from hiveflow.mcp import MCPClient, MCPTransportType


@pytest.mark.asyncio
async def test_mcp_mock_initialize_and_list_tools():
    client = MCPClient(transport="mock")
    await client.initialize()
    assert client.is_connected()
    tools = await client.list_tools()
    assert isinstance(tools, list)


@pytest.mark.asyncio
async def test_mcp_mock_register_and_call_tool():
    client = MCPClient(transport="mock")
    await client.initialize()

    async def echo_handler(args):
        return {"echo": args.get("message", "")}

    client.register_tool("echo", echo_handler)
    tools = await client.list_tools()
    assert any(t.name == "echo" for t in tools)

    result = await client.call_tool("echo", {"message": "hello"})
    assert result.success
    assert "hello" in str(result.content)


def test_mcp_implemented_transports():
    implemented = MCPTransportType.implemented()
    assert MCPTransportType.STDIO in implemented
    assert MCPTransportType.MOCK in implemented
    assert MCPTransportType.SSE not in implemented


@pytest.mark.asyncio
async def test_mcp_sse_raises_not_implemented():
    client = MCPClient(transport="sse")
    with pytest.raises(NotImplementedError, match="not implemented"):
        await client.initialize()
