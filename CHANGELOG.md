# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Cognitive Orchestration with dynamic plan generation
- Human-in-the-Loop (HITL) complete approval workflow
- Secure Blackboard system with encryption and audit logging
- Multi-strategy scheduler (least-loaded, auction, global load-aware)
- RAG pipeline with multi-source document processing
- MCP (Model Context Protocol) plugin integration
- Evaluation framework with A/B testing and benchmarks
- Checkpoint system with time travel capability
- Streaming SSE responses with rich event types
- Visual Studio UI with workflow builder, analytics, and plugin marketplace
- Input/Output dual Guard security (injection/XSS/SQLi protection)
- Multi-modal processing (image/audio/video)
- Kubernetes deployment support
- Docker Compose development environment
- 745 test cases across all three projects

### Changed
- Enhanced `pyproject.toml` with proper PyPI metadata
- Added optional dependency groups (security, redis, llm, rag, all, dev)
- Improved code quality with Ruff and MyPy configuration

### Fixed
- Test isolation issues in Studio backend
- Mock engine pollution between test files
- Async fixture handling in test suite

---

## [0.1.0] - 2025-06-11

### Added
- Initial public release
- Core engine with Event Bus, Scheduler, Blackboard, Cell, Orchestrator
- Agent runtime with ReAct Worker, Intent Parser, Memory Manager
- Studio backend with FastAPI
- Studio frontend with React + TypeScript
- HITL manager for human approval workflows
- Guard system for input/output security
- RAG pipeline with vector store integration
- MCP protocol support
- Evaluation and A/B testing framework
- Checkpoint system for state snapshots
- Streaming support
- Multi-modal processing
- Kubernetes deployment configs
- Docker Compose setup
- 745 passing tests
