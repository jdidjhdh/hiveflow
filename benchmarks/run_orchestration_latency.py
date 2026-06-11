#!/usr/bin/env python3
"""Orchestration latency benchmarks (synthetic, no LLM).

Compares:
  - Pure asyncio sequential chain (baseline)
  - HiveFlow DAGOrchestrator (3-node linear + parallel fan-in)
  - HITL gate overhead (auto-approved)
  - Scheduler throughput (100 ECM messages)

Usage:
    python benchmarks/run_orchestration_latency.py
    python benchmarks/run_orchestration_latency.py --quick --json out.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

# Repo root on path for editable install in CI
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "packages" / "core") not in sys.path:
    sys.path.insert(0, str(_ROOT / "packages" / "core"))

from hiveflow import (  # noqa: E402
    DAGOrchestrator,
    ECM,
    HITLAction,
    HITLManager,
    InProcessEventBus,
    InProcessScheduler,
    MemoryBlackboard,
    SchedulerConfig,
    SecureBlackboard,
)


@dataclass
class BenchResult:
    name: str
    iterations: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    notes: str = ""


@dataclass
class BenchmarkReport:
    platform: str = field(default_factory=lambda: sys.platform)
    python: str = field(default_factory=lambda: sys.version.split()[0])
    iterations: int = 0
    results: list[BenchResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "python": self.python,
            "iterations": self.iterations,
            "results": [asdict(r) for r in self.results],
        }


def _percentiles(samples_ms: list[float]) -> tuple[float, float, float]:
    if not samples_ms:
        return 0.0, 0.0, 0.0
    ordered = sorted(samples_ms)
    p50 = statistics.median(ordered)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    mean = statistics.mean(ordered)
    return p50, p95, mean


async def _run_timed(
    name: str,
    fn: Callable[[], Coroutine[Any, Any, None]],
    iterations: int,
    notes: str = "",
) -> BenchResult:
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t0) * 1000)
    p50, p95, mean = _percentiles(samples)
    return BenchResult(name=name, iterations=iterations, p50_ms=round(p50, 3), p95_ms=round(p95, 3), mean_ms=round(mean, 3), notes=notes)


async def _bench_asyncio_baseline() -> None:
    async def step(_: int) -> int:
        return 1

    x = 0
    for i in range(3):
        x += await step(i)


def _make_linear_dag_graph() -> dict:
    async def n1(deps, view):
        return {"v": 1}

    async def n2(deps, view):
        return {"v": deps["a"]["v"] + 1}

    async def n3(deps, view):
        return {"v": deps["b"]["v"] + 1}

    return {
        "a": {"task": n1, "depends_on": []},
        "b": {"task": n2, "depends_on": ["a"]},
        "c": {"task": n3, "depends_on": ["b"]},
    }


def _make_parallel_dag_graph() -> dict:
    async def src(deps, view):
        return {"v": 10}

    async def left(deps, view):
        return {"v": deps["src"]["v"] + 1}

    async def right(deps, view):
        return {"v": deps["src"]["v"] + 2}

    async def merge(deps, view):
        return {"v": deps["left"]["v"] + deps["right"]["v"]}

    return {
        "src": {"task": src, "depends_on": []},
        "left": {"task": left, "depends_on": ["src"]},
        "right": {"task": right, "depends_on": ["src"]},
        "merge": {"task": merge, "depends_on": ["left", "right"]},
    }


async def _bench_hiveflow_dag_linear(bb: SecureBlackboard, orch: DAGOrchestrator) -> None:
    await orch.execute(_make_linear_dag_graph())


async def _bench_hiveflow_dag_parallel(bb: SecureBlackboard, orch: DAGOrchestrator) -> None:
    await orch.execute(_make_parallel_dag_graph())


async def _bench_hitl_gate() -> None:
    hitl = HITLManager()
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, hitl_manager=hitl, workflow_id="bench_hitl")

    async def gated(deps, view):
        return "ok"

    graph = {
        "step": {
            "task": gated,
            "depends_on": [],
            "hitl": {
                "action": HITLAction.APPROVAL.value,
                "prompt": "Approve?",
                "context": {},
            },
        },
    }

    exec_task = asyncio.create_task(orch.execute(graph))
    await asyncio.sleep(0.01)
    pending = await hitl.list_pending_gates()
    if pending:
        await hitl.respond(pending[0].gate_id, approved=True)
    await exec_task


async def _bench_scheduler_100() -> None:
    bus = InProcessEventBus()
    sched = InProcessScheduler(bus=bus, config=SchedulerConfig())
    await sched.start()
    try:
        from hiveflow import Capability

        cap = Capability(
            agent_id="bench-worker",
            skills={"noop"},
            read_keys=set(),
            write_keys=set(),
        )
        cap.state = "running"
        cap.max_queue_size = 1000
        mock_worker = type(
            "BenchWorker",
            (),
            {
                "agent_id": "bench-worker",
                "assign_task": lambda self, ecm: None,
            },
        )()
        await sched.register_worker(mock_worker, cap)

        for i in range(100):
            await sched.schedule(
                ECM(
                    trace_id=f"t-{i}",
                    intent="noop",
                    intent_id=f"i-{i}",
                    emitter="bench",
                    required_skills=["noop"],
                )
            )
    finally:
        await sched.close()


async def run_benchmarks(iterations: int) -> BenchmarkReport:
    report = BenchmarkReport(iterations=iterations)
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    report.results.append(
        await _run_timed("asyncio_sequential_3step", _bench_asyncio_baseline, iterations, "Baseline, no framework")
    )
    report.results.append(
        await _run_timed(
            "hiveflow_dag_linear_3node",
            lambda: _bench_hiveflow_dag_linear(bb, orch),
            iterations,
            "DAGOrchestrator A→B→C",
        )
    )
    report.results.append(
        await _run_timed(
            "hiveflow_dag_parallel_fanin",
            lambda: _bench_hiveflow_dag_parallel(bb, orch),
            iterations,
            "Parallel branches + merge",
        )
    )
    report.results.append(
        await _run_timed(
            "hiveflow_hitl_auto_approve",
            _bench_hitl_gate,
            max(5, iterations // 5),
            "One HITL gate; fewer iters (async wait)",
        )
    )
    report.results.append(
        await _run_timed(
            "hiveflow_scheduler_100_ecm",
            _bench_scheduler_100,
            max(3, iterations // 10),
            "100 schedule() calls per iter",
        )
    )
    return report


def _print_report(report: BenchmarkReport) -> None:
    print(f"\nHiveFlow orchestration benchmarks (iterations={report.iterations})")
    print(f"Platform: {report.platform}  Python: {report.python}\n")
    print(f"{'Scenario':<32} {'p50 ms':>10} {'p95 ms':>10} {'mean ms':>10}  Notes")
    print("-" * 90)
    for r in report.results:
        print(f"{r.name:<32} {r.p50_ms:>10.3f} {r.p95_ms:>10.3f} {r.mean_ms:>10.3f}  {r.notes}")


def main() -> int:
    parser = argparse.ArgumentParser(description="HiveFlow orchestration latency benchmarks")
    parser.add_argument("--iterations", type=int, default=50, help="Iterations per scenario (default 50)")
    parser.add_argument("--quick", action="store_true", help="CI mode: 10 iterations")
    parser.add_argument("--json", type=str, default="", help="Write JSON report to path")
    args = parser.parse_args()
    iterations = 10 if args.quick else args.iterations

    report = asyncio.run(run_benchmarks(iterations))
    _print_report(report)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nWrote {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
