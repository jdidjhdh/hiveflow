# API 参考

公开 `hiveflow` Python API 参考。教程请参阅 [快速入门](getting-started.md)。

---

## HiveFlow

顶层编排引擎。

```python
from hiveflow import HiveFlow, HiveFlowConfig

hf = HiveFlow(HiveFlowConfig())
await hf.start()
```

### 方法

| 方法 | 说明 |
|--------|-------------|
| `start()` | 启动事件总线与调度器 |
| `shutdown()` | 停止 Worker、调度器、总线与黑板 |
| `create_agent(agent_id, skills, read_keys, write_keys, task_handler, max_queue_size=None)` | 注册并启动 Worker |
| `register_agent_handler(agent_id, handler)` | 注册状态恢复用的处理器 |
| `save_state()` | 将 Agent 能力持久化到黑板 |
| `restore_state()` | 从已保存状态恢复 Agent |
| `set_strategy(strategy)` | 替换调度器选择策略（async） |

### 属性

| 属性 | 说明 |
|-----------|-------------|
| `config` | `HiveFlowConfig` 实例 |
| `blackboard` | `SecureBlackboard`（带审计的包装器） |
| `bus` | `InProcessEventBus` 或 `RedisEventBus` |
| `scheduler` | `InProcessScheduler` |
| `cell` | `Cell` 监督树 |
| `dag_orchestrator` | 静态 DAG 编排器 |
| `dynamic_orchestrator` | 运行时扩展编排器 |

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

| 字段 | 取值 / 说明 |
|-------|----------------|
| `blackboard_type` | `memory`、`ttl_memory`、`redis`、`encrypted` |
| `redis_url` | 使用 Redis 黑板/总线时必填 |
| `encryption_key_provider` | `blackboard_type="encrypted"` 时必填 |

**类方法：** `HiveFlowConfig.from_env(prefix="HIVEFLOW")` — 从环境变量加载。

---

## ECM

Event-Condition-Messaging 单元 — 传递给 Agent 的任务消息。

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

## Cell 与 Worker

`Cell` 管理 Worker 生命周期。应用代码中优先使用 `HiveFlow.create_agent()`。

任务处理器接收 `(ecm, view)`，其中 `view` 为作用域黑板视图：

```python
async def handler(ecm, view):
    data = await view.get("input_key")
    await view.put("output_key", {"result": data})
    return {"ok": True}
```

---

## Blackboard（黑板）

| 类 | 使用场景 |
|-------|----------|
| `MemoryBlackboard` | 本地开发、测试 |
| `TTLMemoryBlackboard` | 带 TTL 的内存黑板 |
| `RedisBlackboard` | 分布式部署 |
| `EncryptedBlackboard` | 静态 AES 加密 |
| `SecureBlackboard` | 审计日志包装器（`HiveFlow` 默认使用） |

系统级键（编排器）：`await blackboard.sys_get(key)` / `sys_put(key, value)`。

---

## Scheduler（调度器）

```python
SchedulerConfig(
    selection_strategy="least_loaded",  # least_loaded | auction | global_load
    default_intent_timeout=60.0,
    auction_timeout=5.0,
)
```

内置策略：`LeastLoadedStrategy`、`AuctionStrategy`、`GlobalLoadAwareStrategy`。

自定义策略继承 `SelectionStrategy` 并实现：

```python
async def select(self, ecm, capabilities, worker_queues) -> List[str]:
    ...
```

---

## HITL（Human-in-the-Loop）

| 类 | 角色 |
|-------|------|
| `HITLManager` | 创建门控、等待响应、处理超时 |
| `HITLGate` | 门控状态 dataclass |
| `HITLAction` | `APPROVAL`、`REVIEW`、`INPUT`、`CONFIRMATION` |
| `HITLStatus` | `PENDING`、`APPROVED`、`REJECTED`、… |

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

## Streaming（流式）

| 类 | 说明 |
|-------|-------------|
| `StreamBuffer` | 异步生产者/消费者事件缓冲 |
| `StreamEvent` | 单个事件，含 `type`、`data`、`node_id` |
| `StreamEventType` | `TOKEN`、`THOUGHT`、`TOOL_CALL`、`NODE_START`、`DONE`、… |
| `collect_stream(buffer)` | 将缓冲排空为列表 |

`StreamEvent.to_sse()` 格式化 Server-Sent Events 载荷。

---

## Guards（守卫）

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

`MCPPluginManager` 管理多个 MCP 服务器插件。`PluginMarketplace` 提供内置插件规格。

---

## Cognitive Orchestrator（认知编排器）

```python
from hiveflow import CognitiveOrchestrator, MockLLMClient

orchestrator = CognitiveOrchestrator(llm_client=MockLLMClient(response='{"plan":[...]}'))
result = await orchestrator.execute(goal="Research and summarize", task_fn=my_task_fn)
```

---

## Evaluation（评估）

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

## Multimodal（多模态）

```python
pipeline = MultiModalPipeline()  # defaults to mock processors
image = MediaContent(media_type=MediaType.IMAGE, data=b"...")
analysis = await pipeline.analyze_image(image)
transcript = await pipeline.transcribe_audio(audio)
summary = await pipeline.summarize_video(video)
```
