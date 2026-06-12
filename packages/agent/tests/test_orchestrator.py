import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from hiveflow import HiveFlow, HiveFlowConfig, Expectation
from core.secure_blackboard import SecureBlackboard, MemoryBlackboard
from memory.manager import MemoryManager
from memory.vector_store import ChromaVectorStore
from intent_parser import IntentParser
from orchestrator.cognitive import CognitiveOrchestrator, OrchestratorReadonlyView
from protocol import CognitiveECM


# --- Mock LLM ---
class MockLLM:
    def __init__(self, json_responses=None, text_responses=None):
        self.json_responses = json_responses or []
        self.text_responses = text_responses or []
        self.json_call_count = 0
        self.text_call_count = 0

    async def complete_json(self, messages):
        resp = self.json_responses[self.json_call_count % len(self.json_responses)]
        self.json_call_count += 1
        return resp

    async def complete(self, messages, **kwargs):
        resp = self.text_responses[self.text_call_count % len(self.text_responses)]
        self.text_call_count += 1
        return resp

    async def stream(self, messages, **kwargs):
        return
        yield


# --- Mock EventBus ---
class MockEventBus:
    def __init__(self):
        self._handlers = {}

    async def start(self):
        pass

    async def publish(self, topic, msg):
        pass

    async def subscribe(self, topic, handler):
        self._handlers[topic] = handler

    async def unsubscribe(self, topic, handler):
        self._handlers.pop(topic, None)

    async def close(self):
        pass


def simple_embedding_fn(texts):
    return [[float(hash(t + str(i)) % 10000) / 10000.0 for i in range(384)] for t in texts]


