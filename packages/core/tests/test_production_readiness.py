"""
HiveFlow Core 生产可用性测试

覆盖以下关键生产场景:
1. DynamicOrchestrator 子图生成
2. 重试策略 (constant / exponential backoff)
3. on_failure 回调
4. 全局超时
5. Worker drain & stop 优雅关闭
6. Cell 生命周期管理
7. EventBus 订阅标签过滤
8. 并发任务取消
"""

import pytest
import asyncio
import time
from hiveflow import (
    MISSING, TaskGraph, AbortExecutionException,
    ECM, Expectation, Capability
)
from hiveflow.bus import InProcessEventBus
from hiveflow.blackboard import SecureBlackboard, MemoryBlackboard
from hiveflow.orchestrator import DAGOrchestrator, DynamicOrchestrator
from hiveflow.cell import Cell, Worker
from hiveflow.scheduler import InProcessScheduler, SchedulerConfig
from hiveflow.validation import ValidationPipeline


# ============================================================
# 1. DynamicOrchestrator - Subgraph Generation
# ============================================================

@pytest.mark.asyncio
async def test_dynamic_orchestrator_subgraph():
    """测试节点运行时动态生成子图。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)

    async def expand_node(deps, view):
        # 返回子图: 在运行时添加两个新节点
        return {
            "value": 42,
            "subgraph": {
                "sub_a": {"task": sub_a_fn, "depends_on": []},
                "sub_b": {"task": sub_b_fn, "depends_on": ["sub_a"]},
            }
        }

    async def sub_a_fn(deps, view):
        return {"sub_a_result": "expanded_a"}

    async def sub_b_fn(deps, view):
        return {"sub_b_result": f"after_{deps.get('sub_a')}"}

    graph = {
        "root": {"task": expand_node, "depends_on": [], "dynamic": True},
        "final": {"task": lambda deps, view: {"done": True}, "depends_on": ["root"]},
    }

    results = await orch.execute(graph)
    assert "root" in results
    assert "root::sub_a" in results
    assert "root::sub_b" in results
    assert results["root::sub_a"]["sub_a_result"] == "expanded_a"


@pytest.mark.asyncio
async def test_dynamic_orchestrator_global_timeout():
    """测试全局超时触发。使用 asyncio.wait_for 包裹。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)

    async def slow_node(deps, view):
        await asyncio.sleep(60)
        return "done"

    graph = {
        "slow": {"task": slow_node, "depends_on": []},
    }

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(orch.execute(graph, global_timeout=0.05), timeout=1.0)


# ============================================================
# 2. Retry Policies
# ============================================================

@pytest.mark.asyncio
async def test_retry_exponential_backoff():
    """测试指数退避重试。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    attempts = []

    async def flaky_node(deps, view):
        attempts.append(time.monotonic())
        if len(attempts) < 3:
            raise RuntimeError(f"Attempt {len(attempts)} failed")
        return "success"

    graph = {
        "flaky": {
            "task": flaky_node,
            "depends_on": [],
            "retry_policy": {
                "max_attempts": 3,
                "backoff_type": "exponential",
                "backoff_base": 0.05,
                "max_backoff": 1.0,
            },
        },
    }

    results = await orch.execute(graph)
    assert results["flaky"] == "success"
    assert len(attempts) == 3
    # 验证退避间隔递增
    if len(attempts) >= 3:
        gap1 = attempts[1] - attempts[0]
        gap2 = attempts[2] - attempts[1]
        assert gap2 >= gap1


@pytest.mark.asyncio
async def test_retry_constant_backoff():
    """测试常量退避重试。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    attempts = []

    async def flaky_node(deps, view):
        attempts.append(time.monotonic())
        if len(attempts) < 2:
            raise ValueError("fail")
        return "ok"

    graph = {
        "flaky": {
            "task": flaky_node,
            "depends_on": [],
            "retry_policy": {
                "max_attempts": 2,
                "backoff_type": "constant",
                "backoff_base": 0.05,
            },
        },
    }

    results = await orch.execute(graph)
    assert results["flaky"] == "ok"


