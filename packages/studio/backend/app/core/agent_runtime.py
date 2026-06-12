"""Bootstrap HiveMindApp on top of Studio EngineService."""
import importlib.util
import logging
import os
import sys

_packages_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
_agent_dir = os.path.join(_packages_dir, "agent")
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

logger = logging.getLogger(__name__)
_agent_app_module = None


def _load_agent_app_module():
    """Load packages/agent/app.py without conflicting with Studio's app package."""
    global _agent_app_module
    if _agent_app_module is not None:
        return _agent_app_module
    app_path = os.path.join(_agent_dir, "app.py")
    spec = importlib.util.spec_from_file_location("hivemind_app", app_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load HiveMindApp from {app_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hivemind_app"] = mod
    spec.loader.exec_module(mod)
    _agent_app_module = mod
    return mod


class _InMemoryVectorStore:
    def __init__(self, embedding_fn):
        self.embedding_fn = embedding_fn

    async def add_texts(self, texts, metadatas=None, ids=None):
        return ids or [f"doc_{i}" for i in range(len(texts))]

    async def similarity_search(self, query, k=5, filter_fn=None):
        return []

    async def delete(self, ids):
        pass


async def build_hive_mind_app(engine_service):
    """Create HiveMindApp sharing the Studio HiveFlow engine."""
    agent_mod = _load_agent_app_module()
    HiveMindApp = agent_mod.HiveMindApp
    HiveMindConfig = agent_mod.HiveMindConfig

    planning_llm, execution_llm, llm_source = _resolve_llm_clients()
    logger.info("Agent runtime LLM source: %s", llm_source)

    default_skills = {
        "general": "General-purpose ReAct task execution",
        "summarize": "Summarize upstream context into final answer",
        "final_answer": "Generate final answer",
    }

    config = HiveMindConfig(
        hiveflow_config=engine_service.config,
        llm=planning_llm,
        planning_llm=planning_llm,
        execution_llm=execution_llm,
        embedding_llm=execution_llm,
        vector_store=_InMemoryVectorStore(embedding_fn=execution_llm.embed),
        skill_registry=dict(default_skills),
        hitl_manager=engine_service.get_hitl_manager(),
        enable_plan_hitl=os.environ.get("HIVEFLOW_PLAN_HITL", "").lower() == "true",
        enable_result_cleanup=True,
    )

    app = HiveMindApp(config, hiveflow=engine_service.engine)
    app._plugin_manager = engine_service.get_plugin_manager()
    await app.start()

    await _register_default_skills(app, execution_llm, llm_source)
    return app


def _resolve_llm_clients():
    from app.core.llm_resolver import resolve_llm_clients as _resolve
    return _resolve()


async def _register_default_skills(app, execution_llm, llm_source: str):
    use_real_llm = llm_source != "echo"

    async def summarize_handler(ecm, view):
        query = ecm.payload.get("query") or getattr(ecm, "user_query", "") or str(ecm.payload)
        deps = ecm.payload.get("input_keys", {})
        parts = []
        for name, key in deps.items():
            try:
                val = await view.get(key)
                parts.append(f"{name}: {val}")
            except (KeyError, PermissionError):
                pass
        context = "\n".join(parts)
        if use_real_llm and execution_llm:
            try:
                prompt = f"Summarize for user query: {query}"
                if context:
                    prompt += f"\n\nContext:\n{context}"
                answer = await execution_llm.complete(
                    [
                        {"role": "system", "content": "You summarize task outputs concisely."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1024,
                )
            except Exception as exc:
                logger.warning("Summarize LLM failed: %s", exc)
                answer = context or str(query)
        else:
            answer = context or str(query)
            if parts:
                answer = "Summary based on upstream:\n" + answer
        payload = {"answer": answer}
        await view.put(f"hivemind:result:{ecm.intent_id}", payload)
        return payload

    await app.create_skill_agent(
        "summarize",
        "studio-summarize",
        summarize_handler,
        read_keys={"hivemind:result:*"},
        write_keys={"hivemind:result:*"},
    )
    await app.create_skill_agent(
        "final_answer",
        "studio-final-answer",
        summarize_handler,
        read_keys={"hivemind:result:*"},
        write_keys={"hivemind:result:*"},
    )

    async def general_handler(ecm, view):
        query = ecm.payload.get("query") or getattr(ecm, "user_query", "") or str(ecm.payload)
        if use_real_llm and execution_llm:
            try:
                text = await execution_llm.complete(
                    [
                        {"role": "system", "content": "You are a general-purpose agent worker."},
                        {"role": "user", "content": str(query)},
                    ],
                    max_tokens=1024,
                )
                payload = {"output": text}
            except Exception as exc:
                logger.warning("General LLM failed: %s", exc)
                payload = {"output": str(query), "llm_error": str(exc)}
        else:
            payload = {"output": str(query)}
        await view.put(f"hivemind:result:{ecm.intent_id}", payload)
        return payload

    await app.create_skill_agent(
        "general",
        "studio-general",
        general_handler,
        read_keys={"hivemind:result:*"},
        write_keys={"hivemind:result:*"},
    )
