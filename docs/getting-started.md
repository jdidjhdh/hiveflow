# Getting Started with HiveFlow

This guide will help you get up and running with HiveFlow in minutes.

## Prerequisites

- **Python 3.10+**: HiveFlow requires Python 3.10 or later
- **pip**: Python package manager
- **(Optional) Redis**: For distributed blackboard support
- **(Optional) PostgreSQL**: For Studio persistence

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
# Core only (minimal dependencies)
pip install hiveflow

# With security features (encryption, JSON schema validation)
pip install "hiveflow[security]"

# With LLM providers (OpenAI, Anthropic)
pip install "hiveflow[llm]"

# With RAG capabilities
pip install "hiveflow[rag]"

# Everything
pip install "hiveflow[all]"
```

### Option 2: Install from Source

```bash
git clone https://github.com/hiveflow/hiveflow.git
cd hiveflow/packages/core
pip install -e ".[all]"
```

### Option 3: Development Installation

```bash
git clone https://github.com/hiveflow/hiveflow.git
cd hiveflow/packages/core
pip install -e ".[dev]"
```

## Quick Start

### 1. Basic Workflow

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig

async def main():
    # Create engine with mock LLM (no API key needed)
    config = HiveFlowConfig(llm_provider="mock")
    hf = HiveFlow(config)

    # Execute a simple workflow
    result = await hf.execute_workflow(
        agents=[
            {"id": "agent-1", "skills": {"greet"}},
        ],
        task="Say hello"
    )

    print(result)

asyncio.run(main())
```

### 2. Multi-Agent Collaboration

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig

async def main():
    hf = HiveFlow(HiveFlowConfig(llm_provider="mock"))

    result = await hf.execute_workflow(
        agents=[
            {"id": "researcher", "skills": {"search", "analyze"}},
            {"id": "writer", "skills": {"write", "edit"}},
            {"id": "reviewer", "skills": {"review", "approve"}},
        ],
        task="Research and write an article about AI"
    )

    print(result)

asyncio.run(main())
```

### 3. Human-in-the-Loop

```python
import asyncio
from hiveflow import HiveFlow, HITLGate

async def main():
    hf = HiveFlow()

    # Create approval gate
    gate = HITLGate(
        gate_id="content-review",
        description="Review before publishing",
        timeout=300,  # 5 minutes
    )

    # Agent submits for approval
    await gate.request_approval(
        agent_id="writer",
        data={"content": "Article draft..."},
    )

    # Human approves via UI or API
    # await gate.approve(gate_id="content-review", reviewer="admin")

asyncio.run(main())
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Copy the template
cp .env.example .env
```

Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `HIVEFLOW_LLM_PROVIDER` | LLM provider | `openai` |
| `HIVEFLOW_LLM_MODEL` | LLM model | `gpt-4o` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `REDIS_URL` | Redis connection URL | - |
| `DB_URL` | Database connection URL | `sqlite:///./hiveflow.db` |

## Next Steps

- Read [Core Concepts](concepts.md) to understand Cell, Agent, Blackboard
- Follow the [Tutorials](tutorials/) for step-by-step guides
- Check the [API Reference](api-reference.md) for complete documentation
- Join the [Community](https://github.com/hiveflow/hiveflow/discussions)

## Troubleshooting

### "No module named 'hiveflow'"

Make sure you've installed the package:
```bash
pip install hiveflow
```

### ImportError with optional features

Install the required extras:
```bash
pip install "hiveflow[security,redis,llm]"
```

### Redis connection errors

Check your Redis server is running:
```bash
redis-cli ping
# Should return: PONG
```
