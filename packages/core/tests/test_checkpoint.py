"""Tests for hiveflow checkpoint module."""
import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch

from hiveflow import Checkpoint, CheckpointManager, CheckpointBackend, MemoryCheckpointBackend


class TestCheckpoint:
    def test_create_minimal(self):
        cp = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=time.time(),
            state={"key": "value"},
        )
        assert cp.checkpoint_id == "cp_001"
        assert cp.workflow_id == "wf_001"
        assert cp.state == {"key": "value"}
        assert cp.metadata == {}
        assert cp.parent_id is None
        assert cp.branch_name is None

    def test_create_full(self):
        cp = Checkpoint(
            checkpoint_id="cp_002",
            workflow_id="wf_001",
            timestamp=1234567890.0,
            state={"nodes": {"step1": "done"}},
            metadata={"description": "After step 1"},
            parent_id="cp_001",
            branch_name="experiment_A",
        )
        assert cp.metadata == {"description": "After step 1"}
        assert cp.parent_id == "cp_001"
        assert cp.branch_name == "experiment_A"


class TestMemoryCheckpointBackend:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        backend = MemoryCheckpointBackend()
        cp = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=time.time(),
            state={"data": "test"},
        )
        result = await backend.save(cp)
        assert result == "cp_001"

        loaded = await backend.load("cp_001")
        assert loaded is not None
        assert loaded.checkpoint_id == "cp_001"
        assert loaded.state == {"data": "test"}

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self):
        backend = MemoryCheckpointBackend()
        result = await backend.load("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        backend = MemoryCheckpointBackend()
        cp1 = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=1000.0,
            state={"step": 1},
        )
        cp2 = Checkpoint(
            checkpoint_id="cp_002",
            workflow_id="wf_001",
            timestamp=2000.0,
            state={"step": 2},
        )
        await backend.save(cp1)
        await backend.save(cp2)

        cps = await backend.list_checkpoints("wf_001")
        assert len(cps) == 2
        assert cps[0].checkpoint_id == "cp_001"
        assert cps[1].checkpoint_id == "cp_002"

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty_workflow(self):
        backend = MemoryCheckpointBackend()
        cps = await backend.list_checkpoints("nonexistent")
        assert cps == []

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        backend = MemoryCheckpointBackend()
        cp = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=time.time(),
            state={"data": "test"},
        )
        await backend.save(cp)

        result = await backend.delete("cp_001")
        assert result is True

        loaded = await backend.load("cp_001")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        backend = MemoryCheckpointBackend()
        result = await backend.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_from_index(self):
        backend = MemoryCheckpointBackend()
        cp = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=time.time(),
            state={},
        )
        await backend.save(cp)
        await backend.delete("cp_001")

        cps = await backend.list_checkpoints("wf_001")
        assert cps == []

    @pytest.mark.asyncio
    async def test_multiple_workflows(self):
        backend = MemoryCheckpointBackend()
        cp1 = Checkpoint(
            checkpoint_id="cp_001",
            workflow_id="wf_001",
            timestamp=time.time(),
            state={"wf": 1},
        )
        cp2 = Checkpoint(
            checkpoint_id="cp_002",
            workflow_id="wf_002",
            timestamp=time.time(),
            state={"wf": 2},
        )
        await backend.save(cp1)
        await backend.save(cp2)

        wf1_cps = await backend.list_checkpoints("wf_001")
        wf2_cps = await backend.list_checkpoints("wf_002")
        assert len(wf1_cps) == 1
        assert len(wf2_cps) == 1


class TestCheckpointManager:
    @pytest.mark.asyncio
    async def test_save_checkpoint(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        cp_id = await mgr.save_checkpoint(
            workflow_id="wf_001",
            state={"nodes": {"step1": "done"}},
            metadata={"desc": "Test"},
        )
        assert cp_id is not None
        assert len(cp_id) == 12

    @pytest.mark.asyncio
    async def test_restore_checkpoint(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        cp_id = await mgr.save_checkpoint(
            workflow_id="wf_001",
            state={"data": "original"},
        )
        restored = await mgr.restore_checkpoint(cp_id)
        assert restored is not None
        assert restored.checkpoint_id == cp_id
        assert restored.state == {"data": "original"}

    @pytest.mark.asyncio
    async def test_restore_nonexistent(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        result = await mgr.restore_checkpoint("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        await mgr.save_checkpoint("wf_001", {"step": 1})
        await mgr.save_checkpoint("wf_001", {"step": 2})

        cps = await mgr.list_checkpoints("wf_001")
        assert len(cps) == 2

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        cp_id = await mgr.save_checkpoint("wf_001", {"data": "test"})
        result = await mgr.delete_checkpoint(cp_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_fork_from_checkpoint(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        original_id = await mgr.save_checkpoint(
            "wf_001", {"data": "original"},
            metadata={"version": 1},
        )
        fork_id = await mgr.fork(original_id, "experiment_A")
        assert fork_id is not None
        assert fork_id != original_id

        fork_cp = await backend.load(fork_id)
        assert fork_cp is not None
        assert fork_cp.parent_id == original_id
        assert fork_cp.branch_name == "experiment_A"
        assert fork_cp.metadata["forked_from"] == original_id

    @pytest.mark.asyncio
    async def test_fork_nonexistent_parent(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        result = await mgr.fork("nonexistent", "branch")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_timeline(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        cp1_id = await mgr.save_checkpoint("wf_001", {"step": 1})
        cp2_id = await mgr.save_checkpoint(
            "wf_001", {"step": 2}, parent_id=cp1_id
        )

        timeline = await mgr.get_checkpoint_timeline("wf_001")
        assert len(timeline) == 2
        assert timeline[0]["checkpoint_id"] == cp1_id
        assert timeline[1]["parent_id"] == cp1_id
        assert "state_keys" in timeline[0]
        assert "step" in timeline[0]["state_keys"]

    @pytest.mark.asyncio
    async def test_get_current_state(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        assert mgr.get_current_state("wf_001") is None

        await mgr.save_checkpoint("wf_001", {"data": "current"})
        state = mgr.get_current_state("wf_001")
        assert state == {"data": "current"}

    @pytest.mark.asyncio
    async def test_get_current_state_nonexistent(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        result = mgr.get_current_state("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_updates_current_state(self):
        backend = MemoryCheckpointBackend()
        mgr = CheckpointManager(backend)

        await mgr.save_checkpoint("wf_001", {"version": 1})
        await mgr.save_checkpoint("wf_001", {"version": 2})

        state = mgr.get_current_state("wf_001")
        assert state == {"version": 2}
