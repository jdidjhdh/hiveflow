# Checkpoint Recovery

Save and restore workflow blackboard state for time-travel debugging and failure recovery.

## When to use

- Long-running multi-agent workflows
- Resume after worker crash or deliberate pause
- Audit and replay via Studio **Replay** page

## Minimal code

See [`examples/04_checkpoint.py`](https://github.com/jdidjhdh/hiveflow/blob/main/examples/04_checkpoint.py):

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

- **Checkpoints** page lists snapshots for the active workflow.
- **Replay** (`/replay`) correlates `intent_id` with blackboard audit entries.

## Related

- [Core Concepts — Checkpoint](../concepts.md)
- [Architecture](../architecture.md)
