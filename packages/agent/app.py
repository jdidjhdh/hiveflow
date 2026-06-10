import uuid
import asyncio
import logging
from typing import Dict, Optional, Set, Callable
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
except ImportError:
    from core.secure_blackboard import SecureBlackboard
    from llm.base import LLMClient
    from memory.manager import MemoryManager
    from memory.vector_store import VectorStore
    from intent_parser import IntentParser
    from orchestrator.cognitive import CognitiveOrchestrator
    from guardrails.input import InputGuard
    from guardrails.output import OutputValidator

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


class HiveMindApp:
    def __init__(self, config: HiveMindConfig):
        self.config = config
        self.core = HiveFlow(config.hiveflow_config)
        self.blackboard = self.core.blackboard
        self.memory = MemoryManager(self.blackboard, config.vector_store, config.short_term_limit)
        self.intent_parser = IntentParser(config.llm, config.skill_registry)
        self.skill_bindings: Dict[str, SkillBinding] = {}
        self.cognitive_orch: Optional[CognitiveOrchestrator] = None
        self._bg_tasks: Set[asyncio.Task] = set()

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

    async def start(self):
        await self.core.start()
        self.cognitive_orch = CognitiveOrchestrator(
            llm=self.config.llm,
            hiveflow=self.core,
            skill_bindings=self.skill_bindings,
            skill_signatures=self.config.skill_registry,
            memory_manager=self.memory,
            intent_parser=self.intent_parser,
            max_replan_attempts=self.config.max_replan_attempts,
            global_timeout=self.config.global_timeout,
            node_result_ttl=self.config.node_result_ttl,
            schedule_retries=self.config.schedule_retries,
            schedule_backoff_base=self.config.schedule_backoff_base
        )

    async def run_query(self, user_input: str, conversation_id: Optional[str] = None) -> dict:
        if self.config.input_guard:
            await self.config.input_guard.check(user_input)
        if not self.cognitive_orch:
            raise RuntimeError("App not started")

        conv_id = conversation_id or str(uuid.uuid4())
        exec_result = await self.cognitive_orch.execute(user_input, conv_id)
        intent_id = exec_result["intent_id"]
        results = exec_result["results"]

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

        return {"answer": final_answer, "raw_results": results, "intent_id": intent_id}

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
        await self.core.shutdown()
