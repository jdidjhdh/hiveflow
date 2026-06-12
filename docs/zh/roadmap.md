# HiveFlow 路线图

面向生产就绪开源版本的公开路线图。时间线为近似值。

## 当前状态（v0.1.0 Alpha）

- 带 HITL、RAG、MCP、checkpoint、guards 的 Core 编排引擎
- Agent 运行时（`hiveflow-agent`）与 ReAct Worker
- Studio 可视化平台（FastAPI + React）
- 800+ 自动化测试、15 个可运行示例
- CI：Core / Agent / Studio / Examples / Frontend / E2E（含后端）

---

## 第一阶段 — 开源发布（2026 Q2）

| 事项 | 状态 |
|------|--------|
| PyPI 发布（`hiveflow`、`hiveflow-agent`） | 维护者 — 打 tag `v0.1.0` |
| GitHub Pages 文档站点 | 维护者 — 启用 Pages |
| 集成指南（OpenAI、Redis、Postgres） | 已完成 |
| 覆盖率门禁（core ≥ 60%） | 已完成 |
| Core 公开 API 模块 MyPy | 已完成 |
| CI 中 Playwright E2E + 后端 | 已完成 |
| CI 中 Vitest 单元测试 | 已完成 |
| 文档/API 一致性 + mkdocstrings | 已完成 |
| GOVERNANCE + OSS 清单 | 已完成 |
| GitHub Discussions | 维护者操作 |
| Demo GIF + Discord | 规划中 |

**退出标准：** 新用户可 `pip install hiveflow`、运行示例，并阅读在线文档，无需阅读源码。

---

## 第二阶段 — 开发者体验（2026 Q3）

| 事项 | 目标 |
|------|--------|
| 代码路径中的统一高层 API | v0.2 |
| Cookbook（5 篇指南） | 已完成 |
| OpenTelemetry | [可观测性指南](observability.md) + v0.2 导出加固 |
| Agent/Core 黑板统一 | v0.2 |
| Semver 策略 | [版本策略](versioning.md) |

---

## 第三阶段 — 生态（2026 Q4 – 2027）

| 事项 | 目标 |
|------|--------|
| 集成中心（20+ 连接器） | 社区 + core |
| LangChain / LangGraph 适配器 | v0.3 — **PoC** [集成](integrations/langgraph.md) |
| 托管评估与追踪 UI | Studio 或独立产品 |
| 生产案例研究与基准 | [案例研究](case-studies/regulated-hitl-content-review.md) + [基准](benchmarks/orchestration-latency.md) |
| **v1.0** API 冻结 | Studio + Core 稳定 6 个月 |

---

## 如何影响路线图

1. 在 GitHub 提交 Feature Request issue
2. 在 GitHub Discussions 中评论（启用后）
3. 提交带测试与文档的 PR

参见 [ROADMAP.md](https://github.com/hiveflow/hiveflow/blob/main/ROADMAP.md) 与 [OSS 发布清单](oss-launch.md)。
