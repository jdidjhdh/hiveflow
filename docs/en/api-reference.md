# API Reference

Reference for the public `hiveflow` Python API. For tutorials, see [Getting Started](getting-started.md).

---

## HiveFlow

Top-level orchestration engine.

```python
from hiveflow import HiveFlow, HiveFlowConfig

hf = HiveFlow(HiveFlowConfig())
await hf.start()
```

### Methods

| Method | Description |
|--------|-------------|
| `start()` | Start event bus and scheduler |
| `shutdown()` | Stop workers, scheduler, bus, and blackboard |
| `create_agent(agent_id, skills, read_keys, write_keys, task_handler, max_queue_size=None)` | Register and start a worker |
| `register_agent_handler(agent_id, handler)` | Register handler for state restore |
| `save_state()` | Persist agent capabilities to blackboard |
| `restore_state()` | Restore agents from saved state |
| `set_strategy(strategy)` | Replace scheduler selection strategy (async) |

### Attributes

| Attribute | Description |
|-----------|-------------|
| `config` | `HiveFlowConfig` instance |
| `blackboard` | `SecureBlackboard` (audited wrapper) |
| `bus` | `InProcessEventBus` or `RedisEventBus` |
| `scheduler` | `InProcessScheduler` |
| `cell` | `Cell` supervision tree |
| `dag_orchestrator` | Static DAG orchestrator |
| `dynamic_orchestrator` | Runtime-expanding orchestrator |

---

## HiveFlowConfig

```python
@dataclass
class HiveFlowConfig:
    scheduler: SchedulerConfig
    blackboard_type: str = "memory"
    encryption_key_provider: Optional[KeyProvider] = None
    redis_url: Optional[str] = None
    redis_db: int = 0
    worker_max_queue_size: int = 100
    log_level: str = "INFO"
    # ...
```

| Field | Values / Notes |
|-------|----------------|
| `blackboard_type` | `memory`, `ttl_memory`, `redis`, `encrypted` |
| `redis_url` | Required when using Redis blackboard/bus |
| `encryption_key_provider` | Required when `blackboard_type="encrypted"` |

**Class method:** `HiveFlowConfig.from_env(prefix="HIVEFLOW")` — load from environment variables.

---

## ECM

Event-Condition-Messaging unit — the task message passed to agents.

```python
ECM(
    trace_id="trace-1",
    intent="Process order",
    intent_id="intent-1",
    emitter="user",
    required_skills=["process"],
    payload={"order_id": "123"},
    priority="normal",
)
```

---

## Cell & Worker

`Cell` manages worker lifecycle. Prefer `HiveFlow.create_agent()` in application code.

Task handlers receive `(ecm, view)` where `view` is a scoped blackboard view:

```python
async def handler(ecm, view):
    data = await view.get("input_key")
    await view.put("output_key", {"result": data})
    return {"ok": True}
```

---

## Blackboard

| Class | Use case |
|-------|----------|
| `MemoryBlackboard` | Local dev, tests |
| `TTLMemoryBlackboard` | In-memory with TTL |
| `RedisBlackboard` | Distributed deployments |
| `EncryptedBlackboard` | AES encryption at rest |
| `SecureBlackboard` | Audit logging wrapper (used by default in `HiveFlow`) |

System-level keys (orchestrator): `await blackboard.sys_get(key)` / `sys_put(key, value)`.

---

## Scheduler

```python
SchedulerConfig(
    selection_strategy="least_loaded",  # least_loaded | auction | global_load
    default_intent_timeout=60.0,
    auction_timeout=5.0,
)
```

Built-in strategies: `LeastLoadedStrategy`, `AuctionStrategy`, `GlobalLoadAwareStrategy`.

Custom strategies subclass `SelectionStrategy` and implement:

```python
async def select(self, ecm, capabilities, worker_queues) -> List[str]:
    ...
```

---

## HITL (Human-in-the-Loop)

| Class | Role |
|-------|------|
| `HITLManager` | Create gates, wait for responses, handle timeouts |
| `HITLGate` | Gate state dataclass |
| `HITLAction` | `APPROVAL`, `REVIEW`, `INPUT`, `CONFIRMATION` |
| `HITLStatus` | `PENDING`, `APPROVED`, `REJECTED`, … |

```python
mgr = HITLManager()
gate = await mgr.create_gate(workflow_id="wf", node_id="n1", action=HITLAction.APPROVAL, prompt="Approve?")
await mgr.respond(gate.gate_id, approved=True)
resolved = await mgr.wait_for_response(gate.gate_id)
```

---

## CheckpointManager

```python
mgr = CheckpointManager(MemoryCheckpointBackend())
cp_id = await mgr.save_checkpoint("wf-1", state={"step": 1})
cp = await mgr.restore_checkpoint(cp_id)
timeline = await mgr.get_checkpoint_timeline("wf-1")
fork_id = await mgr.fork(cp_id, branch_name="experiment")
```

---

## Streaming

| Class | Description |
|-------|-------------|
| `StreamBuffer` | Async producer/consumer event buffer |
| `StreamEvent` | Single event with `type`, `data`, `node_id` |
| `StreamEventType` | `TOKEN`, `THOUGHT`, `TOOL_CALL`, `NODE_START`, `DONE`, … |
| `collect_stream(buffer)` | Drain buffer into a list |

`StreamEvent.to_sse()` formats Server-Sent Events payloads.

---

## Guards

```python
guard = InputGuard(max_length=10000)
result = guard.check(user_text)  # InputGuardResult

validator = OutputValidator(max_length=50000)
result = validator.validate(agent_output)  # OutputValidationResult
```

---

## RAG

```python
processor = DocumentProcessor()
doc = processor.parse_text("...", source="manual")
chunker = TextChunker(chunk_size=500, chunk_overlap=50)
pipeline = RAGPipeline(
    vector_store=MemoryVectorStore(),
    embedding_model=DummyEmbeddingModel(),
    llm_client=client,  # optional
)
await pipeline.add_document(doc, chunker)
result = await pipeline.query("What is AI?")
```

---

## MCP

```python
client = MCPClient(transport="mock")
client.register_tool("echo", lambda args: {"content": args.get("text", "")})
await client.initialize()
tools = await client.list_tools()
result = await client.call_tool("echo", {"text": "hello"})
```

`MCPPluginManager` manages multiple MCP server plugins. `PluginMarketplace` ships built-in plugin specs.

---

## Cognitive Orchestrator

```python
from hiveflow import CognitiveOrchestrator, MockLLMClient

orchestrator = CognitiveOrchestrator(llm_client=MockLLMClient(response='{"plan":[...]}'))
result = await orchestrator.execute(goal="Research and summarize", task_fn=my_task_fn)
```

---

## Evaluation

```python
evaluator = Evaluator()
evaluator.add_criteria("accuracy", "Is the output correct?")
evaluator.add_custom_evaluator("accuracy", my_scorer_fn)
report = await evaluator.evaluate(
    workflow_id="wf-1",
    test_name="demo",
    input_text="...",
    output_text="...",
    expected_output="...",
)

tester = ABTester(evaluator)
comparison = await tester.compare("input", agent_a_fn, agent_b_fn, "test_name")
```

---

## Multimodal

```python
pipeline = MultiModalPipeline()  # defaults to mock processors
image = MediaContent(media_type=MediaType.IMAGE, data=b"...")
analysis = await pipeline.analyze_image(image)
transcript = await pipeline.transcribe_audio(audio)
summary = await pipeline.summarize_video(video)
```
