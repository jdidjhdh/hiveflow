import pytest
import asyncio
import time
from typing import Any, Dict, Set

from hiveflow import (
    HiveFlow, HiveFlowConfig,
    InProcessEventBus, InProcessScheduler, SchedulerConfig,
    SecureBlackboard, MemoryBlackboard,
    Cell, Worker, DAGOrchestrator, Capability, ECM, Expectation
)


# --- Mock LLM for integration tests ---
class MockLLM:
    def __init__(self, json_responses=None, text_responses=None):
        self.json_responses = json_responses or []
        self.text_responses = text_responses or []
        self.json_call_count = 0
        self.text_call_count = 0

    async def complete_json(self, messages):
        resp = self.json_responses[self.json_call_count % len(self.json_responses)]
        self.json_call_count += 1
        return resp

    async def complete(self, messages, **kwargs):
        resp = self.text_responses[self.text_call_count % len(self.text_responses)]
        self.text_call_count += 1
        return resp

    async def stream(self, messages, **kwargs):
        return
        yield


# --- Integration: Core Worker + Blackboard + Scheduler ---
@pytest.mark.asyncio
async def test_worker_blackboard_integration(tmp_path):
    """Test that a Worker can read/write to blackboard via the scheduler."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)
    await hf.start()

    results = {}

    async def handler(ecm, view):
        # Read from upstream
        upstream = await view.get("upstream_data")
        result = {"processed": upstream, "agent": ecm.emitter}
        # Write result
        await view.put("worker_result", result)
        return result

    worker = await hf.create_agent(
        agent_id="test-worker",
        skills={"process"},
        read_keys={"upstream_data"},
        write_keys={"worker_result"},
        task_handler=handler,
    )

    # Write upstream data
    await hf.blackboard.sys_put("upstream_data", "hello")

    # Schedule task
    ecm = ECM(
        trace_id="test-1",
        intent="process",
        intent_id="intent-1",
        emitter="test",
        required_skills=["process"],
        payload={"query": "test"},
    )
    success = await hf.scheduler.schedule(ecm)
    assert success

    # Wait for result
    await asyncio.sleep(0.2)
    result = await hf.blackboard.sys_get("worker_result")
    assert result["processed"] == "hello"
    assert result["agent"] == "test"

    await hf.shutdown()


@pytest.mark.asyncio
async def test_multi_worker_pipeline():
    """Test multiple workers in a pipeline: Worker A -> Worker B."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)
    await hf.start()

    async def worker_a_handler(ecm, view):
        await view.put("step_a_result", {"step": "a", "value": 42})
        return {"step": "a", "value": 42}

    async def worker_b_handler(ecm, view):
        step_a = await view.get("step_a_result")
        result = {"step": "b", "value": step_a["value"] * 2}
        await view.put("step_b_result", result)
        return result

    await hf.create_agent(
        agent_id="worker-a",
        skills={"step_a"},
        read_keys=set(),
        write_keys={"step_a_result"},
        task_handler=worker_a_handler,
    )

    await hf.create_agent(
        agent_id="worker-b",
        skills={"step_b"},
        read_keys={"step_a_result"},
        write_keys={"step_b_result"},
        task_handler=worker_b_handler,
    )

    # Schedule step A
    ecm_a = ECM(
        trace_id="pipe-1",
        intent="step_a",
        intent_id="pipe-intent",
        emitter="test",
        required_skills=["step_a"],
        payload={"query": "pipeline"},
    )
    await hf.scheduler.schedule(ecm_a)

    # Wait for A
    await asyncio.sleep(0.1)
    a_result = await hf.blackboard.sys_get("step_a_result")
    assert a_result["value"] == 42

    # Schedule step B
    ecm_b = ECM(
        trace_id="pipe-2",
        intent="step_b",
        intent_id="pipe-intent",
        emitter="test",
        required_skills=["step_b"],
        payload={"query": "pipeline"},
    )
    await hf.scheduler.schedule(ecm_b)

    # Wait for B
    await asyncio.sleep(0.1)
    b_result = await hf.blackboard.sys_get("step_b_result")
    assert b_result["value"] == 84

    await hf.shutdown()


