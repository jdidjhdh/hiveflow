"""Register MCP plugin tools as HiveMind skills."""
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


async def register_mcp_plugin_as_skills(
    app,
    plugin_manager,
    plugin_id: str,
    *,
    read_keys: Optional[Set[str]] = None,
    write_keys: Optional[Set[str]] = None,
    argument_key: str = "arguments",
) -> List[str]:
    """Initialize an MCP plugin and expose each tool as a named skill."""
    read_keys = read_keys or {"mcp:*", "hivemind:result:*"}
    write_keys = write_keys or {"mcp:*", "hivemind:result:*"}

    await plugin_manager.initialize_plugin(plugin_id)
    tools = await plugin_manager.get_plugin_tools(plugin_id)
    registered: List[str] = []

    for tool in tools:
        skill_name = f"mcp_{plugin_id}_{tool.name}"
        if skill_name in app.skill_bindings:
            continue

        async def handler(
            ecm,
            view,
            _tool_name=tool.name,
            _plugin_id=plugin_id,
            _arg_key=argument_key,
        ):
            args = ecm.payload.get(_arg_key) or ecm.payload.get("args") or {}
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"input": args}
            result = await plugin_manager.call_tool(_plugin_id, _tool_name, args)
            payload: Dict[str, Any] = {
                "success": result.success,
                "content": result.content,
                "error": result.error,
                "tool": _tool_name,
            }
            await view.put(f"hivemind:result:{ecm.intent_id}", payload)
            return payload

        agent_id = f"mcp-{plugin_id}-{tool.name}".replace(" ", "_")[:64]
        await app.create_skill_agent(
            skill_name,
            agent_id,
            handler,
            read_keys=read_keys,
            write_keys=write_keys,
        )
        app.config.skill_registry[skill_name] = tool.description or f"MCP tool {tool.name}"
        registered.append(skill_name)
        logger.info("Registered MCP skill %s from plugin %s", skill_name, plugin_id)

    return registered
