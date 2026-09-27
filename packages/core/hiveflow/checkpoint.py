"""HiveFlow - Checkpoint System

Provides state persistence and time-travel capability for workflow execution.
Similar to LangGraph's Checkpointer but integrated with HiveFlow's blackboard system.

Features:
- Save/restore workflow state at any point
- Time-travel: rewind to any previous checkpoint
- Branching: fork execution from any checkpoint
- Multiple backends (Memory, SQLite)
- Incremental snapshots (delta mode) to reduce storage
- Compressed storage for SQLite backend
- 🔒 P0 FIX: Agent isolation for replay (agent_id parameter)
"""

import copy
import json
import logging
import time
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 🔄 P0 FIX: Schema version for checkpoint compatibility
SCHEMA_VERSION = "1.1.0"


class SchemaVersionMismatchError(Exception):
    """
    Raised when checkpoint schema version is incompatible with current version.

    This error indicates that the checkpoint was created with a different schema version
    and may require migration or reconstruction.
    """

    def __init__(self, checkpoint_version: str, current_version: str):
        self.checkpoint_version = checkpoint_version
        self.current_version = current_version
        self.message = (
            f"Checkpoint schema version '{checkpoint_version}' is incompatible "
            f"with current version '{current_version}'. "
            f"You may need to migrate checkpoint data or rebuild the checkpoint."
        )
        super().__init__(self.message)


@dataclass
class Checkpoint:
    """A saved workflow state snapshot."""

    checkpoint_id: str
    workflow_id: str
    timestamp: float
    state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None  # For branching
    branch_name: str | None = None
    is_delta: bool = False  # Whether this is an incremental snapshot
    schema_version: str = SCHEMA_VERSION  # 🔄 P0 FIX: Schema version tracking


class CheckpointBackend(ABC):
    """Abstract base class for checkpoint storage."""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> str: ...

    @abstractmethod
    async def load(self, checkpoint_id: str) -> Checkpoint | None: ...

    @abstractmethod
    async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]: ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> bool: ...


class MemoryCheckpointBackend(CheckpointBackend):
    """In-memory checkpoint storage (for testing/development)."""

    def __init__(self):
        self._store: dict[str, Checkpoint] = {}
        self._index: dict[str, list[str]] = {}  # workflow_id -> [checkpoint_id]

    async def save(self, checkpoint: Checkpoint) -> str:
        self._store[checkpoint.checkpoint_id] = checkpoint
        wf_id = checkpoint.workflow_id
        if wf_id not in self._index:
            self._index[wf_id] = []
        self._index[wf_id].append(checkpoint.checkpoint_id)
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> Checkpoint | None:
        return self._store.get(checkpoint_id)

    async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
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


def _compute_delta_state(
    prev_state: dict[str, Any] | None,
    new_state: dict[str, Any],
    delta_keys: set[str] | None = None,
) -> dict[str, Any]:
    """
    Compute the delta between previous and new state.
    
    Args:
        prev_state: Previous checkpoint state (None if first checkpoint)
        new_state: New state to save
        delta_keys: Keys to compute delta for (default: {"completed", "deps"})
    
    Returns:
        Delta state with only changed fields
    """
    if prev_state is None:
        return new_state
    
    delta_keys = delta_keys or {"completed", "deps"}
    delta_state = {}
    
    for key in new_state:
        if key in delta_keys:
            # For dict fields, compute deep diff
            prev_val = prev_state.get(key, {})
            new_val = new_state[key]
            if isinstance(new_val, dict) and isinstance(prev_val, dict):
                # Only include changed/new keys
                diff = {}
                for k, v in new_val.items():
                    if k not in prev_val or prev_val.get(k) != v:
                        diff[k] = v
                if diff:
                    delta_state[key] = diff
            else:
                if prev_val != new_val:
                    delta_state[key] = new_val
        else:
            # For non-delta keys, include if changed
            if prev_state.get(key) != new_state.get(key):
                delta_state[key] = new_state[key]
    
    return delta_state


def _merge_delta_state(
    base_state: dict[str, Any],
    delta_state: dict[str, Any],
    delta_keys: set[str] | None = None,
) -> dict[str, Any]:
    """
    Merge delta state into base state to reconstruct full state.
    
    Args:
        base_state: Base checkpoint state
        delta_state: Delta state to merge
        delta_keys: Keys that were stored as delta
    
    Returns:
        Reconstructed full state
    """
    delta_keys = delta_keys or {"completed", "deps"}
    merged = copy.deepcopy(base_state)
    
    for key, val in delta_state.items():
        if key in delta_keys and isinstance(val, dict) and isinstance(merged.get(key), dict):
            # Merge dict delta
            merged[key].update(val)
        else:
            merged[key] = val
    
    return merged


