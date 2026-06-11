import uuid
import json
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hiveflow import MISSING, AbortExecutionException, Expectation, HITLAction, HITLStatus

if TYPE_CHECKING:
    from ..app import SkillBinding

try:
    from ..protocol import CognitiveECM
except ImportError:
    from protocol import CognitiveECM
try:
    from ..memory import MemoryManager
except ImportError:
    from memory.manager import MemoryManager
try:
    from ..intent_parser import IntentParser
except ImportError:
    from intent_parser import IntentParser
try:
    from ..llm import LLMClient
except ImportError:
    from llm.base import LLMClient

logger = logging.getLogger(__name__)


class OrchestratorReadonlyView:
    def __init__(self, secure):
        self._secure = secure

    async def get(self, key: str) -> Any:
        val = await self._secure.sys_get(key)
        await self._secure._add_audit("sys_get", "__orchestrator__", key)
        return val

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        val = await self._secure.sys_wait_for_key(key, timeout)
        await self._secure._add_audit("sys_wait", "__orchestrator__", key)
        return val


class CognitiveOrchestrator:
    def __init__(self,
                 llm: LLMClient,
                 hiveflow,
                 skill_bindings: Dict[str, 'SkillBinding'],
                 skill_signatures: Dict[str, str],
                 memory_manager: MemoryManager,
                 intent_parser: IntentParser,
                 max_replan_attempts: int = 3,
                 global_timeout: float = 300.0,
                 node_result_ttl: float = 600.0,
                 schedule_retries: int = 3,
                 schedule_backoff_base: float = 0.5,
                 hitl_manager=None,
                 enable_plan_hitl: bool = False):
        self.llm = llm
        self.hive = hiveflow
        self.scheduler = hiveflow.scheduler
        self.blackboard = hiveflow.blackboard
        self.skill_bindings = skill_bindings
        self.skill_signatures = skill_signatures
        self.memory = memory_manager
        self.intent_parser = intent_parser
        self.max_replan_attempts = max_replan_attempts
        self.global_timeout = global_timeout
        self.node_result_ttl = node_result_ttl
        self.schedule_retries = schedule_retries
        self.schedule_backoff_base = schedule_backoff_base
        self.dynamic_orch = hiveflow.dynamic_orchestrator
        self.hitl_manager = hitl_manager
        self.enable_plan_hitl = enable_plan_hitl

    async def execute(self, user_query: str, conversation_id: str = "") -> dict:
        ecm = await self.intent_parser.parse(user_query, conversation_id)
        intent_id = ecm.intent_id

        short_term = self.memory.get_short_term()
        long_term_items = await self.memory.recall_long_term(user_query, k=3)
        long_term_context = "\n".join([i.content for i in long_term_items])

        graph_spec = await self._plan(ecm, short_term, long_term_context)
        graph_spec, rejection = await self._maybe_approve_plan(graph_spec, intent_id, conversation_id)
        if rejection:
            return {
                "intent_id": intent_id,
                "results": {},
                "status": "plan_rejected",
                "reason": rejection,
            }

        partial_results: Dict[str, Any] = {}

        for attempt in range(self.max_replan_attempts):
            if attempt > 0:
                short_term = self.memory.get_short_term()
                long_term_items = await self.memory.recall_long_term(user_query, k=3)
                long_term_context = "\n".join([i.content for i in long_term_items])

            executable_graph = self._build_executable_graph(
                graph_spec, intent_id, user_query,
                short_term, long_term_context, partial_results, ecm.payload
            )

            try:
                results = await self.dynamic_orch.execute(executable_graph, global_timeout=self.global_timeout)
                partial_results.update(results)

                if "final_answer" not in results:
                    logger.error("Graph completed but no 'final_answer' node found")
                    raise AbortExecutionException("Missing final_answer node")

                return {"intent_id": intent_id, "results": partial_results}

            except (AbortExecutionException, Exception) as e:
                logger.exception(f"Orchestration attempt {attempt+1} failed: {e}")
                await self._persist_partial_results(partial_results, intent_id)
                if attempt == self.max_replan_attempts - 1:
                    raise
                diagnosis = await self._diagnose(e, graph_spec, partial_results, ecm)
                graph_spec = await self._replan(
                    ecm, diagnosis, partial_results, short_term, long_term_context, intent_id
                )

        return {"intent_id": intent_id, "results": partial_results}

    async def plan_only(self, user_query: str, conversation_id: str = "") -> dict:
        """Generate TaskGraph plan without executing or HITL."""
        ecm = await self.intent_parser.parse(user_query, conversation_id)
        intent_id = ecm.intent_id
        short_term = self.memory.get_short_term()
        long_term_items = await self.memory.recall_long_term(user_query, k=3)
        long_term_context = "\n".join([i.content for i in long_term_items])
        graph_spec = await self._plan(ecm, short_term, long_term_context)
        return {"intent_id": intent_id, "plan": graph_spec, "status": "planned"}

    async def execute_plan(
        self,
        graph_spec: Dict,
        user_query: str = "",
        conversation_id: str = "",
    ) -> dict:
        """Execute a pre-built TaskGraph without LLM planning or plan HITL."""
        ecm = await self.intent_parser.parse(user_query or "execute plan", conversation_id)
        intent_id = ecm.intent_id
        short_term = self.memory.get_short_term()
        long_term_items = await self.memory.recall_long_term(user_query or "execute plan", k=3)
        long_term_context = "\n".join([i.content for i in long_term_items])
        partial_results: Dict[str, Any] = {}

        for attempt in range(self.max_replan_attempts):
            if attempt > 0:
                short_term = self.memory.get_short_term()
                long_term_items = await self.memory.recall_long_term(user_query, k=3)
                long_term_context = "\n".join([i.content for i in long_term_items])

            executable_graph = self._build_executable_graph(
                graph_spec, intent_id, user_query or "execute plan",
                short_term, long_term_context, partial_results, ecm.payload,
            )
            try:
                results = await self.dynamic_orch.execute(executable_graph, global_timeout=self.global_timeout)
                partial_results.update(results)
                if "final_answer" not in results:
                    raise AbortExecutionException("Missing final_answer node")
                return {"intent_id": intent_id, "results": partial_results, "status": "completed"}
            except (AbortExecutionException, Exception) as e:
                logger.exception(f"execute_plan attempt {attempt + 1} failed: {e}")
                await self._persist_partial_results(partial_results, intent_id)
                if attempt == self.max_replan_attempts - 1:
                    raise
                diagnosis = await self._diagnose(e, graph_spec, partial_results, ecm)
                graph_spec = await self._replan(
                    ecm, diagnosis, partial_results, short_term, long_term_context, intent_id,
                )

        return {"intent_id": intent_id, "results": partial_results, "status": "completed"}

    def _build_executable_graph(self,
                                graph_spec: Dict,
                                intent_id: str,
                                user_query: str,
                                short_term: List,
                                long_term_context: str,
                                partial_results: Dict[str, Any],
                                intent_payload: Dict[str, Any]) -> Dict:
        executable = {}
        for node_name, node_data in graph_spec.items():
            skill_name = node_data["task"]
            binding = self.skill_bindings.get(skill_name)
            if not binding:
                raise ValueError(f"Unknown skill '{skill_name}'")

            on_failure = node_data.get("on_failure", "abort")
            exp_cfg = node_data.get("expectation")

            async def node_task(deps, view, _name=node_name, _skill=skill_name,
                                _intent_id=intent_id, _query=user_query,
                                _st=short_term, _lt=long_term_context,
                                _partial=partial_results, _on_failure=on_failure,
                                _payload=intent_payload, _exp_cfg=exp_cfg):
                # 1. 缓存结果
                cached = _partial.get(_name)
                if cached is not None and cached is not MISSING:
                    return cached

                # 2. 上游缺失处理
                if any(v is MISSING for v in deps.values()):
                    if _on_failure == "abort":
                        raise AbortExecutionException(f"Upstream failure in '{_name}'")
                    else:
                        return MISSING

                node_intent_id = f"{_intent_id}:{_name}"
                result_key = f"hivemind:result:{node_intent_id}"

                input_keys = {
                    dep: f"hivemind:result:{_intent_id}:{dep}" for dep in deps
                }

                task_ecm = CognitiveECM(
                    trace_id=str(uuid.uuid4()),
                    intent=_skill,
                    intent_id=node_intent_id,
                    emitter="cognitive_orchestrator",
                    required_skills=[_skill],
                    payload={
                        "query": _query,
                        "input_keys": input_keys,
                        "context": {"short_term": _st, "long_term": _lt},
                        **_payload
                    },
                    priority="normal",
                    expectation=None,
                    user_query=_query
                )
                if _exp_cfg:
                    task_ecm.expectation = Expectation(
                        state_key=result_key,
                        expected_schema=_exp_cfg.get("schema", {}),
                        validation=_exp_cfg.get("validation", ""),
                        use_json_schema=_exp_cfg.get("use_json_schema", False),
                    )

                # 3. 调度重试 (不吞 CancelledError)
                last_err = None
                for retry in range(self.schedule_retries):
                    try:
                        success = await self.scheduler.schedule(task_ecm)
                        if success:
                            break
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        last_err = e
                        if retry == self.schedule_retries - 1:
                            raise
                    delay = self.schedule_backoff_base * (2 ** retry)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to schedule node '{_name}' after retries")
                    if _on_failure == "abort":
                        raise AbortExecutionException(f"Schedule failure for '{_name}'")
                    return MISSING

                # 4. 等待结果 (Worker 保证成功或错误均写入)
                try:
                    result = await view.wait_for_key(result_key, timeout=120.0)
                    if isinstance(result, dict) and "error" in result:
                        logger.warning(f"Node '{_name}' returned error: {result['error']}")
                        if _on_failure == "abort":
                            raise AbortExecutionException(f"Node '{_name}' failed: {result['error']}")
                        return MISSING
                    result = self._validate_expectation(result, _exp_cfg, _name)
                    _partial[_name] = result
                    return result
                except KeyError:
                    raise TimeoutError(f"Node '{_name}' result not available")
                except Exception:
                    raise

            new_node = dict(node_data)
            new_node["task"] = node_task
            executable[node_name] = new_node
        return executable

    async def _plan(self, ecm, short_term, long_term_context):
        skills_desc = "\n".join([f"- {n}: {d}" for n, d in self.skill_signatures.items()])
        messages = [
            {"role": "system", "content": f"""You are a task planner. Generate a TaskGraph JSON.
Keys = node names. Values:
- task: skill name
- depends_on: list of dependencies
- on_failure: "skip" or "abort" (default "abort")
- expectation: optional {{ required_keys: [], on_violation: "abort"|"warn", schema: {{}} }}
Final node must be "final_answer".
Skills:
{skills_desc}
Conversation: {json.dumps(short_term, ensure_ascii=False)}
Long-term: {long_term_context}
Intent: {ecm.intent}
Params: {json.dumps(ecm.payload, ensure_ascii=False)}"""},
            {"role": "user", "content": "Generate graph JSON."}
        ]
        graph = await self.llm.complete_json(messages)
        if "final_answer" not in graph:
            raise ValueError("Generated graph lacks 'final_answer' node")
        return graph

    async def _maybe_approve_plan(self, graph_spec: Dict, intent_id: str, conversation_id: str):
        if not self.enable_plan_hitl or not self.hitl_manager:
            return graph_spec, None

        gate = await self.hitl_manager.create_gate(
            workflow_id=conversation_id or intent_id,
            node_id="plan_approval",
            action=HITLAction.REVIEW,
            prompt="请审阅执行计划，确认或修改后再运行 Agent。",
            context={"plan": graph_spec, "intent_id": intent_id},
        )
        resolved = await self.hitl_manager.wait_for_response(gate.gate_id)
        if resolved.status not in (HITLStatus.APPROVED, HITLStatus.MODIFIED):
            return None, resolved.status.value

        if isinstance(resolved.human_response, dict) and "plan" in resolved.human_response:
            return resolved.human_response["plan"], None
        return graph_spec, None

    def _validate_expectation(self, result: Any, exp_cfg: Optional[Dict], node_name: str) -> Any:
        if not exp_cfg or not isinstance(result, dict):
            return result
        required = exp_cfg.get("required_keys") or exp_cfg.get("schema", {}).get("required", [])
        for key in required:
            if key not in result:
                msg = f"Expectation violated on '{node_name}': missing '{key}'"
                if exp_cfg.get("on_violation", "warn") == "abort":
                    raise AbortExecutionException(msg)
                logger.warning(msg)
        return result

    async def _diagnose(self, error, graph_spec, partial_results, ecm):
        return await self.llm.complete([
            {"role": "system", "content": "Analyze failure, give short diagnosis."},
            {"role": "user", "content": f"Graph: {json.dumps(graph_spec)}\nPartial: {json.dumps(partial_results, default=str)}\nError: {str(error)}"}
        ])

    async def _replan(self, ecm, diagnosis, partial_results, short_term, long_term_context, intent_id):
        available_keys = [f"hivemind:result:{intent_id}:{n}" for n, v in partial_results.items() if v is not MISSING]
        skills_desc = "\n".join([f"- {n}: {d}" for n, d in self.skill_signatures.items()])
        messages = [
            {"role": "system", "content": f"""Previous graph failed. Generate corrected TaskGraph JSON.
Skills: {skills_desc}
Diagnosis: {diagnosis}
Partial results available at: {json.dumps(available_keys)}
Include "final_answer".
Conversation: {json.dumps(short_term, ensure_ascii=False)}
Long-term: {long_term_context}"""},
            {"role": "user", "content": f"Intent: {ecm.intent}"}
        ]
        graph = await self.llm.complete_json(messages)
        if "final_answer" not in graph:
            raise ValueError("Replanned graph lacks 'final_answer' node")
        return graph

    async def _persist_partial_results(self, results, intent_id):
        for node_name, value in results.items():
            if value is not MISSING:
                key = f"hivemind:result:{intent_id}:{node_name}"
                try:
                    await self.blackboard.sys_put(key, value, ttl=self.node_result_ttl)
                except Exception as e:
                    logger.error(f"Failed to persist {key}: {e}")
