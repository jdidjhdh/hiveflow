import asyncio
import time

import pytest

from hiveflow import (
    Capability,
    InProcessEventBus,
    InProcessScheduler,
    LeastLoadedStrategy,
    MemoryBlackboard,
    SchedulerConfig,
    SecureBlackboard,
    TTLMemoryBlackboard,
)


# --- Performance test: Blackboard throughput ---
@pytest.mark.asyncio
async def test_blackboard_put_get_throughput():
    bb = SecureBlackboard(MemoryBlackboard())
    n = 1000

    start = time.monotonic()
    for i in range(n):
        await bb.sys_put(f"key_{i}", f"value_{i}")
    for i in range(n):
        await bb.sys_get(f"key_{i}")
    elapsed = time.monotonic() - start
    if elapsed == 0:
        elapsed = 0.001
    ops_per_sec = (2 * n) / elapsed
    # Should handle at least 1000 ops/sec on in-memory
    assert ops_per_sec > 1000, f"Blackboard too slow: {ops_per_sec:.0f} ops/sec"


@pytest.mark.asyncio
async def test_blackboard_concurrent_access():
    bb = SecureBlackboard(MemoryBlackboard())
    n_writers = 10
    writes_per_writer = 100

    async def writer(agent_id, count):
        for i in range(count):
            await bb.sys_put(f"{agent_id}_key_{i}", f"value_{i}")

    tasks = [writer(f"agent-{w}", writes_per_writer) for w in range(n_writers)]
    await asyncio.gather(*tasks)

    # Verify all keys are present
    for w in range(n_writers):
        for i in range(writes_per_writer):
            val = await bb.sys_get(f"agent-{w}_key_{i}")
            assert val == f"value_{i}"


@pytest.mark.asyncio
async def test_scheduler_task_distribution():
    bus = InProcessEventBus()
    config = SchedulerConfig()
    sched = InProcessScheduler(bus=bus, config=config)

    await sched.start()

    # Register multiple workers
    for i in range(5):
        cap = Capability(
            agent_id=f"agent-{i}",
            skills={f"skill-{i}"},
            read_keys=set(),
            write_keys=set(),
        )
        await sched.register_worker(None, cap)

    # Verify all workers registered
    assert len(sched._capabilities) == 5

    await sched.close()


@pytest.mark.asyncio
async def test_scheduler_least_loaded_strategy():
    bus = InProcessEventBus()
    config = SchedulerConfig()
    sched = InProcessScheduler(bus=bus, config=config)
    await sched.set_strategy(LeastLoadedStrategy())

    await sched.start()

    # Register workers with different loads
    agents = [
        ("agent-heavy", 0.8),
        ("agent-light", 0.1),
        ("agent-medium", 0.5),
    ]
    for agent_id, load in agents:
        cap = Capability(
            agent_id=agent_id,
            skills={"test_skill"},
            read_keys=set(),
            write_keys=set(),
        )
        cap.load = load
        cap.history = [load]
        cap.pending_tasks = int(load * 10)
        cap.state = "running"
        # Use a mock worker reference so it's added to worker_queues
        mock_worker = type('MockWorker', (), {'agent_id': agent_id})()
        await sched.register_worker(mock_worker, cap)

    # Strategy should prefer least loaded
    from hiveflow import ECM
    ecm = ECM(
        trace_id='test',
        intent='test',
        intent_id='test-intent',
        emitter='test',
        required_skills=['test_skill'],
        priority='normal',
        payload={},
        timestamp=time.monotonic(),
    )

    selected = await sched.strategy.select(ecm, sched._capabilities, sched._worker_queues)
    # Should select agent-light (lowest load)
    assert selected[0] == "agent-light"

    await sched.close()


@pytest.mark.asyncio
async def test_blackboard_ttl_performance():
    bb = SecureBlackboard(TTLMemoryBlackboard(default_ttl=60.0))
    n = 500

    start = time.monotonic()
    for i in range(n):
        await bb.sys_put(f"ttl_key_{i}", f"value_{i}", ttl=30.0)
    write_time = time.monotonic() - start

    # Verify all
    for i in range(n):
        val = await bb.sys_get(f"ttl_key_{i}")
        assert val == f"value_{i}"

    # Write time should be reasonable (< 1 sec for 500 items)
    assert write_time < 1.0, f"TTL write too slow: {write_time:.2f}s"


@pytest.mark.asyncio
async def test_concurrent_blackboard_latency():
    """Measure P50 and P99 latency of concurrent blackboard operations."""
    import statistics
    bb = SecureBlackboard(MemoryBlackboard())
    latencies = []
    n_ops = 200
    n_workers = 10

    async def worker(worker_id, count):
        for i in range(count):
            key = f"w{worker_id}_k{i}"
            start = time.monotonic()
            await bb.sys_put(key, f"v{i}")
            await bb.sys_get(key)
            elapsed = (time.monotonic() - start) * 1000  # ms
            latencies.append(elapsed)

    tasks = [worker(w, n_ops // n_workers) for w in range(n_workers)]
    await asyncio.gather(*tasks)

    if latencies:
        p50 = statistics.median(latencies)
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        # P50 < 10ms, P99 < 100ms for in-memory operations
        assert p50 < 10, f"P50 latency too high: {p50:.2f}ms"
        assert p99 < 100, f"P99 latency too high: {p99:.2f}ms"


@pytest.mark.asyncio
async def test_scheduler_capacity_under_load():
    """Test scheduler can handle rapid sequential scheduling."""
    bus = InProcessEventBus()
    config = SchedulerConfig()
    sched = InProcessScheduler(bus=bus, config=config)

    await sched.start()

    # Register a single worker
    cap = Capability(
        agent_id='agent-1',
        skills={'fast_skill'},
        read_keys=set(),
        write_keys=set(),
    )
    cap.max_queue_size = 1000
    cap.state = "running"
    mock_worker = type('MockWorker', (), {'agent_id': 'agent-1'})()
    await sched.register_worker(mock_worker, cap)

    n_tasks = 100
    from hiveflow import ECM
    start = time.monotonic()
    for i in range(n_tasks):
        ecm = ECM(
            trace_id=f'task-{i}',
            intent='test',
            intent_id=f'intent-{i}',
            emitter='test',
            required_skills=['fast_skill'],
            priority='normal',
            payload={},
            timestamp=time.monotonic(),
        )
        await sched.schedule(ecm)
    elapsed = time.monotonic() - start

    # Ensure elapsed is non-zero
    if elapsed == 0:
        elapsed = 0.001

    tasks_per_sec = n_tasks / elapsed
    assert tasks_per_sec > 100, f"Scheduling too slow: {tasks_per_sec:.0f} tasks/sec"

    await sched.close()
