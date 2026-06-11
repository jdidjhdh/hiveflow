# Benchmarks

Reproducible performance measurements for HiveFlow orchestration (synthetic workloads, no LLM).

## Quick run

```bash
cd packages/core && pip install -e .
python ../../benchmarks/run_orchestration_latency.py --quick
```

Full run (50 iterations per scenario):

```bash
python benchmarks/run_orchestration_latency.py --json benchmarks/last-run.json
```

## Scenarios

| Name | What it measures |
|------|------------------|
| `asyncio_sequential_3step` | Baseline: 3 await steps, no framework |
| `hiveflow_dag_linear_3node` | `DAGOrchestrator` linear chain |
| `hiveflow_dag_parallel_fanin` | Parallel branches + merge node |
| `hiveflow_hitl_auto_approve` | HITL gate create + respond + node run |
| `hiveflow_scheduler_100_ecm` | 100× `scheduler.schedule()` calls |

## Interpreting results

- Numbers are **machine-dependent**; use for regression tracking on the same hardware.
- Overhead vs baseline = `(hiveflow_dag_linear p50) - (asyncio p50)`.
- HITL scenario includes async polling; compare trends, not absolute SLA.
- LLM / plan-only latency is **not** included (use mock LLM in Agent tests separately).

See [docs/benchmarks/orchestration-latency.md](../docs/benchmarks/orchestration-latency.md).
