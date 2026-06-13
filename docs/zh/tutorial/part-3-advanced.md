# 第 3 部分 — 进阶

认知规划、评估、加密黑板、分布式部署、自定义调度器、插件与护栏。

## 3.1 认知规划（示例 08）

步骤事先未知时，动态生成执行计划。

```bash
python examples/08_cognitive_planning.py
```

认知编排器会：

1. 分析目标。
2. 生成带 rationale 的多步计划。
3. 执行步骤并记录推理过程。

输出包含 `plan rationale`、`steps executed` 和 `reasoning log` — 便于调试 Studio Agent 模式的计划。

## 3.2 评估与 A/B 测试（示例 09）

用关键词重叠、完整性、清晰度等指标衡量输出质量。

```bash
python examples/09_evaluation.py
```

```python
# 概念用法
report = evaluator.evaluate(output, reference, criteria=["accuracy", "completeness", "clarity"])
print(report.total_score, report.passed)
winner = ab_runner.compare_variant_a_vs_b(output_a, output_b)
```

接入 CI 以门禁 prompt 或模型变更。Studio **A/B Testing** 页面提供类似能力。

## 3.3 安全黑板（示例 10）

静态加密敏感键，并记录审计日志。

```bash
pip install "hiveflow-core[security]"
python examples/10_secure_blackboard.py
```

```python
import os
from cryptography.fernet import Fernet
from hiveflow import HiveFlow, HiveFlowConfig, EnvKeyProvider

os.environ["HIVEFLOW_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

config = HiveFlowConfig(
    blackboard_type="encrypted",
    encryption_key_provider=EnvKeyProvider("HIVEFLOW_ENCRYPTION_KEY"),
)
hf = HiveFlow(config)
```

**切勿将加密密钥提交到 Git。** 生产环境使用密钥管理服务。

## 3.4 分布式 Agent（示例 11）

通过 Redis 黑板与总线在进程间共享状态。

```bash
docker run -d -p 6379:6379 redis:7-alpine
python examples/11_distributed_agents.py
```

```python
config = HiveFlowConfig(
    blackboard_type="redis",
    redis_url="redis://localhost:6379",
)
```

Redis 不可用时，示例 11 会回退到内存模式并警告 — 适合本地开发，不适合生产。

见 [Redis 集成](../integrations/redis.md)。

## 3.5 自定义调度器（示例 12）

接入自己的 Agent 选择策略。

```bash
python examples/12_custom_scheduler.py
```

内置策略：

| 策略 | 行为 |
|------|------|
| `least_loaded` | 选队列最短的 Agent |
| `auction` | Agent 按负载/能力竞价 |
| `load_aware` | 按 CPU/内存提示加权 |

子类或注册自定义策略以实现领域路由（如 GPU Agent、区域亲和）。

## 3.6 插件开发（示例 13）

浏览、搜索、安装 MCP 插件。

```bash
python examples/13_plugin_development.py
```

内置插件包括 Filesystem、Web Search、Database、API Client、Code Executor。分类：`data`、`tools`、`development`、`communication`、`ai`。

```python
from hiveflow import PluginMarketplace, MCPPluginManager

marketplace = PluginMarketplace()
plugin_manager = MCPPluginManager()
await marketplace.install_plugin("filesystem", plugin_manager)
```

Studio **Capability Market** 提供相同的安装/卸载操作。

## 3.7 输入/输出护栏（示例 14）

拦截 prompt 注入，并在输出到达用户或工具前校验。

```bash
python examples/14_guard_configuration.py
```

护栏与 Agent、Studio 深度集成：

- **输入护栏** — 正则/模式黑名单（如 "ignore previous instructions"）。
- **输出护栏** — 大小限制、Schema 校验。

通过 `HiveFlowConfig` 全局或按 Agent 配置。

## 3.8 进阶主题清单

| 主题 | 示例 | 扩展 |
|------|------|------|
| 动态规划 | `08` | Studio Agent plan-only |
| 质量门禁 | `09` | [质量门禁](../quality-gates.md) |
| 加密 | `10` | `[security]` extra |
| Redis 扩展 | `11` | `docker-compose.yml` redis 服务 |
| 调度策略 | `12` | `SchedulerConfig` |
| MCP 插件 | `13` | Studio `/api/plugins` |
| 安全护栏 | `14` | HITL + 护栏组合 |

## 3.9 练习

1. 在示例 10 中中途轮换密钥，观察解密行为。
2. 注册总选 `specialist` Agent 的自定义调度器。
3. 在示例 14 中拦截已知注入字符串，确认工作流干净停止。

## 下一步

→ [第 4 部分 — 集成](part-4-integrations.md)：多模态与 LangGraph 导出。
