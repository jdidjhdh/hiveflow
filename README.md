# HiveFlow

[![PyPI version](https://img.shields.io/pypi/v/hiveflow.svg)](https://pypi.org/project/hiveflow/)
[![Python](https://img.shields.io/pypi/pyversions/hiveflow.svg)](https://pypi.org/project/hiveflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/hiveflow/hiveflow/actions/workflows/test.yml/badge.svg)](https://github.com/hiveflow/hiveflow/actions/workflows/test.yml)
[![Downloads](https://pepy.tech/badge/hiveflow)](https://pepy.tech/project/hiveflow)

**Lightweight multi-agent orchestration engine** with human-in-the-loop, RAG, MCP protocol support, and cognitive planning.

> HiveFlow transforms how you build, manage, and scale AI agent workflows — from simple tasks to complex multi-agent collaborations with full human oversight.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Cognitive Orchestration** | Dynamic DAG execution with runtime plan generation and adaptive routing |
| 🤝 **Multi-Agent Collaboration** | Event-driven architecture with smart scheduling (least-loaded, auction, load-aware) |
| 👤 **Human-in-the-Loop** | Complete approval workflows with timeout strategies and manual intervention |
| 🔒 **Security First** | Dual guards (input/output), encrypted blackboard, audit logging |
| 📚 **RAG Pipeline** | Multi-source document processing, chunking strategies, vector store integration |
| 🔌 **MCP Protocol** | Model Context Protocol for unified tool integration and plugin marketplace |
| ⏱️ **Time Travel** | Checkpoint snapshots with full state restoration and history replay |
| 📊 **Evaluation** | Built-in benchmarking, A/B testing, and multi-dimensional scoring |
| 🎨 **Studio UI** | Visual workflow builder, analytics dashboard, and plugin marketplace |
| 🔌 **Streaming** | SSE streaming responses with rich event types for real-time feedback |

---

## 🚀 Quick Start

### Installation

```bash
# Basic installation (core only)
pip install hiveflow

# With security features
pip install "hiveflow[security]"

# With LLM providers
pip install "hiveflow[llm]"

# With RAG capabilities
pip install "hiveflow[rag]"

# Full installation
pip install "hiveflow[all]"
```

### 5-Minute Tutorial

```python
from hiveflow import HiveFlow, HiveFlowConfig

# 1. Create the engine
config = HiveFlowConfig(llm_api_key="sk-...")
hf = HiveFlow(config)

# 2. Define a simple workflow
result = await hf.execute_workflow(
    agents=[
        {"id": "researcher", "skills": {"search", "analyze"}},
        {"id": "writer", "skills": {"write", "edit"}},
    ],
    task="Research and write a summary about AI trends in 2025"
)

print(result)
```

### With Human Approval

```python
from hiveflow import HITLGate, HITLStatus

# Create a gate that requires human approval
gate = HITLGate(
    gate_id="content-review",
    description="Review generated content before publishing",
    timeout=300,  # 5 minutes timeout
)

# Agent submits for approval
await gate.request_approval(agent_id="writer", data={"content": "..."})

# Human approves (via UI or API)
await gate.approve(gate_id="content-review", reviewer="admin")
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HiveFlow Studio (Web UI)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │Workflow  │ │Capability│ │Analytics │ │Plugin Market │  │
│  │Builder   │ │Market    │ │Dashboard │ │              │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API + WebSocket
┌─────────────────────────────▼───────────────────────────────┐
│                   HiveFlow Agent Runtime                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ReAct     │ │Intent    │ │Memory    │ │Tools (MCP)   │  │
│  │Worker    │ │Parser    │ │Manager   │ │              │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    HiveFlow Core Engine                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │Cognitive │ │Scheduler │ │Blackboard│ │Checkpoints   │  │
│  │Orchestr. │ │(3 modes) │ │(encrypted│ │(time travel) │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │EventBus  │ │HITL      │ │Guards    │ │Evaluation    │  │
│  │(pub/sub) │ │Manager   │ │(dual)    │ │(A/B testing) │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📖 Documentation

| Resource | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation and first workflow |
| [Core Concepts](docs/concepts.md) | Cell, Agent, Blackboard, Checkpoint |
| [API Reference](docs/api-reference.md) | Complete API documentation |
| [Architecture](docs/architecture.md) | Deep dive into the design |
| [Deployment](docs/deployment.md) | Docker, Kubernetes, and production setup |
| [Contributing](CONTRIBUTING.md) | How to contribute to HiveFlow |

---

## 📦 Project Structure

```
HiveFlow/
├── packages/
│   ├── core/                 # Core engine (PyPI: hiveflow)
│   │   ├── hiveflow/         # Main package
│   │   │   ├── __init__.py   # Public API exports
│   │   │   ├── app.py        # Top-level HiveFlow API
│   │   │   ├── orchestrator.py
│   │   │   ├── cognitive_orchestrator.py
│   │   │   ├── scheduler.py
│   │   │   ├── blackboard.py
│   │   │   ├── cell.py
│   │   │   ├── bus.py
│   │   │   ├── checkpoint.py
│   │   │   ├── hitl.py
│   │   │   ├── guards.py
│   │   │   ├── evaluation.py
│   │   │   ├── streaming.py
│   │   │   ├── validation.py
│   │   │   ├── llm_client.py
│   │   │   ├── memory_manager.py
│   │   │   ├── react_worker.py
│   │   │   ├── intent_parser.py
│   │   │   ├── mcp.py
│   │   │   ├── multimodal.py
│   │   │   ├── rag.py
│   │   │   ├── plugin_marketplace.py
│   │   │   ├── observability/
│   │   │   └── ...
│   │   ├── tests/            # Test suite
│   │   └── pyproject.toml    # Package configuration
│   │
│   ├── agent/                # Agent runtime
│   │   ├── worker/           # Agent workers (ReAct, etc.)
│   │   ├── memory/           # Short/long-term memory
│   │   ├── tools/            # Tool integrations
│   │   ├── tests/            # Test suite
│   │   └── requirements.txt
│   │
│   └── studio/               # Visual orchestration platform
│       ├── frontend/         # React + TypeScript UI
│       └── backend/          # FastAPI backend
│
├── kubernetes/               # Production deployment configs
├── docker-compose.yml        # Development environment
├── examples/                 # Cookbook examples
└── docs/                     # Documentation
```

---

## 🔧 Configuration

### Environment Variables

```bash
# LLM Configuration
HIVEFLOW_LLM_PROVIDER=openai        # openai, anthropic, mock
HIVEFLOW_LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Redis (optional, for distributed blackboard)
REDIS_URL=redis://localhost:6379

# Database (optional, for Studio persistence)
DB_URL=postgresql://user:pass@localhost:5432/hiveflow
```

---

## 🧪 Testing

```bash
# Run all tests
cd packages/core && python -m pytest

# Run with coverage
python -m pytest --cov=hiveflow --cov-report=html

# Run specific test file
python -m pytest tests/test_blackboard.py -v
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

```bash
# 1. Fork the repository
# 2. Create a feature branch
git checkout -b feature/my-feature

# 3. Install dev dependencies
pip install "hiveflow[dev]"

# 4. Run tests and linting
ruff check hiveflow/
mypy hiveflow/
pytest

# 5. Submit a Pull Request
```

---

## 📊 Comparison

| Feature | HiveFlow | LangGraph | CrewAI | AutoGen |
|---------|:--------:|:---------:|:------:|:-------:|
| Dynamic Orchestration | ✅ | ⚠️ | ❌ | ⚠️ |
| Human-in-the-Loop | ✅ | ⚠️ | ❌ | ⚠️ |
| Checkpoint/Time Travel | ✅ | ✅ | ❌ | ❌ |
| Security Guards | ✅ | ❌ | ❌ | ❌ |
| MCP Protocol | ✅ | ❌ | ❌ | ❌ |
| Visual UI | ✅ | 💰 | ❌ | ❌ |
| A/B Testing | ✅ | 💰 | ❌ | ❌ |
| Plugin Marketplace | ✅ | ❌ | ❌ | ❌ |

*✅ Built-in | ⚠️ Requires custom | ❌ Not available | 💰 Paid*

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Inspired by LangGraph, CrewAI, and AutoGen
- Built on [MCP (Model Context Protocol)](https://github.com/modelcontextprotocol)
- UI powered by [Ant Design](https://ant.design/) and [React](https://react.dev/)
