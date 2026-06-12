# 质量门禁（Core · Agent · Studio）

HiveFlow **0.1.x 为 Alpha**（PyPI 分类器 `Development Status :: 3 - Alpha`）。API 可能变更，见 [版本策略](versioning.md)。

本文说明**自动化门禁**与**已知缺口**，便于贡献者与使用者对齐预期。

## 总览

| 包 | 测试（本地） | 覆盖率门禁 | 类型检查 | PyPI / npm |
|----|-------------|-----------|---------|------------|
| **Core** | 294 pytest | **≥ 60%**（`hiveflow/`） | MyPy 覆盖公开 API 模块 | `hiveflow` |
| **Agent** | 162+ pytest（CI） | **≥ 60%**（运行时模块） | — | `hiveflow-agent`（与 Core 同版本发布） |
| **Studio 后端** | 432 pytest | **≥ 60%**（`app/`） | — | 仅 Docker / monorepo |
| **Studio 前端** | 58 Vitest + 17 Playwright | **≥ 24%** 行（utils/stores）；UI 靠 E2E | `tsc --noEmit` | 仅 Docker / monorepo |

本地一键验证：

```bash
python scripts/verify_launch_readiness.py
```

---

## Core

### Alpha 分类器

PyPI 上的 `Development Status :: 3 - Alpha` **是有意为之**，表示：

- 遵循 **0.y.z** 语义化版本，minor 可能含破坏性变更（见 CHANGELOG）
- 在 **1.0.0** 之前不提供生产级 SLA（见 [路线图](roadmap.md)）

### Core MyPy 范围

CI 对 `packages/core/pyproject.toml` 中 `[tool.mypy] files` 列出的**公开 API 面**运行 `mypy`。

- **在范围内：** blackboard、bus、scheduler、cell、hitl、checkpoint、orchestrator、app、guards、streaming、validation、plugin_marketplace
- **0.1.x 不在范围内：** RAG 内部、multimodal、完整 `llm_client` — 将在 0.2 / 1.0 逐步补齐
- 配置了 `ignore_errors = true` 的模块为遗留项，清理前不阻塞 CI

### 执行后端（ExecutionBackend）

TaskGraph 可插拔运行时（`hiveflow.execution`）：

| 后端 | 状态 |
|------|------|
| `native` | 生产可用 — `DynamicOrchestrator` |
| `langgraph` | `to_langgraph_spec()` 导出；进程内 `execute()` 为 v0.3 占位 |

见 [LangGraph Sidecar 指南](cookbook/langgraph-sidecar.md)。

---

## Agent

### 覆盖率门禁（CI）

```bash
cd packages/agent
pytest tests/ \
  --ignore=tests/test_real_llm.py \
  --ignore=tests/test_llm_connection.py \
  --cov --cov-fail-under=60
```

源码范围见 `pyproject.toml`（`app`、`orchestrator`、`worker` 等）。

### 真实 LLM 测试（可选，仅本地）

`tests/test_real_llm.py` 与 `tests/test_llm_connection.py` **不进入 CI**，需真实 LLM，输出非确定性。

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=...
cd packages/agent
pytest tests/test_real_llm.py -v -m real_llm
```

标记：`@pytest.mark.real_llm` — 合并不需要。

### 发版耦合

`hiveflow-agent` 依赖 `hiveflow>=0.1.0`。**同一 git tag 必须同时发布两个包**（如 `v0.1.0`）。见 [发布指南](publishing.md)。

---

## Studio

### 分发方式

Studio **不会**在 0.1.x 作为独立 PyPI/npm 包发布。

| 产物 | 使用方式 |
|------|---------|
| 全栈 | `docker compose up` 或 `docker-compose.release.yml` |
| 仅后端 | `packages/studio/backend` + 可编辑安装 core/agent |
| 仅前端 | `packages/studio/frontend`（Vite → API `:8000`） |

### 前端覆盖率策略

Vitest 阈值约 **24%** 行覆盖，针对 `src/`，并有意排除：

- `src/pages/**` — 主要由 **Playwright E2E**（17 场景）覆盖
- `src/components/orchestrator/hooks/**` — React Flow 集成复杂，靠 E2E + 手工验证

页面单测提升到 80% 为 **0.2.x** 目标，不阻塞 Alpha。

### 演示 / 预览页面

并非所有路由均为生产级。见 **[CAPABILITIES.md](https://github.com/hiveflow/hiveflow/blob/main/packages/studio/CAPABILITIES.md)**（Stable / Beta / Preview / Demo）。

示例：**A/B 测试** = Demo；**执行分析** = Preview。

---

## 相关文档

- [版本策略](versioning.md)
- [发布（维护者）](publishing.md)
- [开源上线](oss-launch.md)
