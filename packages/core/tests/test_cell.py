import pytest
import asyncio
from hiveflow import Cell, ECM, Capability
from hiveflow.bus import InProcessEventBus
from hiveflow.blackboard import SecureBlackboard, MemoryBlackboard
from hiveflow.scheduler import InProcessScheduler, SchedulerConfig
from hiveflow.validation import ValidationPipeline


async def simple_handler(ecm, view):
    return "handled"


@pytest.fixture
def setup_env():
    bus = InProcessEventBus()
    bb = SecureBlackboard(MemoryBlackboard())
    sched = InProcessScheduler(bus=bus, config=SchedulerConfig())
    val = ValidationPipeline()
    cell = Cell(bus=bus, blackboard=bb, scheduler=sched, validation=val)
    return cell, bus, bb, sched


@pytest.mark.asyncio
async def test_cell_create_worker(setup_env):
    cell, bus, bb, sched = setup_env
    worker = await cell.create_worker(
        agent_id="test_worker",
        skills={"test"},
        read_keys={"test:*"},
        write_keys={"test:*"},
        handler=simple_handler
    )
    assert worker is not None
    assert worker.agent_id == "test_worker"
    await cell.stop_worker("test_worker")


@pytest.mark.asyncio
async def test_cell_stop_worker(setup_env):
    cell, bus, bb, sched = setup_env
    await cell.create_worker(
        agent_id="stop_test",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
        handler=simple_handler
    )
    await cell.stop_worker("stop_test")
    assert "stop_test" not in cell._workers


@pytest.mark.asyncio
async def test_cell_double_worker_error(setup_env):
    cell, bus, bb, sched = setup_env
    await cell.create_worker(
        agent_id="dup_worker",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
        handler=simple_handler
    )
    with pytest.raises(ValueError, match="already exists"):
        await cell.create_worker(
            agent_id="dup_worker",
            skills={"test2"},
            read_keys={"*"},
            write_keys={"*"},
            handler=simple_handler
        )
    await cell.stop_worker("dup_worker")
