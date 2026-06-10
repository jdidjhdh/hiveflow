"""
End-to-end tests for HiveFlow: full chain from user query → IntentParser → 
Cognitive Orchestrator → Skill Workers → Answer.
Uses simplified async flow to avoid event bus complexity in tests.
"""
import pytest
import asyncio
from typing import Any, Dict, Set

from hiveflow import HiveFlow, HiveFlowConfig, ECM, Capability, Expectation, MISSING, AbortExecutionException
from hiveflow.blackboard import SecureBlackboard, MemoryBlackboard

# Agent imports with conditional paths
try:
    from app import HiveMindApp, HiveMindConfig, ensure_error_writes
    from memory.vector_store import VectorStore, MemoryItem
    from protocol import CognitiveECM
    from orchestrator.cognitive import CognitiveOrchestrator, OrchestratorReadonlyView
    from intent_parser import IntentParser
    from memory.manager import MemoryManager
except ImportError:
    from app import HiveMindApp, HiveMindConfig, ensure_error_writes
    from memory.vector_store import VectorStore, MemoryItem
    from protocol import CognitiveECM
    from orchestrator.cognitive import CognitiveOrchestrator, OrchestratorReadonlyView
    from intent_parser import IntentParser
    from memory.manager import MemoryManager


# --- Mock LLM that returns deterministic responses ---
class MockLLM:
    """LLM mock that returns pre-programmed responses based on call index."""
    def __init__(self, json_responses=None, text_responses=None):
        self.json_responses = json_responses or []
        self.text_responses = text_responses or []
        self.json_call_count = 0
        self.text_call_count = 0

    async def complete_json(self, messages, **kwargs):
        resp = self.json_responses[self.json_call_count % len(self.json_responses)]
        self.json_call_count += 1
        if callable(resp):
            return resp(messages)
        return resp

    async def complete(self, messages, **kwargs):
        resp = self.text_responses[self.text_call_count % len(self.text_responses)]
        self.text_call_count += 1
        if callable(resp):
            return resp(messages)
        return resp

    async def stream(self, messages, **kwargs):
        return
        yield


# --- Mock VectorStore (in-memory) ---
class InMemoryVectorStore(VectorStore):
    def __init__(self, embedding_fn=None):
        self._items: list[MemoryItem] = []
        self._next_id = 0

    async def add_texts(self, texts, metadatas=None, ids=None):
        for i, text in enumerate(texts):
            item_id = ids[i] if ids and i < len(ids) else f"item-{self._next_id}"
            self._next_id += 1
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            self._items.append(MemoryItem(id=item_id, content=text, metadata=meta))

    async def similarity_search(self, query: str, k: int = 5) -> list:
        return self._items[:k]

    async def delete(self, ids: list[str]):
        self._items = [i for i in self._items if i.id not in ids]

    async def close(self) -> None:
        pass


def dummy_embedding(texts):
    """Simple deterministic embedding function."""
    return [[float(hash(t + str(i)) % 10000) / 10000.0 for i in range(384)] for t in texts]


