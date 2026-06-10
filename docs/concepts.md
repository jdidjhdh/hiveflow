# Core Concepts

This document explains the fundamental concepts of HiveFlow.

## 🏗️ Architecture Overview

HiveFlow is built on a layered architecture:

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

## 🔑 Key Concepts

### 1. ECM (Event-Condition-Messaging)

The fundamental communication unit in HiveFlow:

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

### 2. Cell & Worker

A **Cell** is a supervision tree that manages **Workers**:

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

**Worker Lifecycle:**
- `starting` → `idle` → `working` → `idle` → `stopped`

### 3. Blackboard

The **Blackboard** is the shared memory system for inter-agent communication:

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

**Blackboard Types:**
- `MemoryBlackboard` - In-memory (fast, non-persistent)
- `TTLMemoryBlackboard` - In-memory with expiration
- `RedisBlackboard` - Distributed (requires Redis)
- `SecureBlackboard` - Encrypted with audit logging
- `EncryptedBlackboard` - Full encryption

### 4. Scheduler

The **Scheduler** assigns tasks to workers:

```python
from hiveflow import Scheduler, SchedulerConfig

config = SchedulerConfig(
    strategy="least_loaded",  # least_loaded, auction, global_load
    max_concurrent=10,
)
scheduler = Scheduler(config)
```

**Strategies:**
- **Least Loaded**: Assigns to worker with fewest active tasks
- **Auction**: Workers bid on tasks, best bid wins
- **Global Load-Aware**: Considers entire system load

### 5. EventBus

The **EventBus** handles publish/subscribe communication:

```python
from hiveflow import EventBus

bus = EventBus()

# Subscribe
await bus.subscribe("task.completed", handler)

# Publish
await bus.publish("task.completed", {"task_id": "123", "result": "success"})
```

**Event Types:**
- `intent.new` - New intent created
- `task.assigned` - Task assigned to worker
- `task.completed` - Task finished
- `task.failed` - Task failed
- `intent.timeout` - Intent timed out

### 6. Orchestrator

The **Orchestrator** manages workflow execution:

```python
from hiveflow import DAGOrchestrator, DynamicOrchestrator

# DAG Orchestrator (static workflow)
dag = DAGOrchestrator()

# Dynamic Orchestrator (runtime expansion)
dynamic = DynamicOrchestrator()
```

### 7. Checkpoint

**Checkpoints** enable state snapshots and time travel:

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

### 8. HITL (Human-in-the-Loop)

**HITL** enables human approval in automated workflows:

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

## 📐 Design Principles

1. **Abstraction over Implementation**: All core components are abstract base classes
2. **Security by Default**: Permissions, encryption, and audit logging built-in
3. **Observability First**: Trace IDs, metrics, and structured logging
4. **Graceful Degradation**: Workers clean up on failure, intents always resolved
5. **Extensibility**: Custom backends, schedulers, and guards
