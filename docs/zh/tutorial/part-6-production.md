# 第 6 部分 — 生产

部署 HiveFlow、观测运行系统、排查常见问题，并导航仓库结构。

## 6.1 部署方式

| 方式 | 适用 | 文档 |
|------|------|------|
| Docker Compose | 本地 / 单节点生产 | [部署](../deployment.md) |
| `docker-compose.release.yml` | 预构建 GHCR 镜像 | 发布说明 |
| Kubernetes | 多节点集群 | `kubernetes/hiveflow-deployment.yaml` |
| PyPI embed | 无 Studio 的自定义应用 | [第 1 部分](part-1-foundation.md) |

### 生产 Docker Compose

```bash
cp .env.example .env
# 配置真实 API Key；取消 HIVEFLOW_AGENT_ECHO_LLM
docker compose -f docker-compose.release.yml up -d
```

GHCR 镜像（Release v0.1.0）：

- `ghcr.io/jdidjhdh/hiveflow-studio-api:0.1.0`
- `ghcr.io/jdidjhdh/hiveflow-studio-web:0.1.0`

### 健康检查

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:3000
redis-cli ping   # PONG
```

## 6.2 可观测性

| 信号 | 工具 | 文档 |
|------|------|------|
| 指标 | Prometheus exporter、Studio Analytics | [可观测性](../observability.md) |
| 追踪 | OpenTelemetry（可选） | `hiveflow.observability.tracing` |
| 日志 | 结构化 JSON 日志 | Studio **Events**、**Audit Log** |
| 回放 | 检查点 + 审计 | Studio **Replay** |

启用追踪：

```python
from hiveflow.observability.tracing import configure_tracing
configure_tracing(service_name="hiveflow-prod")
```

## 6.3 安全清单

- [ ] 通过密钥管理服务轮换 `HIVEFLOW_ENCRYPTION_KEY`（[第 3 部分](part-3-advanced.md)）
- [ ] 启用输入/输出护栏（[示例 14](../../examples/14_guard_configuration.py)）
- [ ] 对不可逆操作使用 HITL（[第 2 部分](part-2-workflows.md)）
- [ ] 限制 Studio 网络访问（反向代理 + 认证）
- [ ] 按 [SECURITY.md](https://github.com/jdidjhdh/hiveflow/blob/main/SECURITY.md) 报告漏洞

## 6.4 扩展

```
                    ┌─────────────┐
                    │   Studio    │
                    │  (UI + API) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Agent 实例    Agent 实例    Agent 实例
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │    黑板     │
                    └─────────────┘
```

- 设置 `blackboard_type=redis` 共享状态（[示例 11](../../examples/11_distributed_agents.py)）
- Postgres 存储 Studio 元数据（工作流、凭证）
- 水平扩展：多个 Agent/Core Worker 共用同一 Redis URL

## 6.5 故障排查

| 错误 | 原因 | 处理 |
|------|------|------|
| `No module named 'hiveflow'` | 未安装 Core | `pip install -e packages/core` |
| `No module named 'cryptography'` | 缺少 security extra | `pip install "hiveflow-core[security]"` |
| Redis 连接拒绝 | Redis 未启动 | `docker compose up redis` |
| Docs strict 构建失败 | mkdocs i18n 配置错误 | 使用顶层 `edit_uri_template` |
| Docker pipe 不存在 | Docker Desktop 未运行 | 启动 Docker Desktop |
| `git push` 超时 | github.com:443 网络问题 | 使用 `scripts/` 下 GitHub API 脚本 |

## 6.6 仓库地图

### 根目录文件

| 文件 | 用途 |
|------|------|
| `README.md` / `README.zh.md` | 项目概览 |
| `docker-compose.yml` | 本地全栈 |
| `mkdocs.yml` | 文档站配置 |
| `CHANGELOG.md` | 版本历史 |
| `ROADMAP.md` | 产品路线图 |
| `CONTRIBUTING.md` | 贡献指南 |
| `OSS_LAUNCH.md` | 上线 checklist |

### Packages

| 路径 | PyPI | 职责 |
|------|------|------|
| `packages/core/hiveflow/` | `hiveflow-core` | 调度、黑板、DAG、HITL、MCP |
| `packages/agent/` | `hiveflow-agent` | LLM、NL 规划、ReAct Worker |
| `packages/studio/backend/` | — | FastAPI REST + WebSocket |
| `packages/studio/frontend/` | — | React UI |

### 脚本（`scripts/`）

| 脚本 | 用途 |
|------|------|
| `verify_launch_readiness.py` | 发布前 CI 门禁 |
| `setup_github_repo.py` | GitHub 仓库配置 |
| `post_discussion_announcement.py` | 发布讨论公告 |
| `blind_test_tarball.py` | 模拟新用户安装 |

### CI（`.github/workflows/`）

| Workflow | 触发 | 动作 |
|----------|------|------|
| `test.yml` | push/PR | 全包 pytest |
| `docs.yml` | push main | 部署 GitHub Pages |
| `release.yml` | tag `v*` | 构建 wheel + GHCR 镜像 |

## 6.7 发布与版本

HiveFlow 处于 **0.1.x Alpha**，1.0 前可能有破坏性变更。

- 从 GitHub Release wheel 或 editable 源码安装
- PyPI 发布由维护者控制（可选）
- 见 [版本策略](../versioning.md) 与 [v0.1.0 发布说明](../release-notes/v0.1.0.md)

## 6.8 获取帮助

| 渠道 | 用途 |
|------|------|
| [GitHub Issues](https://github.com/jdidjhdh/hiveflow/issues) | Bug |
| [Discussions](https://github.com/jdidjhdh/hiveflow/discussions) | 问题、想法 |
| [文档站](https://jdidjhdh.github.io/hiveflow/) | 教程、API |
| 文档页「Edit this page」 | 通过 PR 修正文档 |

## 6.9 最终练习 — 端到端

1. `docker compose up --build`
2. 在 Studio 完成 Golden Path（第 5 部分）
3. 审批一个 HITL gate
4. 查看 **Replay** 与 **Analytics**
5. 在新 venv 中运行 `python examples/run_smoke_tests.py`
6. 导出计划为 LangGraph JSON

恭喜 — 你已完成 HiveFlow 完整教程。

← 返回 [教程索引](index.md)
