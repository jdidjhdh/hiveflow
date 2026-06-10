# API Reference

Complete API documentation for HiveFlow.

---

## HiveFlow

### `HiveFlow(config)`

Top-level entry point for the HiveFlow engine.

**Parameters:**
- `config` (`HiveFlowConfig`): Configuration object

**Methods:**

#### `execute_workflow(agents, task)`

Execute a multi-agent workflow.

**Parameters:**
- `agents` (`list[dict]`): List of agent configurations with `id` and `skills`
- `task` (`str`): Task description

**Returns:** Workflow result

---

## HiveFlowConfig

Configuration for the HiveFlow engine.

**Parameters:**
- `llm_provider` (`str`): LLM provider name (`openai`, `anthropic`, `mock`)
- `llm_model` (`str`): Model name
- `llm_api_key` (`str`): API key
- `scheduler_strategy` (`str`): Scheduling strategy (`least_loaded`, `auction`, `global_load`)
- `max_concurrent` (`int`): Maximum concurrent tasks

---

## Cell

Supervision tree managing a pool of workers.

**Methods:**

#### `create_worker(agent_id, skills, read_keys, write_keys, task_handler)`

Create a new worker.

**Parameters:**
- `agent_id` (`str`): Unique agent identifier
- `skills` (`set[str]`): Set of skills
- `read_keys` (`set[str]`): Blackboard read permissions
- `write_keys` (`set[str]`): Blackboard write permissions
- `task_handler` (`callable`): Async function to handle tasks

---

## Blackboard

Shared memory for inter-agent communication.

### Types

- `MemoryBlackboard` — In-memory, fast, non-persistent
- `TTLMemoryBlackboard` — In-memory with expiration
- `RedisBlackboard` — Distributed via Redis
- `SecureBlackboard` — Encrypted with audit logging

**Methods:**

#### `put(agent_id, key, value)`

Write data to the blackboard.

#### `get(agent_id, key)`

Read data from the blackboard.

#### `wait(agent_id, key, timeout)`

Wait for data to appear (blocking with timeout).

---

## Scheduler

Assigns tasks to available workers.

**Strategies:**
- `least_loaded` — Assign to worker with fewest active tasks
- `auction` — Workers bid, best bid wins
- `global_load` — Considers entire system load

---

## EventBus

Publish/subscribe communication.

**Methods:**

#### `subscribe(event_type, handler)`

Subscribe to events.

#### `publish(event_type, data)`

Publish an event.

---

## HITLGate

Human-in-the-Loop approval gate.

**Parameters:**
- `gate_id` (`str`): Unique gate identifier
- `description` (`str`): Gate description
- `timeout` (`int`): Timeout in seconds
- `on_timeout` (`str`): Action on timeout (`auto_approve`, `auto_reject`, `cancel`)

**Methods:**

#### `request_approval(agent_id, data)`

Submit for human approval.

#### `approve(gate_id, reviewer)`

Approve the gate.

#### `reject(gate_id, reviewer, reason)`

Reject the gate.

---

## CheckpointManager

State snapshots and time travel.

**Methods:**

#### `save(workflow_id, state)`

Save workflow state.

#### `restore(workflow_id)`

Restore workflow state.

#### `list_snapshots(workflow_id)`

List available snapshots.

---

## Guards

### InputGuard

Validates and sanitizes input.

**Parameters:**
- `max_length` (`int`): Maximum input length
- `blocked_patterns` (`list[str]`): Patterns to block

### OutputValidator

Validates output before returning.

**Parameters:**
- `allowed_patterns` (`list[str]`): Allowed output patterns
- `max_length` (`int`): Maximum output length

---

## Observability

### StructuredLogger

JSON-formatted structured logging with trace context.

### MetricsCollector

Prometheus-compatible metrics collection.

### Tracer

Distributed tracing support with trace/span context propagation.