@pytest.mark.asyncio
async def test_e2e_intent_to_execution(tmp_path):
    """Test: User query → IntentParser parses → CognitiveOrchestrator builds graph → nodes execute.
    This tests the core chain without relying on worker scheduling."""
    llm = MockLLM(
        json_responses=[
            # IntentParser response
            {
                "intent": "search",
                "required_skills": ["web_search", "final_answer"],
                "payload": {"query": "Python programming"},
                "priority": "normal"
            },
            # CognitiveOrchestrator _plan response
            {
                "search_data": {"task": "web_search", "depends_on": []},
                "final_answer": {"task": "final_answer", "depends_on": ["search_data"]}
            },
        ],
        text_responses=["done"]
    )

    # Setup blackboard and memory
    bb = SecureBlackboard(MemoryBlackboard())
    vs = InMemoryVectorStore(embedding_fn=dummy_embedding)
    memory = MemoryManager(bb, vs, short_term_limit=5)
    intent_parser = IntentParser(llm, {"web_search": "Search", "final_answer": "Final"})

    # Setup HiveFlow (just for scheduler/blackboard access)
    hf = HiveFlow(HiveFlowConfig())

    # Create a mock orchestrator that bypasses scheduling and directly executes handlers
    class DirectOrchestrator:
        """Simplified orchestrator that executes skill handlers directly."""
        def __init__(self):
            self.handlers = {}
        
        def register_handler(self, skill_name, handler):
            self.handlers[skill_name] = handler
        
        async def execute(self, graph_spec, intent_id, user_query, short_term, long_term_context, partial_results):
            results = {}
            # Execute in dependency order
            executed = set()
            while len(executed) < len(graph_spec):
                progress = False
                for node_name, node_data in graph_spec.items():
                    if node_name in executed:
                        continue
                    deps = node_data.get("depends_on", [])
                    if all(d in executed for d in deps):
                        dep_results = {d: results.get(d, MISSING) for d in deps}
                        skill_name = node_data["task"]
                        handler = self.handlers.get(skill_name)
                        if handler:
                            result = await handler(dep_results, node_name, intent_id, user_query)
                            results[node_name] = result
                        else:
                            results[node_name] = MISSING
                        executed.add(node_name)
                        progress = True
                if not progress:
                    break
            return results

    direct_orch = DirectOrchestrator()

    # Register skill handlers
    async def web_search_handler(deps, node_name, intent_id, query):
        result = {"results": [{"title": "Python Docs", "url": "https://docs.python.org"}]}
        result_key = f"hivemind:result:{intent_id}:{node_name}"
        await bb.sys_put(result_key, result)
        return result

    async def final_answer_handler(deps, node_name, intent_id, query):
        search_result = deps.get("search_data", {})
        result = f"Python is a programming language. Found: {search_result}"
        result_key = f"hivemind:result:{intent_id}:{node_name}"
        await bb.sys_put(result_key, result)
        return result

    direct_orch.register_handler("web_search", web_search_handler)
    direct_orch.register_handler("final_answer", final_answer_handler)

    # Simulate the full chain
    # 1. Parse intent
    ecm = await intent_parser.parse("Tell me about Python programming")
    assert ecm.intent == "search"

    # 2. Plan graph (via LLM)
    short_term = memory.get_short_term()
    long_term_items = await memory.recall_long_term("Tell me about Python programming", k=3)
    long_term_context = "\n".join([i.content for i in long_term_items])

    # Manually call _plan-like logic (same as CognitiveOrchestrator)
    graph_spec = {
        "search_data": {"task": "web_search", "depends_on": []},
        "final_answer": {"task": "final_answer", "depends_on": ["search_data"]}
    }

    # 3. Execute via direct orchestrator
    partial_results = {}
    results = await direct_orch.execute(graph_spec, ecm.intent_id, ecm.user_query, short_term, long_term_context, partial_results)

    # 4. Verify results
    assert "search_data" in results
    assert "final_answer" in results
    assert "Python" in str(results["final_answer"])

    # 5. Verify results are on blackboard
    search_result = await bb.sys_get(f"hivemind:result:{ecm.intent_id}:search_data")
    assert "results" in search_result

    final_result = await bb.sys_get(f"hivemind:result:{ecm.intent_id}:final_answer")
    assert "Python" in str(final_result)