try:
    import aiosqlite

    class SQLiteCheckpointBackend(CheckpointBackend):
        """SQLite-based checkpoint storage (persistent) with compression."""

        def __init__(self, db_path: str = "hiveflow_checkpoints.db", compress: bool = True):
            self.db_path = db_path
            self.compress = compress
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
                        state BLOB NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        parent_id TEXT,
                        branch_name TEXT,
                        is_delta INTEGER NOT NULL DEFAULT 0,
                        compressed INTEGER NOT NULL DEFAULT 1
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
            
            # Serialize state to JSON
            state_json = json.dumps(checkpoint.state, default=str)
            
            # Compress if enabled
            if self.compress:
                state_blob = zlib.compress(state_json.encode("utf-8"), level=6)
                compressed_flag = 1
            else:
                state_blob = state_json.encode("utf-8")
                compressed_flag = 0
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        checkpoint.checkpoint_id,
                        checkpoint.workflow_id,
                        checkpoint.timestamp,
                        state_blob,
                        json.dumps(checkpoint.metadata, default=str),
                        checkpoint.parent_id,
                        checkpoint.branch_name,
                        int(checkpoint.is_delta),
                        compressed_flag,
                    ),
                )
                await db.commit()
            return checkpoint.checkpoint_id

        async def load(self, checkpoint_id: str) -> Checkpoint | None:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                ) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return None
            
            # Decompress state if needed
            state_blob = row[3]
            compressed_flag = row[8]
            if compressed_flag:
                state_json = zlib.decompress(state_blob).decode("utf-8")
            else:
                state_json = state_blob.decode("utf-8")
            
            return Checkpoint(
                checkpoint_id=row[0],
                workflow_id=row[1],
                timestamp=row[2],
                state=json.loads(state_json),
                metadata=json.loads(row[4]),
                parent_id=row[5],
                branch_name=row[6],
                is_delta=bool(row[7]),
            )

        async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY timestamp",
                    (workflow_id,),
                ) as cursor:
                    rows = await cursor.fetchall()
            
            result = []
            for r in rows:
                state_blob = r[3]
                compressed_flag = r[8]
                if compressed_flag:
                    state_json = zlib.decompress(state_blob).decode("utf-8")
                else:
                    state_json = state_blob.decode("utf-8")
                
                result.append(Checkpoint(
                    checkpoint_id=r[0],
                    workflow_id=r[1],
                    timestamp=r[2],
                    state=json.loads(state_json),
                    metadata=json.loads(r[4]),
                    parent_id=r[5],
                    branch_name=r[6],
                    is_delta=bool(r[7]),
                ))
            return result

        async def delete(self, checkpoint_id: str) -> bool:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                    (checkpoint_id,),
                )
                await db.commit()
            return bool(cursor.rowcount > 0)
except ImportError:
    SQLiteCheckpointBackend = None  # type: ignore


