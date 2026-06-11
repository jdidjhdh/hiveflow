import uuid
import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

from hiveflow import HiveFlow, HiveFlowConfig
try:
    from .core.secure_blackboard import SecureBlackboard
    from .llm.base import LLMClient
    from .memory.manager import MemoryManager
    from .memory.vector_store import VectorStore
    from .intent_parser import IntentParser
    from .orchestrator.cognitive import CognitiveOrchestrator
    from .guardrails.input import InputGuard
    from .guardrails.output import OutputValidator
    from .mcp_skills import register_mcp_plugin_as_skills
except ImportError:
    from core.secure_blackboard import SecureBlackboard
    from llm.base import LLMClient
    from memory.manager import MemoryManager
    from memory.vector_store import VectorStore
    from intent_parser import IntentParser
    from orchestrator.cognitive import CognitiveOrchestrator
    from guardrails.input import InputGuard
    from guardrails.output import OutputValidator
    from mcp_skills import register_mcp_plugin_as_skills

logger = logging.getLogger(__name__)


def ensure_error_writes(handler):
    async def wrapped(ecm, view):
        try:
            return await handler(ecm, view)
        except Exception as e:
            logger.exception(f"Worker task failed: {e}")
            error_result = {"error": str(e)}
            # 优先写入 expectation.state_key (如果存在)
            if hasattr(ecm, 'expectation') and ecm.expectation and ecm.expectation.state_key:
                try:
                    await view.put(ecm.expectation.state_key, error_result)
                except Exception:
                    pass
            # 同时写入标准结果键，确保 orchestrator 能收到错误
            result_key = f"hivemind:result:{ecm.intent_id}"
            try:
                await view.put(result_key, error_result)
            except Exception:
                pass
            return error_result
    return wrapped


@dataclass
class SkillBinding:
    skill_name: str
    agent_id: str
    handler: Callable
    read_keys: Set[str]
    write_keys: Set[str]


@dataclass
class HiveMindConfig:
    hiveflow_config: HiveFlowConfig
    llm: LLMClient
    embedding_llm: LLMClient
    vector_store: VectorStore
    skill_registry: Dict[str, str] = field(default_factory=dict)
    system_prompt: str = "You are a helpful assistant."
    max_replan_attempts: int = 3
    short_term_limit: int = 10
    global_timeout: float = 300.0
    node_result_ttl: float = 600.0
    input_guard: Optional[InputGuard] = None
    output_validator: Optional[OutputValidator] = None
    schedule_retries: int = 3
    schedule_backoff_base: float = 0.5
    enable_result_cleanup: bool = True
    planning_llm: Optional[LLMClient] = None
    execution_llm: Optional[LLMClient] = None
    enable_plan_hitl: bool = False
    hitl_manager: Any = None
    mcp_plugin_ids: List[str] = field(default_factory=list)


