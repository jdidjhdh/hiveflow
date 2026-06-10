# Architecture

Deep dive into HiveFlow's architecture and design decisions.

---

## Overview

HiveFlow is a **three-layer** multi-agent orchestration system:

```
┌─────────────────────────────────────────────────────────────┐
│                    HiveFlow Studio (Web UI)                 │
│  Visual workflow builder, analytics, plugin marketplace     │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API + WebSocket (SSE)
┌─────────────────────────────▼───────────────────────────────┐
│                   HiveFlow Agent Runtime                    │
│  ReAct workers, intent parsing, memory management, tools    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    HiveFlow Core Engine                     │
│  Event Bus, Scheduler, Blackboard, Cell, Orchestrator       │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Core Engine

The foundation layer provides the fundamental primitives:

### Event Bus
- Publish/subscribe pattern for decoupled communication
- Event types: `intent.new`, `task.assigned`, `task.completed`, `task.failed`
- Supports both sync and async subscribers

### Scheduler
- Three scheduling strategies: least-loaded, auction, global load-aware
- Manages task distribution across worker pools
- Configurable concurrency limits

### Cell
- Supervision tree pattern
- Manages worker lifecycle (start, idle, working, stop)
- Handles worker failure recovery

### Blackboard
- Shared memory for agent communication
- Permission-based access control (read/write keys)
- Multiple backends: in-memory, Redis, encrypted

### Orchestrator
- DAG orchestrator for static workflows
- Dynamic orchestrator for runtime plan generation
- Cognitive orchestrator for adaptive routing

---

## Layer 2: Agent Runtime

Builds on Core to provide intelligent agent behavior:

### ReAct Worker
- Reasoning + Acting loop
- Tool use with MCP protocol
- Self-correction on failure

### Intent Parser
- Parses user input into structured intents
- Extracts required skills and context
- Supports multi-turn conversations

### Memory Manager
- Short-term memory (context window)
- Long-term memory (vector store)
- Episodic memory (interaction history)

### Tools
- Blackboard tools (read/write/search)
- Code execution (sandboxed)
- File I/O
- HTTP requests
- Web search
- Memory operations

---

## Layer 3: Studio

Visual orchestration and management platform:

### Backend (FastAPI)
- RESTful API for all operations
- WebSocket for real-time streaming
- SQLite/PostgreSQL/MongoDB persistence

### Frontend (React + TypeScript)
- Visual workflow builder (node-based)
- Analytics dashboard
- Plugin marketplace
- LLM configuration management
- Knowledge base management
- Variable and trigger management

---

## Security Model

### Defense in Depth

1. **Input Guards**: Validate and sanitize all incoming data
2. **Output Guards**: Filter and validate all outgoing data
3. **Encrypted Blackboard**: AES-256 encryption for sensitive data
4. **Audit Logging**: Complete trail of all operations
5. **Permission System**: Granular read/write access control

---

## Extensibility

### Custom Backends
Implement abstract base classes for:
- `BlackboardBackend` — Custom storage
- `CheckpointBackend` — Custom state persistence
- `Guard` — Custom validation rules

### Custom Schedulers
Extend `BaseScheduler` for custom scheduling logic.

### Custom Workers
Implement custom worker types with specialized tool sets.

### Plugin System
MCP-compatible plugins for tool integration.

---

## Performance Considerations

- Async-first design throughout
- Connection pooling for external services
- Configurable concurrency limits
- TTL-based cache expiration
- Lazy loading for large data structures
