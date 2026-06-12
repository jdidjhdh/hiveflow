# Checkpoint 恢复

保存并恢复工作流黑板状态，用于时间旅行调试与故障恢复。

## 适用场景

- 长时间运行的多智能体工作流
- Worker 崩溃或 deliberate 暂停后恢复
- 通过 Studio **Replay** 页面审计与回放

## 最小代码

见 [`examples/04_checkpoint.py`](https://github.com/jdidjhdh/hiveflow/blob/main/examples/04_checkpoint.py)：

```python
from hiveflow import HiveFlow, HiveFlowConfig, CheckpointManager

hf = HiveFlow(HiveFlowConfig())
await hf.start()

manager = CheckpointManager(hf.blackboard)
checkpoint_id = await manager.create_checkpoint(
    workflow_id="my-workflow",
    metadata={"step": "after_ingest"},
)

# ... later ...
await manager.restore_checkpoint(checkpoint_id)
```

## Studio

- **Checkpoints** 页面列出当前工作流的快照。
- **Replay**（`/replay`）将 `intent_id` 与黑板 audit 条目关联。

## 相关

- [核心概念 — Checkpoint](../concepts.md)
- [架构](../architecture.md)