class HiveMindApp:
    def __init__(self, config: HiveMindConfig, hiveflow: Optional[HiveFlow] = None):
        self.config = config
        self._owns_core = hiveflow is None
        self.core = hiveflow or HiveFlow(config.hiveflow_config)
        self.blackboard = self.core.blackboard
        self.memory = MemoryManager(self.blackboard, config.vector_store, config.short_term_limit)
        planning_llm = config.planning_llm or config.llm
        self.intent_parser = IntentParser(planning_llm, config.skill_registry)
        self.skill_bindings: Dict[str, SkillBinding] = {}
        self.cognitive_orch: Optional[CognitiveOrchestrator] = None
        self._bg_tasks: Set[asyncio.Task] = set()
        self._plugin_manager = None

    async def create_skill_agent(self, skill_name: str, agent_id: str, handler,
                                 read_keys: Set[str], write_keys: Set[str],
                                 max_queue_size: int = 10):
        if skill_name in self.skill_bindings:
            raise ValueError(f"Skill '{skill_name}' already registered")
        safe_handler = ensure_error_writes(handler)
        worker = await self.core.create_agent(
            agent_id=agent_id, skills={skill_name},
            read_keys=read_keys, write_keys=write_keys,
            task_handler=safe_handler, max_queue_size=max_queue_size
        )
        self.skill_bindings[skill_name] = SkillBinding(skill_name, agent_id, safe_handler, read_keys, write_keys)
        return worker

    async def create_react_skill(
        self,
        skill_name: str,
        agent_id: str,
        tools: List,
        *,
        llm: Optional[LLMClient] = None,
        system_prompt: str = "",
        read_keys: Optional[Set[str]] = None,
        write_keys: Optional[Set[str]] = None,
        max_steps: int = 10,
    ):
        """Register a ReAct-based skill that writes hivemind:result:{intent_id}."""
        try:
            from .worker.react_worker import ReActWorker
        except ImportError:
            from worker.react_worker import ReActWorker

        execution_llm = llm or self.config.execution_llm or self.config.llm
        worker = ReActWorker(
            agent_id=agent_id,
            llm=execution_llm,
            tools=tools,
            system_prompt=system_prompt or self.config.system_prompt,
            max_steps=max_steps,
            memory_manager=self.memory,
        )
        read_keys = read_keys or {"hivemind:result:*", "mcp:*"}
        write_keys = write_keys or {"hivemind:result:*", "mcp:*"}

        async def handler(ecm, view):
            result = await worker.task_handler(ecm, view)
            result_key = f"hivemind:result:{ecm.intent_id}"
            await view.put(result_key, result)
            return result

        await self.create_skill_agent(skill_name, agent_id, handler, read_keys, write_keys)
        if skill_name not in self.config.skill_registry:
            self.config.skill_registry[skill_name] = f"ReAct skill: {skill_name}"
        return worker

    async def register_mcp_skills(self, plugin_manager, plugin_ids: Optional[List[str]] = None) -> List[str]:
        """Expose MCP plugin tools as HiveMind skills."""
        self._plugin_manager = plugin_manager
        ids = plugin_ids if plugin_ids is not None else self.config.mcp_plugin_ids
        registered: List[str] = []
        for plugin_id in ids:
            names = await register_mcp_plugin_as_skills(self, plugin_manager, plugin_id)
            registered.extend(names)
        return registered

    async def start(self):
        if self._owns_core:
            await self.core.start()
        elif not getattr(self.core, "_running", False):
            await self.core.start()
        planning_llm = self.config.planning_llm or self.config.llm
        self.cognitive_orch = CognitiveOrchestrator(
            llm=planning_llm,
            hiveflow=self.core,
            skill_bindings=self.skill_bindings,
            skill_signatures=self.config.skill_registry,
            memory_manager=self.memory,
            intent_parser=self.intent_parser,
            max_replan_attempts=self.config.max_replan_attempts,
            global_timeout=self.config.global_timeout,
            node_result_ttl=self.config.node_result_ttl,
            schedule_retries=self.config.schedule_retries,
            schedule_backoff_base=self.config.schedule_backoff_base,
            hitl_manager=self.config.hitl_manager,
            enable_plan_hitl=self.config.enable_plan_hitl,
        )
        if self._plugin_manager and self.config.mcp_plugin_ids:
            await self.register_mcp_skills(self._plugin_manager)

    async def run_query(self, user_input: str, conversation_id: Optional[str] = None) -> dict:
        if self.config.input_guard:
            await self.config.input_guard.check(user_input)
        if not self.cognitive_orch:
            raise RuntimeError("App not started")

        conv_id = conversation_id or str(uuid.uuid4())
        exec_result = await self.cognitive_orch.execute(user_input, conv_id)
        intent_id = exec_result["intent_id"]
        results = exec_result.get("results", {})

        if exec_result.get("status") == "plan_rejected":
            return {
                "answer": "Execution plan was not approved.",
                "raw_results": results,
                "intent_id": intent_id,
                "status": "plan_rejected",
                "reason": exec_result.get("reason"),
            }

        final_answer = results.get("final_answer", "No final answer generated.")
        if self.config.output_validator:
            if not await self.config.output_validator.validate(final_answer, context=user_input):
                final_answer = "Output validation failed."

        self.memory.add_to_short_term("user", user_input)
        self.memory.add_to_short_term("assistant", str(final_answer))

        task = asyncio.create_task(self.memory.summarize_and_remember(conv_id, self.config.llm))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

        if self.config.enable_result_cleanup:
            cleanup_task = asyncio.create_task(self._cleanup_results(intent_id, list(results.keys())))
            self._bg_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(self._bg_tasks.discard)

        return {"answer": final_answer, "raw_results": results, "intent_id": intent_id, "status": "completed"}

    async def plan_only(self, user_input: str, conversation_id: Optional[str] = None) -> dict:
        if not self.cognitive_orch:
            raise RuntimeError("App not started")
        conv_id = conversation_id or str(uuid.uuid4())
        return await self.cognitive_orch.plan_only(user_input, conv_id)

    async def execute_plan(
        self,
        graph_spec: Dict,
        user_input: str = "",
        conversation_id: Optional[str] = None,
    ) -> dict:
        if not self.cognitive_orch:
            raise RuntimeError("App not started")
        conv_id = conversation_id or str(uuid.uuid4())
        exec_result = await self.cognitive_orch.execute_plan(
            graph_spec, user_input, conv_id,
        )
        intent_id = exec_result["intent_id"]
        results = exec_result.get("results", {})
        final_answer = results.get("final_answer", "No final answer generated.")
        return {
            "answer": final_answer,
            "raw_results": results,
            "intent_id": intent_id,
            "status": exec_result.get("status", "completed"),
        }

    def get_replay_debugger(self):
        try:
            from .replay import ReplayDebugger
        except ImportError:
            from replay import ReplayDebugger
        return ReplayDebugger(self.blackboard)

    async def _cleanup_results(self, intent_id: str, node_names: list):
        for name in node_names:
            key = f"hivemind:result:{intent_id}:{name}"
            try:
                await self.blackboard.sys_delete(key)
            except Exception:
                logger.debug(f"Failed to delete key {key}, may already be removed")

    async def shutdown(self):
        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        if self._owns_core:
            await self.core.shutdown()