@pytest.mark.asyncio
async def test_dag_orchestrator_with_blackboard():
    """Test DAG orchestrator execution with real blackboard using sys_put for node results."""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    async def node_a(deps, view):
        # Use sys_put since OrchestratorReadonlyView is read-only
        await bb.sys_put("hivemind:result:exec-1:node_a", {"val": 10})
        return {"val": 10}

    async def node_b(deps, view):
        a = deps.get("node_a")
        await bb.sys_put("hivemind:result:exec-1:node_b", {"val": a["val"] * 2})
        return {"val": a["val"] * 2}

    async def final(deps, view):
        a = deps.get("node_a")
        b = deps.get("node_b")
        await bb.sys_put("hivemind:result:exec-1:final_answer", {"total": a["val"] + b["val"]})
        return {"total": a["val"] + b["val"]}

    graph = {
        "node_a": {"task": node_a, "depends_on": []},
        "node_b": {"task": node_b, "depends_on": ["node_a"]},
        "final_answer": {"task": final, "depends_on": ["node_a", "node_b"]},
    }

    result = await orch.execute(graph)
    assert result["node_a"]["val"] == 10
    assert result["node_b"]["val"] == 20
    assert result["final_answer"]["total"] == 30


@pytest.mark.asyncio
async def test_worker_error_propagation():
    """Test that worker errors are properly caught and published via event bus."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)
    await hf.start()

    error_published = False

    async def on_task_failed(ecm):
        nonlocal error_published
        error_published = True

    await hf.bus.subscribe("task.failed", on_task_failed)

    async def failing_handler(ecm, view):
        raise ValueError("Simulated failure")

    worker = await hf.create_agent(
        agent_id="failing-worker",
        skills={"fail"},
        read_keys=set(),
        write_keys={"fail_result"},
        task_handler=failing_handler,
    )

    ecm = ECM(
        trace_id="err-1",
        intent="fail",
        intent_id="err-intent",
        emitter="test",
        required_skills=["fail"],
        payload={"query": "test"},
    )

    # Schedule - worker will execute and error will be caught
    await hf.scheduler.schedule(ecm)
    await asyncio.sleep(0.2)

    # Error should have been published
    assert error_published

    await hf.shutdown()


@pytest.mark.asyncio
async def test_concurrent_workers_isolation():
    """Test that concurrent workers don't interfere with each other's keys."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)
    await hf.start()

    async def make_handler(agent_id):
        async def handler(ecm, view):
            # Only write to own key
            await view.put(f"result_{agent_id}", {"agent": agent_id})
            return {"agent": agent_id}
        return handler

    # Create 5 isolated workers
    for i in range(5):
        await hf.create_agent(
            agent_id=f"iso-{i}",
            skills={f"skill-{i}"},
            read_keys=set(),
            write_keys={f"result_iso-{i}"},
            task_handler=await make_handler(f"iso-{i}"),
        )

    # Schedule all concurrently
    tasks = []
    for i in range(5):
        ecm = ECM(
            trace_id=f"iso-{i}",
            intent=f"skill-{i}",
            intent_id=f"iso-intent-{i}",
            emitter="test",
            required_skills=[f"skill-{i}"],
            payload={},
        )
        tasks.append(hf.scheduler.schedule(ecm))

    await asyncio.gather(*tasks)
    await asyncio.sleep(0.2)

    # Verify each worker wrote only to its own key
    for i in range(5):
        result = await hf.blackboard.sys_get(f"result_iso-{i}")
        assert result["agent"] == f"iso-{i}"

    await hf.shutdown()


@pytest.mark.asyncio
async def test_full_pipeline_with_expectation():
    """Test full flow: Worker processes with expectation validation."""
    config = HiveFlowConfig()
    hf = HiveFlow(config)
    await hf.start()

    async def handler(ecm, view):
        data = {"output": "valid", "status": "success"}
        await view.put("validated_result", data)
        return data

    worker = await hf.create_agent(
        agent_id="validated-worker",
        skills={"validate"},
        read_keys=set(),
        write_keys={"validated_result"},
        task_handler=handler,
    )

    ecm = ECM(
        trace_id="val-1",
        intent="validate",
        intent_id="val-intent",
        emitter="test",
        required_skills=["validate"],
        payload={},
        expectation=Expectation(
            state_key="validated_result",
            expected_schema={"type": "object"},
        ),
    )

    # Schedule the task
    await hf.scheduler.schedule(ecm)
    await asyncio.sleep(0.2)

    # Result should be written with validation
    result = await hf.blackboard.sys_get("validated_result")
    assert result["status"] == "success"

    await hf.shutdown()
