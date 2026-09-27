import difflib
import json
import logging
import re
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hiveflow.checkpoint import CheckpointManager

try:
    from .tools import Tool
except ImportError:
    from worker.tools import Tool


logger = logging.getLogger(__name__)


def _repair_json(text: str) -> dict | None:
    """
    🔒 SECURITY FIX: Attempt to repair common JSON format issues from LLM output.
    
    Handles:
    - Markdown code blocks (```json...```)
    - Trailing commas
    - Missing quotes around keys
    - Single quotes instead of double quotes
    - Comments in JSON
    
    Returns:
        dict if successfully repaired and parsed, None otherwise
    """
    json_text = text.strip()
    
    # 1. Extract from markdown code blocks
    if "```" in json_text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_text)
        if match:
            json_text = match.group(1).strip()
    
    # 2. Remove trailing commas before } and ]
    json_text = re.sub(r',\s*([}\]])', r'\1', json_text)
    
    # 3. Remove JavaScript-style comments
    json_text = re.sub(r'//.*$', '', json_text, flags=re.MULTILINE)
    json_text = re.sub(r'/\*[\s\S]*?\*/', '', json_text)
    
    # 4. Convert single quotes to double quotes (for string values)
    # Be careful not to break valid JSON with escaped quotes
    json_text = re.sub(r"'([^']*)'", r'"\1"', json_text)
    
    # 5. Add missing quotes around unquoted keys (common in sloppy JSON)
    # Match pattern like {key: or ,key: and add quotes
    json_text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', json_text)
    
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def _fuzzy_match_tool(tool_name: str, available_tools: dict[str, Tool], cutoff: float = 0.6) -> str | None:
    """
    🔧 PERFORMANCE FIX: Fuzzy match tool names to handle LLM hallucination.
    
    When LLM generates a slightly incorrect tool name (e.g., "search_web" vs "web_search"),
    this function attempts to find the closest match using difflib.
    
    Args:
        tool_name: The (potentially incorrect) tool name from LLM
        available_tools: Dict of available tool name -> Tool objects
        cutoff: Minimum similarity ratio (0.6 = 60% similar)
    
    Returns:
        The matched tool name if found, None otherwise
    
    Examples:
        _fuzzy_match_tool("search_web", {"web_search": Tool, "file_read": Tool})
        -> "web_search" (if similarity >= 0.6)
    """
    tool_names = list(available_tools.keys())
    
    # First, check for exact match (fast path)
    if tool_name in available_tools:
        return tool_name
    
    # Try fuzzy match with difflib
    matches = difflib.get_close_matches(tool_name, tool_names, n=1, cutoff=cutoff)
    
    if matches:
        matched = matches[0]
        similarity = difflib.SequenceMatcher(None, tool_name, matched).ratio()
        logger.info(f"Fuzzy matched tool '{tool_name}' -> '{matched}' (similarity: {similarity:.2f})")
        return matched
    
    return None