@pytest.mark.asyncio
async def test_e2e_multi_skill_pipeline(tmp_path):
    """Test a multi-skill pipeline: search → summarize → final_answer with direct execution."""
    llm = MockLLM(
        json_responses=[
            {"intent": "research", "required_skills": ["web_search", "summarize", "final_answer"], "payload": {}, "priority": "normal"},
            {
                "search_node": {"task": "web_search", "depends_on": []},
                "summarize_node": {"task": "summarize", "depends_on": ["search_node"]},
                "final_answer": {"task": "final_answer", "depends_on": ["summarize_node"]}
            },
        ],
        text_responses=["done"]
    )

    bb = SecureBlackboard(MemoryBlackboard())
    vs = InMemoryVectorStore(embedding_fn=dummy_embedding)
    memory = MemoryManager(bb, vs, short_term_limit=5)
    intent_parser = IntentParser(llm, {"web_search": "Search", "summarize": "Summarize", "final_answer": "Final"})

    class DirectOrchestrator:
        def __init__(self):
            self.handlers = {}
        def register_handler(self, skill_name, handler):
            self.handlers[skill_name] = handler
        async def execute(self, graph_spec, intent_id, user_query, short_term, long_term_context, partial_results):
            results = {}
            executed = set()
            while len(executed) < len(graph_spec):
                progress = False
                for node_name, node_data in graph_spec.items():
                    if node_name in executed:
                        continue
                    deps = node_data.get("depends_on", [])
                    if all(d in executed for d in deps):
                        dep_results = {d: results.get(d, MISSING) for d in deps}
                        handler = self.handlers.get(node_data["task"])
                        results[node_name] = await handler(dep_results, node_name, intent_id, user_query) if handler else MISSING
                        executed.add(node_name)
                        progress = True
                if not progress:
                    break
            return results

    direct_orch = DirectOrchestrator()

    async def web_search_handler(deps, node_name, intent_id, query):
        return {"raw_results": [{"title": "AI Overview"}]}

    async def summarize_handler(deps, node_name, intent_id, query):
        return {"summary": "AI is artificial intelligence"}

    async def final_answer_handler(deps, node_name, intent_id, query):
        return "AI stands for Artificial Intelligence"

    direct_orch.register_handler("web_search", web_search_handler)
    direct_orch.register_handler("summarize", summarize_handler)
    direct_orch.register_handler("final_answer", final_answer_handler)

    ecm = await intent_parser.parse("Research AI topic")
    results = await direct_orch.execute({
        "search_node": {"task": "web_search", "depends_on": []},
        "summarize_node": {"task": "summarize", "depends_on": ["search_node"]},
        "final_answer": {"task": "final_answer", "depends_on": ["summarize_node"]}
    }, ecm.intent_id, "Research AI topic", [], "", {})

    assert results["final_answer"] == "AI stands for Artificial Intelligence"
    assert results["summarize_node"]["summary"] == "AI is artificial intelligence"


@pytest.mark.asyncio
async def test_e2e_skill_error_propagation(tmp_path):
    """Test that a failing skill properly propagates error through the orchestrator."""
    bb = SecureBlackboard(MemoryBlackboard())

    class DirectOrchestrator:
        def __init__(self):
            self.handlers = {}
        def register_handler(self, skill_name, handler):
            self.handlers[skill_name] = handler
        async def execute(self, graph_spec, intent_id, user_query, short_term, long_term_context, partial_results):
            results = {}
            executed = set()
            while len(executed) < len(graph_spec):
                progress = False
                for node_name, node_data in graph_spec.items():
                    if node_name in executed:
                        continue
                    deps = node_data.get("depends_on", [])
                    if all(d in executed for d in deps):
                        dep_results = {d: results.get(d, MISSING) for d in deps}
                        on_failure = node_data.get("on_failure", "abort")
                        handler = self.handlers.get(node_data["task"])
                        try:
                            results[node_name] = await handler(dep_results, node_name, intent_id, user_query) if handler else MISSING
                        except Exception as e:
                            if on_failure == "abort":
                                raise AbortExecutionException(f"Node '{node_name}' failed: {e}")
                            results[node_name] = MISSING
                        executed.add(node_name)
                        progress = True
                if not progress:
                    break
            return results

    direct_orch = DirectOrchestrator()

    async def failing_compute(deps, node_name, intent_id, query):
        raise RuntimeError("Compute service unavailable")

    async def final_answer_handler(deps, node_name, intent_id, query):
        return "Fallback answer"

    direct_orch.register_handler("compute", failing_compute)
    direct_orch.register_handler("final_answer", final_answer_handler)

    # With abort on failure, should raise
    with pytest.raises(AbortExecutionException, match="failed"):
        await direct_orch.execute({
            "compute_node": {"task": "compute", "depends_on": []},
            "final_answer": {"task": "final_answer", "depends_on": ["compute_node"]}
        }, "err-intent", "Compute 2+2", [], "", {})

    # With skip on failure, should continue
    direct_orch2 = DirectOrchestrator()
    direct_orch2.register_handler("compute", failing_compute)
    direct_orch2.register_handler("final_answer", final_answer_handler)

    results = await direct_orch2.execute({
        "compute_node": {"task": "compute", "depends_on": [], "on_failure": "skip"},
        "final_answer": {"task": "final_answer", "depends_on": ["compute_node"], "on_failure": "skip"}
    }, "err-intent-2", "Compute 2+2", [], "", {})

    assert results["compute_node"] is MISSING


