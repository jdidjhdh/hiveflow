"""
HiveFlow - 07: MCP Tool Integration

This example demonstrates Model Context Protocol tool integration in mock mode.

Usage:
    python 07_mcp_tools.py
"""
import asyncio
from hiveflow import MCPClient, MCPToolParam


async def main():
    print("=== MCP Tool Integration Example ===\n")

    client = MCPClient(transport="mock")

    async def get_weather(args):
        location = args.get("location", "unknown")
        return {"content": f"Sunny, 22°C in {location}"}

    async def calculate(args):
        expression = args.get("expression", "0")
        try:
            value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 — demo only
            return {"content": str(value)}
        except Exception as exc:
            return {"content": f"Error: {exc}"}

    client.register_tool("get_weather", get_weather)
    client.register_tool("calculate", calculate)
    await client.initialize()

    tools = await client.list_tools()
    print(f"Registered tools: {[t.name for t in tools]}")

    weather = await client.call_tool("get_weather", {"location": "San Francisco"})
    print(f"\nWeather: {weather.content}")

    calc = await client.call_tool("calculate", {"expression": "(10 + 20 + 30 + 40 + 50) / 5"})
    print(f"Average: {calc.content}")

    print("\nMCP provides unified tool discovery and invocation across providers.")


if __name__ == "__main__":
    asyncio.run(main())
