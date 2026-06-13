# HiveFlow Examples (Cookbook)

This directory contains practical examples demonstrating various HiveFlow capabilities.

**Full bilingual tutorial:** [English](../docs/en/tutorial/index.md) · [简体中文](../docs/zh/tutorial/index.md)

## Basic Examples

| File | Description |
|------|-------------|
| `01_hello_hiveflow.py` | Basic setup and first workflow |
| `02_multi_agent.py` | Multi-agent collaboration |
| `03_hitl_approval.py` | Human-in-the-Loop approval workflow |
| `04_checkpoint.py` | State snapshots and time travel |
| `05_streaming.py` | SSE streaming responses |

## Advanced Examples

| File | Description |
|------|-------------|
| `06_rag_pipeline.py` | RAG with document processing |
| `07_mcp_tools.py` | MCP protocol tool integration |
| `08_cognitive_planning.py` | Cognitive orchestrator with dynamic planning |
| `09_evaluation.py` | Evaluation framework and A/B testing |
| `10_secure_blackboard.py` | Encrypted blackboard with audit logging |

## Production Examples

| File | Description |
|------|-------------|
| `11_distributed_agents.py` | Distributed agents with Redis backend |
| `12_custom_scheduler.py` | Custom scheduling strategy |
| `13_plugin_development.py` | Creating custom plugins |
| `14_guard_configuration.py` | Input/Output guard setup |
| `15_multimodal_pipeline.py` | Image/audio/video processing |

## Running Examples

```bash
cd packages/core && pip install -e ".[all]"
cd ../../examples
python 01_hello_hiveflow.py    # run a single example
python run_smoke_tests.py      # run all 15 examples
```
