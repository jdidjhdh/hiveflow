# Orchestration Latency Benchmarks

Synthetic benchmarks for HiveFlow Core orchestration overhead. **Alpha disclaimer:** figures are for relative comparison on your hardware, not production SLAs.

## Methodology

- **Environment:** CPython 3.10+, in-memory blackboard, no network I/O, no LLM.
- **Tool:** [`benchmarks/run_orchestration_latency.py`](https://github.com/hiveflow/hiveflow/blob/main/benchmarks/run_orchestration_latency.py)
- **Metrics:** p50 / p95 / mean end-to-end latency (milliseconds) per scenario.
- **CI:** `--quick` (10 iterations) runs on every push via GitHub Actions.

## Scenarios

### Baseline: asyncio sequential

Three no-op async steps in a loop. Represents hand-rolled orchestration without a DAG engine.

### HiveFlow DAG (linear)

Three-node chain `A → B → C` via `DAGOrchestrator`. Measures framework scheduling + dependency wiring vs baseline.

### HiveFlow DAG (parallel fan-in)

```
    src
   /   \
 left  right
   \   /
   merge
```

Validates parallel `asyncio.gather` execution inside the orchestrator.

### HITL auto-approve

Single node with `hitl.approval` gate; benchmark auto-responds to pending gate. Useful for estimating **approval UX overhead** separate from human think time.

### Scheduler throughput

100× `ECM.schedule()` enqueued to one worker (queue only, handlers not executed). Stresses scheduler hot path.

## Example output (illustrative)

| Scenario | p50 ms | Notes |
|----------|--------|-------|
| asyncio_sequential_3step | ~0.05 | Baseline |
| hiveflow_dag_linear_3node | ~0.15 | +~0.1 ms framework |
| hiveflow_dag_parallel_fanin | ~0.12 | Parallel layer |
| hiveflow_hitl_auto_approve | ~15 | Includes gate wait poll |
| hiveflow_scheduler_100_ecm | ~2 | 100 schedules |

*Replace with your `last-run.json` after running locally.*

## Reproduce

```bash
pip install -e packages/core
python benchmarks/run_orchestration_latency.py --iterations 50 --json benchmarks/last-run.json
```

## Comparison with LangGraph

Direct LangGraph benchmarks are **not** included in this script (optional dependency). For migration semantics see [LangGraph integration](../integrations/langgraph.md) and [migration guide](../guides/migrate-from-langgraph.md).

## Regression policy

- CI `--quick` must complete without error.
- p50 for `hiveflow_dag_linear_3node` should stay **&lt; 50 ms** on GitHub `ubuntu-latest` (sanity guard in CI test).
