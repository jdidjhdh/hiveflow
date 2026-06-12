#!/usr/bin/env python3
"""Core maintainer debug session — import paths, DAG, scheduler, blackboard."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

DEBUG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEBUG_DIR))

from common import log, reset_log


def check_import_mode() -> None:
    import hiveflow.bus as bus_mod

    bus_file = getattr(bus_mod, "__file__", "").replace("\\", "/")
    uses_package = "/hiveflow/" in bus_file
    flat_bus = sys.modules.get("bus")
    split_brain = flat_bus is not None and flat_bus is not bus_mod
    log(
        "core_session:import",
        "import path check",
        {"usesPackagePath": uses_package, "busModuleFile": bus_file, "splitBrain": split_brain},
        "H1",
    )


async def test_dag_pipeline() -> None:
    from hiveflow import HiveFlow, HiveFlowConfig
    from hiveflow.orchestrator import DAGOrchestrator

    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    order: list[str] = []

    async def n1(_deps, _bb):
        order.append("n1")
        return {"v": 1}

    async def n2(deps, _bb):
        order.append("n2")
        return {"v": deps["a"]["v"] + 1}

    async def n3(deps, _bb):
        order.append("n3")
        return {"sum": deps["a"]["v"] + deps["b"]["v"]}

    graph = {
        "a": {"task": n1, "depends_on": []},
        "b": {"task": n2, "depends_on": ["a"]},
        "c": {"task": n3, "depends_on": ["a", "b"]},
    }
    out = await DAGOrchestrator(hf.blackboard).execute(graph)
    log(
        "core_session:dag",
        "DAG result",
        {"executionOrder": order, "outputKeys": list(out.keys()), "cSum": out.get("c", {}).get("sum")},
        "H3",
    )
    await hf.shutdown()


async def test_schedule_race() -> None:
    from hiveflow import ECM, HiveFlow, HiveFlowConfig

    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    ecm = ECM(
        trace_id="race",
        intent="test",
        intent_id="race-1",
        emitter="debug",
        required_skills={"skill_a"},
    )
    scheduled = await hf.scheduler.schedule(ecm)
    log(
        "core_session:schedule",
        "schedule without worker",
        {"scheduled": scheduled, "workerCount": len(hf.scheduler._worker_queues)},
        "H4",
    )

    async def handler(ecm, view):
        return {"ok": True}

    await hf.create_agent("a1", {"skill_a"}, set(), set(), handler)
    ecm2 = ECM(
        trace_id="race",
        intent="test",
        intent_id="race-2",
        emitter="debug",
        required_skills={"skill_a"},
    )
    scheduled2 = await hf.scheduler.schedule(ecm2)
    await asyncio.sleep(0.2)
    log("core_session:schedule", "schedule with worker", {"scheduled": scheduled2}, "H4")
    await hf.shutdown()


async def test_blackboard_permissions() -> None:
    from hiveflow import Capability
    from hiveflow.blackboard import MemoryBlackboard, SecureBlackboard

    bb = SecureBlackboard(MemoryBlackboard())
    cap = Capability(agent_id="wildcard-agent", skills={"x"}, read_keys={"*"}, write_keys={"*"})
    await bb.register_agent("wildcard-agent", cap)
    denied = False
    try:
        await bb.get_and_audit("wildcard-agent", "any:key")
    except PermissionError:
        denied = True
    log("core_session:blackboard", "wildcard read blocked", {"denied": denied}, "H5")


async def main() -> None:
    reset_log()
    log("core_session:main", "session start", {}, "H0")
    check_import_mode()
    await test_dag_pipeline()
    await test_schedule_race()
    await test_blackboard_permissions()
    log("core_session:main", "session complete", {}, "H0")


if __name__ == "__main__":
    asyncio.run(main())