@pytest.fixture
def mock_hiveflow(tmp_path):
    """Create a minimal HiveFlow instance with mocked components."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)

    # Override the event bus and scheduler with mock-compatible versions
    mock_bus = MockEventBus()
    hf.bus = mock_bus
    hf.scheduler.bus = mock_bus

    return hf


@pytest.fixture
def memory_manager(tmp_path):
    bb = SecureBlackboard(MemoryBlackboard())
    vs = ChromaVectorStore(path=str(tmp_path / "chroma"), embedding_fn=simple_embedding_fn)
    return MemoryManager(bb, vs, short_term_limit=5)


@pytest.fixture
def intent_parser():
    llm = MockLLM(json_responses=[{
        "intent": "search",
        "required_skills": ["web_search"],
        "payload": {"query": "test"},
        "priority": "normal"
    }])
    return IntentParser(llm, {"web_search": "Search the web", "final_answer": "Generate final answer"})


@pytest.mark.asyncio
async def test_orchestrator_readonly_view():
    bb = SecureBlackboard(MemoryBlackboard())
    await bb.sys_put("test:key", "test_value")

    view = OrchestratorReadonlyView(bb)
    result = await view.get("test:key")
    assert result == "test_value"


@pytest.mark.asyncio
async def test_orchestrator_readonly_view_wait():
    bb = SecureBlackboard(MemoryBlackboard())

    async def delayed_put():
        await asyncio.sleep(0.1)
        await bb.sys_put("delayed:key", "delayed_value")

    asyncio.create_task(delayed_put())

    view = OrchestratorReadonlyView(bb)
    result = await view.wait_for_key("delayed:key", timeout=2.0)
    assert result == "delayed_value"


@pytest.mark.asyncio
async def test_intent_parser_returns_ecm():
    llm = MockLLM(json_responses=[{
        "intent": "greeting",
        "required_skills": ["chat"],
        "payload": {},
        "priority": "low"
    }])
    parser = IntentParser(llm, {"chat": "Chat with user"})
    ecm = await parser.parse("Hello!")
    assert ecm.intent == "greeting"
    assert "chat" in ecm.required_skills
    assert ecm.priority == "low"
    assert ecm.user_query == "Hello!"


@pytest.mark.asyncio
async def test_cognitive_orchestrator_build_graph():
    """Test that _build_executable_graph creates valid node tasks."""
    llm = MockLLM()
    hf = HiveFlow(HiveFlowConfig())

    # Mock scheduler schedule to succeed
    async def mock_schedule(ecm):
        return True

    hf.scheduler.schedule = mock_schedule

    memory = MemoryManager(SecureBlackboard(MemoryBlackboard()), None, short_term_limit=5)

    parser = IntentParser(llm, {"search": "Search", "summarize": "Summarize", "final_answer": "Final"})

    class MockBinding:
        def __init__(self, skill_name):
            self.skill_name = skill_name
            self.agent_id = f"agent-{skill_name}"
            self.handler = AsyncMock(return_value={"result": "ok"})
            self.read_keys = set()
            self.write_keys = set()

    bindings = {
        "search": MockBinding("search"),
        "summarize": MockBinding("summarize"),
        "final_answer": MockBinding("final_answer"),
    }

    # Replace event bus to avoid async issues
    hf.bus = MockEventBus()
    hf.scheduler.bus = hf.bus

    orch = CognitiveOrchestrator(
        llm=llm,
        hiveflow=hf,
        skill_bindings=bindings,
        skill_signatures={"search": "Search", "summarize": "Summarize", "final_answer": "Final"},
        memory_manager=memory,
        intent_parser=parser,
    )

    graph_spec = {
        "search_node": {"task": "search", "depends_on": []},
        "summarize_node": {"task": "summarize", "depends_on": ["search_node"]},
        "final_answer": {"task": "final_answer", "depends_on": ["summarize_node"]},
    }

    executable = orch._build_executable_graph(
        graph_spec, "intent-1", "user query", [], "", {}, {}
    )

    assert "search_node" in executable
    assert "summarize_node" in executable
    assert "final_answer" in executable
    assert callable(executable["search_node"]["task"])
    assert executable["search_node"]["depends_on"] == []
    assert executable["summarize_node"]["depends_on"] == ["search_node"]


@pytest.mark.asyncio
async def test_cognitive_orchestrator_unknown_skill():
    llm = MockLLM()
    hf = HiveFlow(HiveFlowConfig())
    memory = MemoryManager(SecureBlackboard(MemoryBlackboard()), None, short_term_limit=5)
    parser = IntentParser(llm, {})

    orch = CognitiveOrchestrator(
        llm=llm,
        hiveflow=hf,
        skill_bindings={},
        skill_signatures={},
        memory_manager=memory,
        intent_parser=parser,
    )

    graph_spec = {
        "node1": {"task": "unknown_skill", "depends_on": []},
    }

    with pytest.raises(ValueError, match="Unknown skill"):
        orch._build_executable_graph(graph_spec, "intent-1", "query", [], "", {}, {})


@pytest.mark.asyncio
async def test_cognitive_orchestrator_on_failure_skip():
    """Test on_failure='skip' returns MISSING on upstream failure."""
    llm = MockLLM()
    hf = HiveFlow(HiveFlowConfig())
    memory = MemoryManager(SecureBlackboard(MemoryBlackboard()), None, short_term_limit=5)
    parser = IntentParser(llm, {"task": "Task"})

    class MockBinding:
        def __init__(self):
            self.skill_name = "task"
            self.agent_id = "agent-task"
            self.handler = AsyncMock(return_value={"result": "ok"})
            self.read_keys = set()
            self.write_keys = set()

    bindings = {"task": MockBinding()}
    hf.bus = MockEventBus()
    hf.scheduler.bus = hf.bus

    orch = CognitiveOrchestrator(
        llm=llm,
        hiveflow=hf,
        skill_bindings=bindings,
        skill_signatures={"task": "Task"},
        memory_manager=memory,
        intent_parser=parser,
    )

    graph_spec = {
        "node1": {"task": "task", "depends_on": ["missing_upstream"], "on_failure": "skip"},
    }

    executable = orch._build_executable_graph(
        graph_spec, "intent-1", "query", [], "", {}, {}
    )

    node_task = executable["node1"]["task"]
    view = MagicMock()

    # Simulate upstream dependency being MISSING
    from hiveflow import MISSING
    deps = {"missing_upstream": MISSING}
    result = await node_task(deps, view)
    assert result is MISSING


def test_normalize_task_graph_unwraps_tasks_wrapper():
    raw = {
        "tasks": {
            "calc": {"task": "calculate", "depends_on": []},
            "answer": {"task": "summarize", "depends_on": ["calc"]},
        }
    }
    normalized = CognitiveOrchestrator._normalize_task_graph(raw)
    assert "final_answer" in normalized


def test_normalize_task_graph_strips_hallucinated_expectation():
    raw = {
        "calc": {"task": "calculate", "depends_on": [], "expectation": {"required_keys": ["result"]}},
        "final_answer": {"task": "summarize", "depends_on": ["calc"]},
    }
    normalized = CognitiveOrchestrator._normalize_task_graph(raw)
    assert "expectation" not in normalized["calc"]


def test_normalize_task_graph_unwraps_nodes_wrapper():
    raw = {
        "nodes": {
            "calc": {"task": "calculate", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["calc"]},
        }
    }
    normalized = CognitiveOrchestrator._normalize_task_graph(raw)
    assert "final_answer" in normalized
    assert normalized["final_answer"]["task"] == "summarize"


def test_normalize_task_graph_renames_unique_sink_to_final_answer():
    raw = {
        "calc": {"task": "calculate", "depends_on": []},
        "summary": {"task": "summarize", "depends_on": ["calc"]},
    }
    normalized = CognitiveOrchestrator._normalize_task_graph(raw)
    assert "final_answer" in normalized
    assert "summary" not in normalized
    assert normalized["final_answer"]["task"] == "summarize"


@pytest.mark.asyncio
async def test_replan_normalizes_nested_graph_without_final_answer_key(mock_hiveflow, memory_manager):
    """H2: replan LLM returns nested nodes without top-level final_answer — must normalize."""
    llm = MockLLM(
        json_responses=[
            {
                "intent": "calc",
                "required_skills": ["calculate", "summarize"],
                "payload": {"expression": "7*8"},
                "priority": "normal",
            },
            {
                "calc_node": {"task": "calculate", "depends_on": []},
                "final_answer": {"task": "summarize", "depends_on": ["calc_node"]},
            },
            {
                "nodes": {
                    "calc_retry": {"task": "calculate", "depends_on": []},
                    "answer": {"task": "summarize", "depends_on": ["calc_retry"]},
                }
            },
        ],
        text_responses=["calc failed"],
    )
    parser = IntentParser(llm, {"calculate": "calc", "summarize": "sum", "final_answer": "final"})
    orch = CognitiveOrchestrator(
        llm=llm,
        hiveflow=mock_hiveflow,
        skill_bindings={},
        skill_signatures={"calculate": "calc", "summarize": "sum", "final_answer": "final"},
        memory_manager=memory_manager,
        intent_parser=parser,
        max_replan_attempts=2,
    )

    graph = await orch._replan(
        ecm=await parser.parse("calc"),
        diagnosis="retry",
        partial_results={},
        short_term=[],
        long_term_context="",
        intent_id="i1",
    )
    assert "final_answer" in graph