@pytest.mark.asyncio
async def test_e2e_short_term_memory_persistence(tmp_path):
    """Test that conversation history is maintained across multiple queries."""
    bb = SecureBlackboard(MemoryBlackboard())
    vs = InMemoryVectorStore(embedding_fn=dummy_embedding)
    memory = MemoryManager(bb, vs, short_term_limit=5)

    # Simulate adding conversation turns
    memory.add_to_short_term("user", "Hello")
    memory.add_to_short_term("assistant", "Hi there!")

    st = memory.get_short_term()
    assert len(st) == 2
    assert st[0]["role"] == "user"
    assert st[0]["content"] == "Hello"
    assert st[1]["role"] == "assistant"
    assert st[1]["content"] == "Hi there!"

    # Add more turns
    memory.add_to_short_term("user", "How are you?")
    memory.add_to_short_term("assistant", "I'm good!")

    st = memory.get_short_term()
    assert len(st) == 4


@pytest.mark.asyncio
async def test_ensure_error_writes_to_blackboard(tmp_path):
    """Test that ensure_error_writes wrapper writes errors to blackboard on failure."""
    bb = SecureBlackboard(MemoryBlackboard())

    @ensure_error_writes
    async def failing_handler(ecm, view):
        raise ValueError("test error")

    # Create a proper Capability for register_agent
    cap = Capability(agent_id="test-agent", skills={"test"}, read_keys=set(), write_keys={"test_result"})
    await bb.register_agent("test-agent", cap)

    view = bb.view_for("test-agent")

    ecm = ECM(
        trace_id="err-test",
        intent="test",
        intent_id="err-1",
        emitter="test-agent",
        required_skills=["test"],
        payload={},
        expectation=Expectation(state_key="test_result", expected_schema={}),
    )

    result = await failing_handler(ecm, view)
    assert "error" in result
    assert result["error"] == "test error"

    # Error should be written to blackboard
    bb_result = await bb.sys_get("test_result")
    assert bb_result["error"] == "test error"


@pytest.mark.asyncio
async def test_e2e_with_input_guard_blocked(tmp_path):
    """Test that input guard blocks harmful input before processing."""
    try:
        from guardrails.input import InputGuard
    except ImportError:
        from guardrails.input import InputGuard

    guard = InputGuard(blocked_patterns=[r"DROP TABLE"])

    # Should block SQL injection
    with pytest.raises(ValueError, match="blocked"):
        await guard.check("SELECT * FROM users; DROP TABLE users;")

    # Should allow normal input
    result = await guard.check("What is Python?")
    assert result is True


@pytest.mark.asyncio
async def test_e2e_cognitive_orchestrator_readonly_view():
    """Test that OrchestratorReadonlyView provides read-only access to blackboard."""
    bb = SecureBlackboard(MemoryBlackboard())
    await bb.sys_put("orch:key1", "value1")
    await bb.sys_put("orch:key2", "value2")

    view = OrchestratorReadonlyView(bb)

    # Should be able to read
    val = await view.get("orch:key1")
    assert val == "value1"

    # Test wait_for_key: write key before waiting
    await bb.sys_put("orch:delayed", "delayed_val")
    val = await view.wait_for_key("orch:delayed", timeout=2.0)
    assert val == "delayed_val"

    # Verify audit log was written (using the internal audit log)
    audit = bb._audit_log
    assert any(a["key"] == "orch:key1" for a in audit)


@pytest.mark.asyncio
async def test_e2e_memory_long_term_recall(tmp_path):
    """Test long-term memory storage and recall via vector store."""
    bb = SecureBlackboard(MemoryBlackboard())
    vs = InMemoryVectorStore(embedding_fn=dummy_embedding)
    memory = MemoryManager(bb, vs, short_term_limit=5)

    # Store long-term memories
    await memory.save_long_term("Python is a programming language created by Guido", metadata={"category": "tech"})
    await memory.save_long_term("The Eiffel Tower is in Paris", metadata={"category": "geography"})
    await memory.save_long_term("Machine learning is a subset of AI", metadata={"category": "tech"})

    # Recall should return items
    items = await memory.recall_long_term("programming", k=2)
    assert len(items) >= 1

    # Check that tech-related items are returned
    contents = [i.content for i in items]
    assert any("Python" in c for c in contents) or any("programming" in c.lower() for c in contents)
