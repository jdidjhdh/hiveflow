# 多智能体辩论

模式：多个专家 Agent 写入黑板；综合器 Agent 产出最终答案。

## 适用场景

- 需要多元视角的研究任务
- 发布前的红队 / 蓝队审阅

## 架构

```
Intent → Scheduler → [Researcher, Critic, FactChecker] (parallel)
                              ↓ blackboard keys
                     Synthesizer → final.result
```

## 示例

运行 [examples/02_multi_agent.py](https://github.com/jdidjhdh/hiveflow/blob/main/examples/02_multi_agent.py)：

```bash
cd packages/core && pip install -e ".[all]"
python ../../examples/02_multi_agent.py
```

要点：

1. 每个 Agent 拥有互不重叠的 `write_keys` 与共享读键
2. 调度策略（`LeastLoadedStrategy`、`AuctionStrategy`）选择 Worker
3. `SecureBlackboard` 强制执行键级权限

## Studio 模板

从 Orchestrator → Templates 加载 **debate_decision** 模板。

## 相关

- [概念 — 多智能体](../concepts.md)
- [示例 12 — 自定义调度器](https://github.com/jdidjhdh/hiveflow/blob/main/examples/12_custom_scheduler.py)
