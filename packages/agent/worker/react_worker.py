import json
import logging
from typing import Any, List, Optional

try:
    from .tools import Tool
except ImportError:
    from worker.tools import Tool


logger = logging.getLogger(__name__)


class ReActWorker:
    def __init__(self, agent_id: str, llm, tools: List[Tool],
                 system_prompt: str = "You are a helpful AI assistant.",
                 max_steps: int = 10,
                 memory_manager: Optional = None,
                 max_message_history: int = 20):
        self.agent_id = agent_id
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.memory = memory_manager
        self.max_message_history = max_message_history

    async def task_handler(self, ecm, view) -> Any:
        try:
            return await self._run(ecm, view)
        except Exception as e:
            logger.exception("ReActWorker unhandled error")
            # 回写错误结果到预期键，避免编排器死等
            if hasattr(ecm, 'expectation') and ecm.expectation:
                try:
                    await view.put(ecm.expectation.state_key, {"error": str(e)})
                except Exception:
                    pass
            return {"error": str(e)}

    async def _run(self, ecm, view) -> Any:
        task_input = ecm.payload.get("query") or getattr(ecm, 'user_query', '') or str(ecm.payload)
        input_keys = ecm.payload.get("input_keys", {})

        # 读取上游依赖
        input_data = {}
        for name, key in input_keys.items():
            try:
                input_data[name] = await view.get(key)
            except (KeyError, PermissionError):
                input_data[name] = f"<unavailable: {key}>"

        messages = [{"role": "system", "content": self.system_prompt}]

        if input_data:
            messages.append({
                "role": "system",
                "content": f"Upstream data:\n{json.dumps(input_data, ensure_ascii=False)}"
            })

        ctx = ecm.payload.get("context", {})
        short_term = ctx.get("short_term", [])
        long_term = ctx.get("long_term", "")
        if short_term:
            messages.append({
                "role": "system",
                "content": "Recent conversation:\n" + "\n".join(
                    [f"{t['role']}: {t['content']}" for t in short_term]
                )
            })
        if long_term:
            messages.append({"role": "system", "content": f"Relevant memory:\n{long_term}"})

        tool_descs = [{"name": t.name, "description": t.description, "parameters": t.parameters}
                      for t in self.tools.values()]
        messages.append({"role": "system", "content": f"Tools: {json.dumps(tool_descs)}"})
        messages.append({
            "role": "system",
            "content": (
                "Respond ONLY with JSON:\n"
                '{"type": "tool_call", "tool": "<name>", "input": <params>}\n'
                '{"type": "final_answer", "content": "<answer>"}'
            )
        })
        messages.append({"role": "user", "content": task_input})

        for step in range(self.max_steps):
            if len(messages) > self.max_message_history:
                system_msgs = [m for m in messages if m["role"] == "system"]
                non_system = [m for m in messages if m["role"] != "system"]
                keep_non_system = max(2, self.max_message_history - len(system_msgs))
                messages[:] = system_msgs + non_system[-keep_non_system:]

            try:
                resp = await self.llm.complete_json(messages)
            except ValueError as e:
                logger.error(f"ReActWorker {self.agent_id} JSON parse failed: {e}")
                return {"error": "Failed to generate valid action"}

            if resp.get("type") == "final_answer":
                return resp["content"]
            elif resp.get("type") == "tool_call":
                tool_name = resp.get("tool")
                tool = self.tools.get(tool_name)
                if not tool:
                    obs = f"Error: unknown tool '{tool_name}'"
                else:
                    try:
                        tool_result = await tool.run(resp.get("input", {}), view)
                        obs = str(tool_result) if not isinstance(tool_result, str) else tool_result
                    except Exception as e:
                        obs = f"Tool error: {str(e)}"
                messages.append({"role": "assistant", "content": json.dumps(resp)})
                messages.append({"role": "user", "content": f"Observation: {obs}"})
            else:
                messages.append({"role": "user", "content": "Invalid format. Use tool_call or final_answer."})

        raise TimeoutError(f"ReActWorker {self.agent_id} exceeded max steps")