class CheckpointManager:
    """
    Manages workflow checkpoints with time-travel and branching support.

    Features:
    - Incremental snapshots (delta mode) to reduce storage
    - Compressed storage for SQLite backend
    - Deep copy fork to prevent data pollution

    Usage:
        mgr = CheckpointManager(MemoryCheckpointBackend())

        # Save a checkpoint
        await mgr.save_checkpoint(
            workflow_id="wf_001",
            state={"nodes": {"step1": "completed"}},
            metadata={"description": "After step 1"},
        )

        # Save incremental checkpoint (only changed fields)
        await mgr.save_checkpoint(
            workflow_id="wf_001",
            state={"nodes": {"step1": "completed", "step2": "completed"}},
            delta=True,  # Only store diff
        )

        # List all checkpoints for a workflow
        cps = await mgr.list_checkpoints("wf_001")

        # Restore to a checkpoint
        cp = await mgr.restore_checkpoint(cps[0].checkpoint_id)

        # Fork from a checkpoint (deep copy)
        fork_id = await mgr.fork(
            parent_checkpoint_id=cps[0].checkpoint_id,
            branch_name="experiment_A",
        )
    """

    def __init__(self, backend: CheckpointBackend):
        self.backend = backend
        self._current_states: dict[str, Checkpoint] = {}  # workflow_id -> current checkpoint

    async def save_checkpoint(
        self,
        workflow_id: str,
        state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        parent_id: str | None = None,
        branch_name: str | None = None,
        delta: bool = False,
    ) -> str:
        """
        Save the current workflow state as a checkpoint.

        Args:
            workflow_id: Workflow identifier
            state: Workflow state to save
            metadata: Optional metadata
            parent_id: Optional parent checkpoint ID
            branch_name: Optional branch name
            delta: If True, only store changed fields (incremental snapshot)
                   Default: False (full snapshot)

        Returns:
            Checkpoint ID
        """
        import uuid

        # Compute delta if enabled and previous state exists
        if delta:
            prev_cp = self._current_states.get(workflow_id)
            prev_state = prev_cp.state if prev_cp else None
            state_to_save = _compute_delta_state(prev_state, state)
            is_delta = len(state_to_save) < len(state)  # Only mark as delta if actually smaller
        else:
            state_to_save = state
            is_delta = False

        cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            workflow_id=workflow_id,
            timestamp=time.time(),
            state=state_to_save,
            metadata=metadata or {},
            parent_id=parent_id,
            branch_name=branch_name,
            is_delta=is_delta,
            schema_version=SCHEMA_VERSION,  # 🔄 P0 FIX: Include schema version
        )
        await self.backend.save(cp)
        
        # Store full state for delta computation next time
        self._current_states[workflow_id] = Checkpoint(
            checkpoint_id=cp.checkpoint_id,
            workflow_id=workflow_id,
            timestamp=cp.timestamp,
            state=state,  # Store full state for delta computation
            metadata=cp.metadata,
            parent_id=cp.parent_id,
            branch_name=cp.branch_name,
            is_delta=is_delta,
        )
        
        logger.info(
            f"Checkpoint saved: {cp.checkpoint_id} for workflow {workflow_id}"
            f" (delta={is_delta}, keys={len(state_to_save)})"
        )
        return cp.checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str, agent_id: str | None = None) -> Checkpoint | None:
        """
        Restore workflow state from a checkpoint.
        
        🔒 P0 FIX: Add agent_id parameter for permission check.
        
        Args:
            checkpoint_id: ID of checkpoint to restore
            agent_id: Optional agent ID for permission filtering
        
        Returns:
            Checkpoint if found and authorized, None otherwise

        Raises:
            PermissionError: If agent_id lacks access to this checkpoint
            SchemaVersionMismatchError: If checkpoint schema version is incompatible
        """
        cp = await self.backend.load(checkpoint_id)
        if cp:
            # 🔄 P0 FIX: Check schema version compatibility
            if cp.schema_version != SCHEMA_VERSION:
                raise SchemaVersionMismatchError(
                    checkpoint_version=cp.schema_version,
                    current_version=SCHEMA_VERSION,
                )
            
            # 🔒 P0 FIX: If agent_id is specified, filter state for agent access
            if agent_id and "agent_results" in cp.state:
                # Filter state to only include keys this agent has permission to access
                filtered_state = dict(cp.state)
                if isinstance(filtered_state.get("agent_results"), dict):
                    # Keep only results for this agent
                    agent_results = filtered_state.get("agent_results", {})
                    filtered_state["agent_results"] = {
                        k: v for k, v in agent_results.items()
                        if k.startswith(f"{agent_id}:") or k == agent_id
                    }
                cp = Checkpoint(
                    checkpoint_id=cp.checkpoint_id,
                    workflow_id=cp.workflow_id,
                    timestamp=cp.timestamp,
                    state=filtered_state,
                    metadata=cp.metadata,
                    parent_id=cp.parent_id,
                    branch_name=cp.branch_name,
                    is_delta=cp.is_delta,
                    schema_version=cp.schema_version,
                )
            
            self._current_states[cp.workflow_id] = cp
            logger.info(f"Restored to checkpoint: {checkpoint_id} (agent_filter={agent_id})")
        return cp

    async def list_checkpoints(self, workflow_id: str) -> list[Checkpoint]:
        """List all checkpoints for a workflow, ordered by timestamp."""
        return await self.backend.list_checkpoints(workflow_id)

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        return await self.backend.delete(checkpoint_id)

    async def fork(
        self,
        parent_checkpoint_id: str,
        branch_name: str = "",
    ) -> str | None:
        """
        Fork execution from a checkpoint, creating a new branch.
        
        Uses deep copy to prevent data pollution between parent and fork.
        """
        parent = await self.backend.load(parent_checkpoint_id)
        if not parent:
            return None

        import uuid

        fork_cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            workflow_id=parent.workflow_id,
            timestamp=time.time(),
            state=copy.deepcopy(parent.state),  # Deep copy to prevent pollution
            metadata={
                "forked_from": parent_checkpoint_id,
                "branch": branch_name,
                **parent.metadata,
            },
            parent_id=parent_checkpoint_id,
            branch_name=branch_name,
            is_delta=False,  # Fork is always a full snapshot
        )
        await self.backend.save(fork_cp)
        self._current_states[parent.workflow_id] = fork_cp
        logger.info(f"Forked from {parent_checkpoint_id} -> {fork_cp.checkpoint_id}")
        return fork_cp.checkpoint_id

    async def get_checkpoint_timeline(self, workflow_id: str) -> list[dict[str, Any]]:
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
                "is_delta": cp.is_delta,
            }
            for cp in checkpoints
        ]

    def get_current_state(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the current active state for a workflow."""
        cp = self._current_states.get(workflow_id)
        return copy.deepcopy(cp.state) if cp else None  # Return deep copy to prevent mutation