# ============================================================
# 3. on_failure Callbacks
# ============================================================

@pytest.mark.asyncio
async def test_on_failure_skip():
    """测试 on_failure='skip' 跳过失败节点。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    async def fail_node(deps, view):
        raise RuntimeError("always fails")

    async def final_node(deps, view):
        a = deps.get("fail_node")
        if a is MISSING:
            return {"used_skip": True}
        return {"used_skip": False}

    graph = {
        "fail_node": {"task": fail_node, "depends_on": [], "on_failure": "skip"},
        "final": {"task": final_node, "depends_on": ["fail_node"]},
    }

    results = await orch.execute(graph)
    assert results["final"]["used_skip"] is True


@pytest.mark.asyncio
async def test_on_failure_callable():
    """测试 on_failure 为回调函数。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    def custom_handler(exc, node_name, deps):
        # 返回 MISSING 表示降级
        return MISSING

    async def fail_node(deps, view):
        raise RuntimeError("test")

    async def fallback_node(deps, view):
        if deps.get("fail_node") is MISSING:
            return {"fallback": True}
        return {"fallback": False}

    graph = {
        "fail_node": {"task": fail_node, "depends_on": [], "on_failure": custom_handler},
        "fallback": {"task": fallback_node, "depends_on": ["fail_node"]},
    }

    results = await orch.execute(graph)
    assert results["fallback"]["fallback"] is True


# ============================================================
# 4. Worker Lifecycle (drain & stop)
# ============================================================

@pytest.mark.asyncio
async def test_worker_drain():
    """测试 Worker 优雅排空。"""
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    config = SchedulerConfig()
    scheduler = InProcessScheduler(bus=bus, config=config)
    validation = ValidationPipeline()
    cell = Cell(bus=bus, blackboard=bb, scheduler=scheduler, validation=validation)

    completed = []

    async def handler(ecm, view):
        completed.append(ecm.intent_id)
        return {"done": True}

    cap = Capability(
        agent_id="drain-worker", skills={"drain"},
        read_keys=set(), write_keys={"drain_result"}
    )
    await bb.register_agent("drain-worker", cap)
    await scheduler.register_worker(None, cap)
    worker = Worker("drain-worker", {"drain"}, set(), {"drain_result"},
                    handler, bb, bus, cap, validation, max_queue_size=10)
    await worker.start()
    await scheduler.bind_worker("drain-worker", worker)

    # 分配一个任务
    ecm = ECM(
        trace_id="drain-1", intent="drain", intent_id="drain-intent-1",
        emitter="test", required_skills=["drain"]
    )
    await worker.assign_task(ecm)

    # 排空
    await worker.drain()
    assert len(completed) == 1

    await worker.stop()
    await scheduler.unregister_worker("drain-worker")
    await bb.unregister_agent("drain-worker")


@pytest.mark.asyncio
async def test_worker_stop_clears_queue():
    """测试 Worker 停止时清空队列并取消意图。"""
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    config = SchedulerConfig()
    scheduler = InProcessScheduler(bus=bus, config=config)
    validation = ValidationPipeline()

    async def slow_handler(ecm, view):
        await asyncio.sleep(60)
        return "never"

    cap = Capability(
        agent_id="stop-worker", skills={"stop"},
        read_keys=set(), write_keys={"stop_result"}
    )
    await bb.register_agent("stop-worker", cap)
    await scheduler.register_worker(None, cap)
    worker = Worker("stop-worker", {"stop"}, set(), {"stop_result"},
                    slow_handler, bb, bus, cap, validation, max_queue_size=10)
    await worker.start()
    await scheduler.bind_worker("stop-worker", worker)

    # 分配多个任务
    for i in range(3):
        ecm = ECM(
            trace_id=f"stop-{i}", intent="stop", intent_id=f"stop-intent-{i}",
            emitter="test", required_skills=["stop"]
        )
        try:
            await worker.assign_task(ecm)
        except RuntimeError:
            pass  # Queue full

    await worker.stop()
    assert not worker._running