class ReActWorker:
    def __init__(self, agent_id: str, llm, tools: list[Tool],
                 system_prompt: str = "You are a helpful AI assistant.",
                 max_steps: int = 10,
                 memory_manager: Optional = None,
                 max_message_history: int = 20,
                 action_log_max: int = 5,
                 checkpoint_manager: Optional["CheckpointManager"] = None):
        self.agent_id = agent_id
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.memory = memory_manager
        self.max_message_history = max_message_history
        # 🔄 P0 FIX: Track action logs for compression
        self.action_log_max = action_log_max  # Max action logs to keep in memory
        self._action_logs: list[dict[str, Any]] = []  # Tool call history
        self._action_count: int = 0  # Total action count for compression trigger
        # 🔄 NEW: Checkpoint manager for partial state saving
        self.checkpoint_manager = checkpoint_manager

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
            # 🔧 PERFORMANCE FIX: Improved message truncation with rolling summary
            # Instead of simply discarding middle messages, preserve:
            # 1. All System prompts (critical instructions)
            # 2. Recent N messages (current context)
            # 3. Rolling summary of discarded messages (key information preserved)
            if len(messages) > self.max_message_history:
                messages = self._smart_truncate_messages(messages)
            
            try:
                resp = await self.llm.complete_json(messages)
            except ValueError as e:
                # 🔒 SECURITY FIX: Attempt JSON repair before giving up
                logger.warning(f"ReActWorker {self.agent_id} JSON parse failed, attempting repair: {e}")
                raw_text = await self.llm.complete(messages)
                repaired = _repair_json(raw_text)
                if repaired:
                    resp = repaired
                    logger.info(f"ReActWorker {self.agent_id} successfully repaired JSON")
                else:
                    logger.error(f"ReActWorker {self.agent_id} JSON repair failed")
                    return {"error": "Failed to generate valid action after repair attempts"}

            if resp.get("type") == "final_answer":
                return resp["content"]
            elif resp.get("type") == "tool_call":
                tool_name = resp.get("tool")
                tool_input = resp.get("input", {})
                obs = ""
                
                # 🔧 PERFORMANCE FIX: Try fuzzy match if exact tool not found
                tool = self.tools.get(tool_name)
                if not tool:
                    matched_name = _fuzzy_match_tool(tool_name, self.tools)
                    if matched_name:
                        tool = self.tools[matched_name]
                        tool_name = matched_name  # Update for logging
                        obs = f"Note: Tool '{resp.get('tool')}' matched to '{matched_name}'\n"
                    else:
                        obs = f"Error: unknown tool '{tool_name}'. Available: {list(self.tools.keys())}"
                
                # 🔄 P0 FIX: Record action log before execution
                action_entry = {
                    "step": step + 1,
                    "tool": tool_name,
                    "input": tool_input,
                    "matched": matched_name if matched_name else None
                }
                
                if tool:
                    try:
                        tool_result = await tool.run(tool_input, view)
                        obs = obs + str(tool_result) if isinstance(tool_result, str) else str(tool_result)
                        action_entry["result"] = obs[:500] if isinstance(obs, str) else str(obs)[:500]  # Truncate for storage
                        action_entry["status"] = "success"
                    except Exception as e:
                        obs = f"Tool error: {e!s}"
                        action_entry["result"] = str(e)
                        action_entry["status"] = "error"
                
                # 🔄 P0 FIX: Add to action logs and compress if needed
                self._action_logs.append(action_entry)
                self._action_count += 1
                
                # 🔄 P0 FIX: Every 5 steps, compress and archive to Blackboard
                if self._action_count >= 5 and len(self._action_logs) > self.action_log_max:
                    # Archive the oldest logs to Blackboard
                    archive_key = f"hivemind:action_archive:{self.agent_id}:{step + 1}"
                    archived_logs = self._action_logs[:-self.action_log_max]
                    try:
                        await view.put(archive_key, {
                            "archived_at": step + 1,
                            "logs": archived_logs,
                            "compressed": True
                        })
                        logger.info(f"ReActWorker {self.agent_id}: archived {len(archived_logs)} action logs to Blackboard")
                    except Exception as e:
                        logger.warning(f"Failed to archive action logs: {e}")
                    
                    # Keep only the most recent logs
                    self._action_logs = self._action_logs[-self.action_log_max:]
                    self._action_count = 0  # Reset counter
                
                messages.append({"role": "assistant", "content": json.dumps(resp)})
                messages.append({"role": "user", "content": f"Observation: {obs}"})
            else:
                messages.append({"role": "user", "content": "Invalid format. Use tool_call or final_answer."})

        # 🔄 NEW: Save partial state on timeout
        # Save executed steps to Blackboard before raising timeout
        partial_state_key = f"agent:{self.agent_id}:partial_state"
        partial_state = {
            "step_number": step + 1,
            "max_steps": self.max_steps,
            "messages": messages[-20:],  # Keep last 20 messages to avoid bloat
            "tool_calls": [
                {
                    "step": log["step"],
                    "tool": log["tool"],
                    "input": log["input"],
                    "result": log.get("result", ""),
                    "status": log.get("status", "unknown"),
                }
                for log in self._action_logs
            ],
            "partial_result": None,  # No final result yet
            "agent_id": self.agent_id,
        }

        # Save to Blackboard
        try:
            await view.put(partial_state_key, partial_state)
            logger.info(f"ReActWorker {self.agent_id}: saved partial state at step {step + 1}")
        except Exception as e:
            logger.warning(f"ReActWorker {self.agent_id}: failed to save partial state: {e}")

        # Also save via checkpoint manager if available
        if self.checkpoint_manager:
            try:
                workflow_id = getattr(ecm, 'workflow_id', f"react_{self.agent_id}")
                await self.checkpoint_manager.save_checkpoint(
                    workflow_id=workflow_id,
                    state={"partial_state": partial_state},
                    metadata={"agent_id": self.agent_id, "step": step + 1, "reason": "timeout"},
                    delta=False,
                )
                logger.info(f"ReActWorker {self.agent_id}: saved checkpoint for partial state")
            except Exception as e:
                logger.warning(f"ReActWorker {self.agent_id}: checkpoint save failed: {e}")

        raise TimeoutError(f"ReActWorker {self.agent_id} exceeded max steps at step {step + 1}. Partial state saved to {partial_state_key}")
    
    def _smart_truncate_messages(self, messages: list[dict]) -> list[dict]:
        """
        🔧 PERFORMANCE FIX: Smart message truncation that preserves critical information.
        
        Strategy:
        1. Keep ALL system messages (instructions, tools, context)
        2. Keep last N user/assistant pairs (recent conversation)
        3. Summarize discarded middle messages into one system message
        
        This prevents losing early instructions while maintaining context limit.
        """
        # Separate message types
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_assistant_msgs = [m for m in messages if m["role"] in ("user", "assistant")]
        
        # Calculate how many recent messages to keep
        max_non_system = self.max_message_history - len(system_msgs)
        keep_recent = min(max_non_system, 6)  # Keep last 3 pairs (6 messages)
        
        if len(user_assistant_msgs) <= keep_recent:
            # No truncation needed
            return messages
        
        # Messages to be summarized (middle portion)
        discarded = user_assistant_msgs[:-keep_recent]
        recent = user_assistant_msgs[-keep_recent:]
        
        # Create rolling summary of discarded messages
        summary_parts = []
        for m in discarded:
            role = m["role"]
            content = m["content"]
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "...(truncated)"
            summary_parts.append(f"{role}: {content}")
        
        summary_msg = {
            "role": "system",
            "content": f"Previous conversation summary:\n" + "\n".join(summary_parts[-5:])  # Last 5 of discarded
        }
        
        # Reconstruct: system + summary + recent
        return system_msgs + [summary_msg] + recent

    async def resume_from_partial(self, ecm, view, partial_state_key: str = None) -> Any:
        """
        🔄 NEW: Resume execution from a previously saved partial state.

        This method allows continuing execution from where a previous ReActWorker
        timed out, using the saved intermediate state.

        Args:
            ecm: Execution context manager
            view: Blackboard view
            partial_state_key: Key to retrieve partial state (default: agent:{agent_id}:partial_state)

        Returns:
            Final result from resumed execution

        Raises:
            ValueError: If no partial state found or invalid state format
            TimeoutError: If resumed execution also exceeds max steps
        """
        # Determine partial state key
        if not partial_state_key:
            partial_state_key = f"agent:{self.agent_id}:partial_state"

        # Retrieve partial state from Blackboard
        try:
            partial_state = await view.get(partial_state_key)
        except KeyError:
            raise ValueError(f"No partial state found at key '{partial_state_key}'")

        if not isinstance(partial_state, dict):
            raise ValueError(f"Invalid partial state format: expected dict, got {type(partial_state)}")

        # Validate required fields
        required_fields = ["step_number", "messages", "tool_calls"]
        missing_fields = [f for f in required_fields if f not in partial_state]
        if missing_fields:
            raise ValueError(f"Partial state missing required fields: {missing_fields}")

        # Restore execution context
        task_input = ecm.payload.get("query") or getattr(ecm, 'user_query', '') or str(ecm.payload)
        input_keys = ecm.payload.get("input_keys", {})

        # Read upstream dependencies
        input_data = {}
        for name, key in input_keys.items():
            try:
                input_data[name] = await view.get(key)
            except (KeyError, PermissionError):
                input_data[name] = f"<unavailable: {key}>"

        # Initialize messages from partial state
        messages = partial_state["messages"]

        # Add resume context message
        last_step = partial_state["step_number"]
        tool_calls_summary = []
        for tc in partial_state.get("tool_calls", [])[-5:]:
            tool_calls_summary.append(
                f"Step {tc['step']}: {tc['tool']} -> {tc.get('status', 'unknown')}"
            )

        messages.append({
            "role": "system",
            "content": (
                f"⚠️ Resuming execution from step {last_step}.\n"
                f"Recent tool calls:\n" + "\n".join(tool_calls_summary) + "\n"
                f"Continue from where you stopped."
            )
        })

        # Calculate remaining steps
        remaining_steps = self.max_steps - last_step
        if remaining_steps <= 0:
            raise ValueError(f"Cannot resume: no remaining steps (last_step={last_step}, max_steps={self.max_steps})")

        # Restore action logs
        self._action_logs = [
            {
                "step": tc["step"],
                "tool": tc["tool"],
                "input": tc["input"],
                "result": tc.get("result", ""),
                "status": tc.get("status", "unknown"),
            }
            for tc in partial_state.get("tool_calls", [])
        ]
        self._action_count = len(self._action_logs)

        logger.info(f"ReActWorker {self.agent_id}: resuming from step {last_step} with {remaining_steps} remaining steps")

        # Continue execution loop
        for step_offset in range(remaining_steps):
            current_step = last_step + step_offset

            # 🔧 PERFORMANCE FIX: Message truncation
            if len(messages) > self.max_message_history:
                messages = self._smart_truncate_messages(messages)

            try:
                resp = await self.llm.complete_json(messages)
            except ValueError as e:
                # 🔒 SECURITY FIX: Attempt JSON repair
                logger.warning(f"ReActWorker {self.agent_id} JSON parse failed, attempting repair: {e}")
                raw_text = await self.llm.complete(messages)
                repaired = _repair_json(raw_text)
                if repaired:
                    resp = repaired
                    logger.info(f"ReActWorker {self.agent_id} successfully repaired JSON")
                else:
                    logger.error(f"ReActWorker {self.agent_id} JSON repair failed")
                    return {"error": "Failed to generate valid action after repair attempts"}

            if resp.get("type") == "final_answer":
                # Clear partial state on successful completion
                try:
                    await view.delete(partial_state_key)
                    logger.info(f"ReActWorker {self.agent_id}: cleared partial state after successful completion")
                except Exception as e:
                    logger.warning(f"Failed to clear partial state: {e}")

                return resp["content"]
            elif resp.get("type") == "tool_call":
                tool_name = resp.get("tool")
                tool_input = resp.get("input", {})
                obs = ""

                # 🔧 PERFORMANCE FIX: Try fuzzy match
                tool = self.tools.get(tool_name)
                matched_name = None
                if not tool:
                    matched_name = _fuzzy_match_tool(tool_name, self.tools)
                    if matched_name:
                        tool = self.tools[matched_name]
                        tool_name = matched_name
                        obs = f"Note: Tool '{resp.get('tool')}' matched to '{matched_name}'\n"
                    else:
                        obs = f"Error: unknown tool '{tool_name}'. Available: {list(self.tools.keys())}"

                action_entry = {
                    "step": current_step + 1,
                    "tool": tool_name,
                    "input": tool_input,
                    "matched": matched_name if matched_name else None
                }

                if tool:
                    try:
                        tool_result = await tool.run(tool_input, view)
                        obs = obs + str(tool_result) if isinstance(tool_result, str) else str(tool_result)
                        action_entry["result"] = obs[:500] if isinstance(obs, str) else str(obs)[:500]
                        action_entry["status"] = "success"
                    except Exception as e:
                        obs = f"Tool error: {e!s}"
                        action_entry["result"] = str(e)
                        action_entry["status"] = "error"

                # Add to action logs
                self._action_logs.append(action_entry)
                self._action_count += 1

                # Compress if needed
                if self._action_count >= 5 and len(self._action_logs) > self.action_log_max:
                    archive_key = f"hivemind:action_archive:{self.agent_id}:{current_step + 1}"
                    archived_logs = self._action_logs[:-self.action_log_max]
                    try:
                        await view.put(archive_key, {
                            "archived_at": current_step + 1,
                            "logs": archived_logs,
                            "compressed": True
                        })
                        logger.info(f"ReActWorker {self.agent_id}: archived {len(archived_logs)} action logs")
                    except Exception as e:
                        logger.warning(f"Failed to archive action logs: {e}")

                    self._action_logs = self._action_logs[-self.action_log_max:]
                    self._action_count = 0

                messages.append({"role": "assistant", "content": json.dumps(resp)})
                messages.append({"role": "user", "content": f"Observation: {obs}"})
            else:
                messages.append({"role": "user", "content": "Invalid format. Use tool_call or final_answer."})

        # Save new partial state if still timeout
        new_partial_state_key = f"agent:{self.agent_id}:partial_state"
        new_partial_state = {
            "step_number": last_step + remaining_steps,
            "max_steps": self.max_steps,
            "messages": messages[-20:],
            "tool_calls": [
                {
                    "step": log["step"],
                    "tool": log["tool"],
                    "input": log["input"],
                    "result": log.get("result", ""),
                    "status": log.get("status", "unknown"),
                }
                for log in self._action_logs
            ],
            "partial_result": None,
            "agent_id": self.agent_id,
        }

        try:
            await view.put(new_partial_state_key, new_partial_state)
            logger.info(f"ReActWorker {self.agent_id}: saved new partial state at step {last_step + remaining_steps}")
        except Exception as e:
            logger.warning(f"ReActWorker {self.agent_id}: failed to save partial state: {e}")

        raise TimeoutError(
            f"ReActWorker {self.agent_id} exceeded max steps at step {last_step + remaining_steps}. "
            f"Partial state updated at {new_partial_state_key}"
        )
