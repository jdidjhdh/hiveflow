# 第 2 部分 — 工作流

构建多 Agent 流水线、加入人工审批、故障恢复、流式事件，以及 RAG + MCP 工具。

## 2.1 多 Agent 协作（示例 02）

模式：**调研 → 写作 → 审阅**，通过黑板传递数据。

```bash
python examples/02_multi_agent.py
```

每个 Agent：

1. 从黑板读取上游键（`view.get()`）。
2. 处理 ECM payload。
3. 写入下游键（`view.put()`）。

调度顺序由你显式控制 — 按序 schedule ECM，或使用 DAG 编排器自动处理依赖。

```python
# 调研完成后，调度 writer
await hf.scheduler.schedule(ECM(
    trace_id="pipeline-1",
    intent="Write article",
    intent_id="write-1",
    emitter="scheduler",
    required_skills=["write"],
    payload={"topic": "AI Trends 2025"},
))
```

**设计建议：** 当 HITL 可能修改中间结果时，保持黑板键稳定并版本化（如 `article_draft_v2`）。

深度阅读：[多 Agent 辩论 Cookbook](../cookbook/multi-agent-debate.md)。

## 2.2 人机协同 HITL（示例 03）

在不可逆操作（发布、发邮件、部署）前暂停。

```bash
python examples/03_hitl_approval.py
```

Core API：

```python
from hiveflow import HITLManager, HITLAction

hitl = HITLManager()
gate = await hitl.create_gate(
    workflow_id="content-pipeline",
    node_id="publish_review",
    action=HITLAction.APPROVAL,
    prompt="Approve publishing this draft?",
    context={"title": draft["title"], "body": draft["body"]},
)
# 工作流等待直到：
await hitl.respond(gate.gate_id, approved=True, comment="LGTM")
```

在 Studio 打开 **Approvals（人工审批）** 进行批准/拒绝。启用 `HIVEFLOW_PLAN_HITL=true` 时，计划在 `node_id=plan_approval` 处 gated，执行前需审批。

深度阅读：[HITL 审批 Cookbook](../cookbook/hitl-approval.md)。

## 2.3 检查点与时间旅行（示例 04）

保存工作流快照并恢复到先前步骤。

```bash
python examples/04_checkpoint.py
```

适用场景：

- 重试失败步骤，无需重跑昂贵的上游任务。
- 合规行业的审计轨迹。
- Studio **Replay（执行回放）** 页面做事后分析。

深度阅读：[Checkpoint 恢复 Cookbook](../cookbook/checkpoint-recovery.md)。

## 2.4 流式事件（示例 05）

发送类型化 SSE 事件：token、工具调用、节点生命周期。

```bash
python examples/05_streaming.py
```

```python
from hiveflow import StreamBuffer, StreamEvent, StreamEventType, collect_stream

buffer = StreamBuffer()
await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
await buffer.close()
events = await collect_stream(buffer)
```

将 `StreamBuffer` 接到 FastAPI `StreamingResponse` 供浏览器消费。Studio **Tracer（任务追踪）** 通过 WebSocket 接收统一 `intent_id` / `trace_id` 的事件。

## 2.5 RAG 流水线（示例 06）

索引文档、检索片段、可选生成答案。

```bash
python examples/06_rag_pipeline.py
```

典型流程：

1. 创建知识库。
2. 索引文档（标题 + 正文）。
3. 自然语言查询。
4. 检索排序后的来源；接入 `llm_client` 做生成。

深度阅读：[RAG + MCP Cookbook](../cookbook/rag-mcp-pipeline.md)。

## 2.6 MCP 工具（示例 07）

通过 Model Context Protocol 统一工具发现与调用。

```bash
python examples/07_mcp_tools.py
```

注册工具、按名调用、切换 Provider 而无需改 Agent 代码。Studio **Capability Market（能力市场）** 展示已安装的 MCP 插件。

## 2.7 工作流模式总结

| 模式 | 适用场景 | 示例 |
|------|----------|------|
| 顺序流水线 | 固定步骤、清晰交接 | `02_multi_agent.py` |
| HITL 门 | 副作用前人工审批 | `03_hitl_approval.py` |
| 检查点 | 容错、审计 | `04_checkpoint.py` |
| 流式 | 对话 UX、实时进度 | `05_streaming.py` |
| RAG + MCP | 知识 + 外部工具 | `06`、`07` |

## 2.8 练习

1. 在示例 02 的 writer 与 reviewer 之间加入 HITL 门。
2. 在示例 05 中从 mock LLM handler 流式输出 token。
3. 在示例 06 中索引本地 markdown 文件并查询。

## 下一步

→ [第 3 部分 — 进阶](part-3-advanced.md)：认知规划、安全、扩展、插件。