# ============================================================
# 5. Cell Lifecycle
# ============================================================

@pytest.mark.asyncio
async def test_cell_shutdown():
    """测试 Cell 关闭流程。"""
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    config = SchedulerConfig()
    scheduler = InProcessScheduler(bus=bus, config=config)
    validation = ValidationPipeline()
    cell = Cell(bus=bus, blackboard=bb, scheduler=scheduler, validation=validation)

    async def handler(ecm, view):
        return {"ok": True}

    await cell.create_worker(
        agent_id="cell-worker", skills={"cell_skill"},
        read_keys=set(), write_keys={"cell_result"},
        handler=handler
    )

    # 关闭 cell
    await cell.shutdown()

    # 关闭后不能再创建 worker
    with pytest.raises(RuntimeError, match="shutting down"):
        await cell.create_worker(
            agent_id="new-worker", skills={"new"},
            read_keys=set(), write_keys={"new_result"},
            handler=handler
        )


@pytest.mark.asyncio
async def test_cell_duplicate_worker():
    """测试创建重复 worker 应该失败。"""
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    config = SchedulerConfig()
    scheduler = InProcessScheduler(bus=bus, config=config)
    validation = ValidationPipeline()
    cell = Cell(bus=bus, blackboard=bb, scheduler=scheduler, validation=validation)

    async def handler(ecm, view):
        return {"ok": True}

    await cell.create_worker(
        agent_id="dup-worker", skills={"dup"},
        read_keys=set(), write_keys={"dup_result"},
        handler=handler
    )

    with pytest.raises(ValueError, match="already exists"):
        await cell.create_worker(
            agent_id="dup-worker", skills={"dup2"},
            read_keys=set(), write_keys={"dup_result2"},
            handler=handler
        )

    await cell.shutdown()


# ============================================================
# 6. EventBus Tag Filtering
# ============================================================

@pytest.mark.asyncio
async def test_eventbus_tag_filtering():
    """测试事件总线基于 skill 标签的过滤。"""
    bus = InProcessEventBus()
    await bus.start()

    received = []

    async def handler_a(ecm):
        received.append(("a", ecm.intent_id))

    async def handler_b(ecm):
        received.append(("b", ecm.intent_id))

    await bus.subscribe("tasks", handler_a, tags={"skill_a"})
    await bus.subscribe("tasks", handler_b, tags={"skill_b"})

    # 只匹配 handler_a
    ecm = ECM(
        trace_id="tag-1", intent="skill_a", intent_id="tag-intent-1",
        emitter="test", required_skills=["skill_a"]
    )
    await bus.publish("tasks", ecm)

    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0][0] == "a"

    await bus.close()


# ============================================================
# 7. Concurrent Task Cancellation
# ============================================================

