# 编排延迟基准

HiveFlow Core 编排开销的合成基准测试。**Alpha 免责声明：** 数据仅供在你自己的硬件上做相对比较，不构成生产 SLA。

## 方法论

- **环境：** CPython 3.10+、内存黑板、无网络 I/O、无 LLM。
- **工具：** [`benchmarks/run_orchestration_latency.py`](https://github.com/hiveflow/hiveflow/blob/main/benchmarks/run_orchestration_latency.py)
- **指标：** 各场景的 p50 / p95 / 平均端到端延迟（毫秒）。
- **CI：** 每次 push 通过 GitHub Actions 运行 `--quick`（10 次迭代）。

## 场景

### 基线：asyncio 顺序执行

循环中三个空操作 async 步骤。代表无 DAG 引擎的手写编排。

### HiveFlow DAG（线性）

通过 `DAGOrchestrator` 的三节点链 `A → B → C`。衡量框架调度 + 依赖连线相对基线的开销。

### HiveFlow DAG（并行 fan-in）

```
    src
   /   \
 left  right
   \   /
   merge
```

验证编排器内部的并行 `asyncio.gather` 执行。

### HITL 自动批准

单节点带 `hitl.approval` 门控；基准自动响应 pending gate。用于估算**审批 UX 开销**（不含人工思考时间）。

### 调度器吞吐量

100× `ECM.schedule()` 入队到单个 Worker（仅队列，不执行 handler）。压测调度器热路径。

## 示例输出（示意）

| 场景 | p50 ms | 说明 |
|----------|--------|-------|
| asyncio_sequential_3step | ~0.05 | 基线 |
| hiveflow_dag_linear_3node | ~0.15 | +~0.1 ms 框架开销 |
| hiveflow_dag_parallel_fanin | ~0.12 | 并行层 |
| hiveflow_hitl_auto_approve | ~15 | 含 gate 等待轮询 |
| hiveflow_scheduler_100_ecm | ~2 | 100 次 schedule |

*本地运行后请用 `last-run.json` 替换。*

## 复现

```bash
pip install -e packages/core
python benchmarks/run_orchestration_latency.py --iterations 50 --json benchmarks/last-run.json
```

## 与 LangGraph 对比

本脚本**未**包含 LangGraph 直接基准（可选依赖）。迁移语义请参阅 [LangGraph 集成](../integrations/langgraph.md) 与 [迁移指南](../guides/migrate-from-langgraph.md)。

## 回归策略

- CI `--quick` 必须无错误完成。
- GitHub `ubuntu-latest` 上 `hiveflow_dag_linear_3node` 的 p50 应**&lt; 50 ms**（CI 测试中的健全性守卫）。
