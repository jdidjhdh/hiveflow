"""HiveFlow - Checkpoint System

Provides state persistence and time-travel capability for workflow execution.
Similar to LangGraph's Checkpointer but integrated with HiveFlow's blackboard system.

Features:
- Save/restore workflow state at any point
- Time-travel: rewind to any previous checkpoint
- Branching: fork execution from any checkpoint
- Multiple backends (Memory, SQLite)
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """A saved workflow state snapshot."""
    checkpoint_id: str
    workflow_id: str
    timestamp: float
    state: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None  # For branching
    branch_name: Optional[str] = None


class CheckpointBackend(ABC):
    """Abstract base class for checkpoint storage."""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> str:
        ...

    @abstractmethod
    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        ...

    @abstractmethod
    async def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> bool:
        ...


class MemoryCheckpointBackend(CheckpointBackend):
    """In-memory checkpoint storage (for testing/development)."""

    def __init__(self):
        self._store: Dict[str, Checkpoint] = {}
        self._index: Dict[str, List[str]] = {}  # workflow_id -> [checkpoint_id]

    async def save(self, checkpoint: Checkpoint) -> str:
        self._store[checkpoint.checkpoint_id] = checkpoint
        wf_id = checkpoint.workflow_id
        if wf_id not in self._index:
            self._index[wf_id] = []
        self._index[wf_id].append(checkpoint.checkpoint_id)
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._store.get(checkpoint_id)

    async def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        ids = self._index.get(workflow_id, [])
        return [self._store[cid] for cid in ids if cid in self._store]

    async def delete(self, checkpoint_id: str) -> bool:
        if checkpoint_id in self._store:
            cp = self._store.pop(checkpoint_id)
            wf_ids = self._index.get(cp.workflow_id, [])
            if checkpoint_id in wf_ids:
                wf_ids.remove(checkpoint_id)
            return True
        return False


try:
    import aiosqlite

    class SQLiteCheckpointBackend(CheckpointBackend):
        """SQLite-based checkpoint storage (persistent)."""

        def __init__(self, db_path: str = "hiveflow_checkpoints.db"):
            self.db_path = db_path
            self._initialized = False

        async def _ensure_db(self):
            if self._initialized:
                return
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        state TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        parent_id TEXT,
                        branch_name TEXT
                    )
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_workflow
                    ON checkpoints(workflow_id)
                """)
                await db.commit()
            self._initialized = True

        async def save(self, checkpoint: Checkpoint) -> str:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        checkpoint.checkpoint_id,
                        checkpoint.workflow_id,
                        checkpoint.timestamp,
                        json.dumps(checkpoint.state, default=str),
                        json.dumps(checkpoint.metadata, default=str),
                        checkpoint.parent_id,
                        checkpoint.branch_name,
                    ),
                )
                await db.commit()
            return checkpoint.checkpoint_id

        async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                ) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return None
            return Checkpoint(
                checkpoint_id=row[0],
                workflow_id=row[1],
                timestamp=row[2],
                state=json.loads(row[3]),
                metadata=json.loads(row[4]),
                parent_id=row[5],
                branch_name=row[6],
            )

        async def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY timestamp",
                    (workflow_id,),
                ) as cursor:
                    rows = await cursor.fetchall()
            return [
                Checkpoint(
                    checkpoint_id=r[0],
                    workflow_id=r[1],
                    timestamp=r[2],
                    state=json.loads(r[3]),
                    metadata=json.loads(r[4]),
                    parent_id=r[5],
                    branch_name=r[6],
                )
                for r in rows
            ]

        async def delete(self, checkpoint_id: str) -> bool:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                await db.commit()
            return cursor.rowcount > 0
except ImportError:
    SQLiteCheckpointBackend = None  # type: ignore


class CheckpointManager:
    """
    Manages workflow checkpoints with time-travel and branching support.

    Usage:
        mgr = CheckpointManager(MemoryCheckpointBackend())

        # Save a checkpoint
        await mgr.save_checkpoint(
            workflow_id="wf_001",
            state={"nodes": {"step1": "completed"}},
            metadata={"description": "After step 1"},
        )

        # List all checkpoints for a workflow
        cps = await mgr.list_checkpoints("wf_001")

        # Restore to a checkpoint
        cp = await mgr.restore_checkpoint(cps[0].checkpoint_id)

        # Fork from a checkpoint
        fork_id = await mgr.fork(
            parent_checkpoint_id=cps[0].checkpoint_id,
            branch_name="experiment_A",
        )
    """

    def __init__(self, backend: CheckpointBackend):
        self.backend = backend
        self._current_states: Dict[str, Checkpoint] = {}  # workflow_id -> current checkpoint

    async def save_checkpoint(
        self,
        workflow_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> str:
        """Save the current workflow state as a checkpoint."""
        import uuid
        cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            workflow_id=workflow_id,
            timestamp=time.time(),
            state=state,
            metadata=metadata or {},
            parent_id=parent_id,
            branch_name=branch_name,
        )
        await self.backend.save(cp)
        self._current_states[workflow_id] = cp
        logger.info(f"Checkpoint saved: {cp.checkpoint_id} for workflow {workflow_id}")
        return cp.checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Restore workflow state from a checkpoint."""
        cp = await self.backend.load(checkpoint_id)
        if cp:
            self._current_states[cp.workflow_id] = cp
            logger.info(f"Restored to checkpoint: {checkpoint_id}")
        return cp

    async def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        """List all checkpoints for a workflow, ordered by timestamp."""
        return await self.backend.list_checkpoints(workflow_id)

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        return await self.backend.delete(checkpoint_id)

    async def fork(
        self,
        parent_checkpoint_id: str,
        branch_name: str = "",
    ) -> Optional[str]:
        """Fork execution from a checkpoint, creating a new branch."""
        parent = await self.backend.load(parent_checkpoint_id)
        if not parent:
            return None

        import uuid
        fork_cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            workflow_id=parent.workflow_id,
            timestamp=time.time(),
            state=dict(parent.state),  # Deep copy would be better
            metadata={
                "forked_from": parent_checkpoint_id,
                "branch": branch_name,
                **parent.metadata,
            },
            parent_id=parent_checkpoint_id,
            branch_name=branch_name,
        )
        await self.backend.save(fork_cp)
        self._current_states[parent.workflow_id] = fork_cp
        logger.info(f"Forked from {parent_checkpoint_id} -> {fork_cp.checkpoint_id}")
        return fork_cp.checkpoint_id

    async def get_checkpoint_timeline(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get a timeline of checkpoints with parent/branch relationships."""
        checkpoints = await self.list_checkpoints(workflow_id)
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "timestamp": cp.timestamp,
                "parent_id": cp.parent_id,
                "branch_name": cp.branch_name,
                "metadata": cp.metadata,
                "state_keys": list(cp.state.keys()),
            }
            for cp in checkpoints
        ]

    def get_current_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get the current active state for a workflow."""
        cp = self._current_states.get(workflow_id)
        return cp.state if cp else None
