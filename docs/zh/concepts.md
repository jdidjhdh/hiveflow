# 核心概念

本文档介绍 HiveFlow 的基础概念。

## 🏗️ 架构概览

HiveFlow 采用分层架构：

```
┌─────────────────────────────────────┐
│  Application Layer (Studio UI)      │
├─────────────────────────────────────┤
│  Agent Layer (Agent Runtime)        │
├─────────────────────────────────────┤
│  Engine Layer (HiveFlow Core)       │
│  ├── EventBus                       │
│  ├── Scheduler                      │
│  ├── Cell                           │
│  ├── Blackboard                     │
│  └── Orchestrator                   │
└─────────────────────────────────────┘
```

## 🔑 关键概念

### 1. ECM（Event-Condition-Messaging）

HiveFlow 中的基本通信单元：

```python
from hiveflow import ECM

ecm = ECM(
    trace_id="trace-001",      # Unique trace for the entire flow
    intent="process_data",     # What needs to be done
    intent_id="intent-001",    # Unique ID for this intent
    emitter="user",            # Who initiated this
    required_skills=["data"],  # What skills are needed
    payload={"key": "value"},  # Data to process
    priority="normal",         # normal, high, critical
)
```

### 2. Cell 与 Worker

**Cell** 是管理 **Worker** 的监督树：

```python
from hiveflow import Cell

cell = Cell(scheduler=scheduler, blackboard=blackboard)

# Create a worker
worker = await cell.create_worker(
    agent_id="agent-1",
    skills={"greet", "analyze"},
    read_keys={"input"},
    write_keys={"output"},
    task_handler=my_handler,
)
```

**Worker 生命周期：**
- `starting` → `idle` → `working` → `idle` → `stopped`

### 3. Blackboard（黑板）

**Blackboard** 是智能体间通信的共享内存系统：

```python
from hiveflow import MemoryBlackboard

blackboard = MemoryBlackboard()

# Write data
await blackboard.put(agent_id="agent-1", key="result", value={"data": "processed"})

# Read data
value = await blackboard.get(agent_id="agent-2", key="result")

# Wait for data
value = await blackboard.wait(agent_id="agent-2", key="result", timeout=30)
```

**黑板类型：**
- `MemoryBlackboard` — 内存（快速，非持久化）
- `TTLMemoryBlackboard` — 带过期时间的内存黑板
- `RedisBlackboard` — 分布式（需要 Redis）
- `SecureBlackboard` — 加密并带审计日志
- `EncryptedBlackboard` — 全量加密

### 4. Scheduler（调度器）

**Scheduler** 将任务分配给 Worker：

```python
from hiveflow import Scheduler, SchedulerConfig

config = SchedulerConfig(
    strategy="least_loaded",  # least_loaded, auction, global_load
    max_concurrent=10,
)
scheduler = Scheduler(config)
```

**策略：**
- **Least Loaded（最少负载）**：分配给当前活跃任务最少的 Worker
- **Auction（拍卖）**：Worker 对任务竞价，最高出价者获胜
- **Global Load-Aware（全局负载感知）**：考虑整个系统负载

### 5. EventBus（事件总线）

**EventBus** 处理发布/订阅通信：

```python
from hiveflow import EventBus

bus = EventBus()

# Subscribe
await bus.subscribe("task.completed", handler)

# Publish
await bus.publish("task.completed", {"task_id": "123", "result": "success"})
```

**事件类型：**
- `intent.new` — 新 intent 创建
- `task.assigned` — 任务已分配给 Worker
- `task.completed` — 任务完成
- `task.failed` — 任务失败
- `intent.timeout` — Intent 超时

### 6. Orchestrator（编排器）

**Orchestrator** 管理工作流执行：

```python
from hiveflow import DAGOrchestrator, DynamicOrchestrator

# DAG Orchestrator (static workflow)
dag = DAGOrchestrator()

# Dynamic Orchestrator (runtime expansion)
dynamic = DynamicOrchestrator()
```

### 7. Checkpoint（检查点）

**Checkpoint** 支持状态快照与时间旅行：

```python
from hiveflow import CheckpointManager, MemoryCheckpointBackend

checkpoint_mgr = CheckpointManager(
    backend=MemoryCheckpointBackend(),
)

# Save state
await checkpoint_mgr.save(workflow_id="wf-001", state=current_state)

# Restore state
restored = await checkpoint_mgr.restore(workflow_id="wf-001")
```

### 8. HITL（Human-in-the-Loop）

**HITL** 在自动化工作流中引入人工审批：

```python
from hiveflow import HITLManager, HITLGate

hitl_mgr = HITLManager()

# Create gate
gate = HITLGate(
    gate_id="approval",
    description="Requires human review",
    timeout=300,
    on_timeout="auto_approve",  # auto_approve, auto_reject, cancel
)

# Request approval
await gate.request_approval(agent_id="agent-1", data={...})

# Human approves/rejects
await gate.approve(gate_id="approval", reviewer="admin")
await gate.reject(gate_id="approval", reviewer="admin", reason="Needs changes")
```

## 📐 设计原则

1. **抽象优于实现**：所有核心组件均为抽象基类
2. **默认安全**：内置权限、加密与审计日志
3. **可观测性优先**：Trace ID、指标与结构化日志
4. **优雅降级**：Worker 失败时清理资源，Intent 始终得到解析
5. **可扩展性**：自定义后端、调度器与守卫
