# 版本策略

HiveFlow 在 **Alpha**（0.y.z）阶段遵循 [Semantic Versioning 2.0.0](https://semver.org/)。

## 当前状态：0.1.x Alpha

- **0.1.x** — 初始公开发布；minor 版本间 API 可能变更，迁移说明见 [CHANGELOG](https://github.com/jdidjhdh/hiveflow/blob/main/CHANGELOG.md)。
- **0.2.x** — 开发者体验重点：统一高层 API、OpenTelemetry 文档、覆盖率目标。
- **1.0.0** — Core + Studio 稳定 6 个月后 API 冻结（[路线图](roadmap.md)）。

## 何谓破坏性变更

| 变更 | 版本 bump |
|--------|------|
| 移除/重命名公开 `hiveflow` 导出 | 0.x 期间 **Minor**（需文档说明）；1.0+ **Major** |
| Studio REST 路径或载荷变更 | Minor + 迁移说明 |
| 默认 env 行为变更 | Minor + CHANGELOG |
| 内部模块重构 | Patch |

## 软件包

| PyPI 名称 | 范围 |
|-----------|-------|
| `hiveflow` | Core 引擎 |
| `hiveflow-agent` | Agent 运行时（依赖 `hiveflow-core>=0.1`） |

发布时版本号保持同步（`v0.1.0` tag 同时发布两者）。

## 质量门禁（0.1.x）

| 包 | 覆盖率（CI） | 说明 |
|----|-------------|------|
| `hiveflow` | ≥ 60% | MyPy 覆盖公开 API；PyPI Alpha 分类器 |
| `hiveflow-agent` | ≥ 60% | 真实 LLM 测试可选本地跑（`-m real_llm`） |
| Studio 后端 | ≥ 60% | 仅 monorepo / Docker |
| Studio 前端 | ≥ 24% 行 | 页面靠 Playwright E2E |

详见 [质量门禁](quality-gates.md)。

## 升级检查清单

1. 阅读 [CHANGELOG](https://github.com/jdidjhdh/hiveflow/blob/main/CHANGELOG.md)。
2. 运行测试套件与 `examples/run_smoke_tests.py`。
3. Studio：检查 [Studio Agent 运维](studio-agent-ops.md) 中的 env 变量。