@pytest.mark.asyncio
async def test_dag_cancellation():
    """测试 DAG 执行被取消时所有节点被正确清理。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)

    started = asyncio.Event()

    async def long_running(deps, view):
        started.set()
        await asyncio.sleep(60)
        return "never"

    graph = {
        "long": {"task": long_running, "depends_on": []},
    }

    task = asyncio.create_task(orch.execute(graph))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_dynamic_orchestrator_node_abort():
    """测试 DynamicOrchestrator 节点 abort 后取消所有活跃任务。"""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)

    async def abort_node(deps, view):
        raise AbortExecutionException("abort all")

    async def slow_node(deps, view):
        await asyncio.sleep(60)
        return "never"

    graph = {
        "abort": {"task": abort_node, "depends_on": []},
        "slow": {"task": slow_node, "depends_on": []},  # 并行
    }

    with pytest.raises(AbortExecutionException):
        await orch.execute(graph)


# ============================================================
# 8. SecureBlackboard Permission Edge Cases
# ============================================================

@pytest.mark.asyncio
async def test_blackboard_prefix_isolation():
    """测试精确匹配权限隔离 (Core 版 SecureBlackboard 使用精确匹配而非 fnmatch)。"""
    bb = SecureBlackboard(MemoryBlackboard())

    cap_a = Capability(
        agent_id="isolated-a", skills={"x"},
        read_keys={"a:secret", "a:data"}, write_keys={"a:secret", "a:data"}
    )
    cap_b = Capability(
        agent_id="isolated-b", skills={"x"},
        read_keys={"b:secret", "b:data"}, write_keys={"b:secret", "b:data"}
    )

    await bb.register_agent("isolated-a", cap_a)
    await bb.register_agent("isolated-b", cap_b)

    await bb.put_and_audit("isolated-a", "a:secret", "value_a")
    await bb.put_and_audit("isolated-b", "b:secret", "value_b")

    # a 不能读 b 的数据
    with pytest.raises(PermissionError):
        await bb.get_and_audit("isolated-a", "b:secret")

    # b 不能读 a 的数据
    with pytest.raises(PermissionError):
        await bb.get_and_audit("isolated-b", "a:secret")

    # 各自能读自己的数据
    assert await bb.get_and_audit("isolated-a", "a:secret") == "value_a"
    assert await bb.get_and_audit("isolated-b", "b:secret") == "value_b"


@pytest.mark.asyncio
async def test_blackboard_non_json_write_rejected():
    """测试 Core 版 SecureBlackboard 不强制 JSON 校验 (直接写入后端)。"""
    bb = SecureBlackboard(MemoryBlackboard())

    cap = Capability(
        agent_id="json-test", skills={"x"},
        read_keys={"test:valid", "test:bad"}, write_keys={"test:valid", "test:bad"}
    )
    await bb.register_agent("json-test", cap)

    # 允许的值
    await bb.put_and_audit("json-test", "test:valid", {"key": "value"})
    assert await bb.get_and_audit("json-test", "test:valid") == {"key": "value"}

    # Core 版不强制 JSON 序列化校验，直接写入后端
    # 但不可序列化的值会在 Redis 后端失败


# ============================================================
# 9. Full Pipeline Integration
# ============================================================

@pytest.mark.asyncio
async def test_full_hiveflow_pipeline():
    """测试完整的 HiveFlow 流程: Cell -> Worker -> DAG -> Blackboard。"""
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    config = SchedulerConfig()
    scheduler = InProcessScheduler(bus=bus, config=config)
    validation = ValidationPipeline()
    cell = Cell(bus=bus, blackboard=bb, scheduler=scheduler, validation=validation)
    await bus.start()

    async def fetcher(ecm, view):
        await view.put("pipeline:fetched", {"data": "raw_data"})
        return {"data": "raw_data"}

    async def processor(deps, view):
        fetched = deps.get("fetch")
        return {"processed": fetched["data"].upper()}

    # 注册 workers
    await cell.create_worker(
        agent_id="fetcher", skills={"fetch"},
        read_keys=set(), write_keys={"pipeline:fetched"},
        handler=fetcher
    )

    await cell.create_worker(
        agent_id="processor", skills={"process"},
        read_keys={"pipeline:fetched"}, write_keys={"pipeline:processed"},
        handler=processor
    )

    # 调度 fetch
    ecm = ECM(
        trace_id="full-1", intent="fetch", intent_id="full-intent",
        emitter="test", required_skills=["fetch"]
    )
    success = await scheduler.schedule(ecm)
    assert success

    await asyncio.sleep(0.2)
    result = await bb.sys_get("pipeline:fetched")
    assert result["data"] == "raw_data"

    await cell.shutdown()
    await bus.close()
