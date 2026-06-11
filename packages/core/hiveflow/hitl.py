"""HiveFlow - Human-in-the-Loop (HITL)

Provides human intervention points in automated workflows.
Supports:
- Approval gates (require human approval before proceeding)
- Review nodes (human reviews and modifies agent output)
- Interactive input (human provides data during execution)
- Timeout handling (auto-proceed or fail on timeout)
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HITLStatus(str, Enum):
    """Status of a human-in-the-loop gate."""

    PENDING = "pending"  # Waiting for human response
    APPROVED = "approved"  # Human approved
    REJECTED = "rejected"  # Human rejected
    MODIFIED = "modified"  # Human modified the content
    TIMED_OUT = "timed_out"  # Timeout reached
    CANCELLED = "cancelled"  # Human cancelled


class HITLAction(str, Enum):
    """Action type for HITL gate."""

    APPROVAL = "approval"  # Simple yes/no approval
    REVIEW = "review"  # Review and modify
    INPUT = "input"  # Request human input
    CONFIRMATION = "confirmation"  # Confirm understanding


@dataclass
class HITLGate:
    """A point in the workflow where human intervention is required."""

    gate_id: str
    workflow_id: str
    node_id: str
    action: HITLAction
    prompt: str  # What to ask the human
    context: dict[str, Any]  # Context data to show the human
    status: HITLStatus = HITLStatus.PENDING
    human_response: Any | None = None
    human_comment: str = ""
    created_at: float = field(default_factory=time.time)
    responded_at: float | None = None
    timeout_seconds: float = 300.0  # 5 minutes default
    on_timeout: str = "fail"  # "fail", "approve", "skip"


class HITLManager:
    """
    Manages human-in-the-loop gates in workflows.

    Usage:
        mgr = HITLManager()

        # Create an approval gate
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="review_node",
            action=HITLAction.APPROVAL,
            prompt="Review the generated report before publishing",
            context={"report": report_text},
            timeout_seconds=600,
            on_timeout="approve",
        )

        # Check if gate is still pending
        if gate.status == HITLStatus.PENDING:
            # Wait for human response
            response = await mgr.wait_for_response(gate.gate_id)

        # Human responds (called from UI/API)
        await mgr.respond(gate.gate_id, approved=True, comment="Looks good!")
    """

    def __init__(self):
        self._gates: dict[str, HITLGate] = {}
        self._waiters: dict[str, asyncio.Event] = {}
        self._callbacks: list[Callable[[HITLGate], Awaitable[None]]] = []

    async def create_gate(
        self,
        workflow_id: str,
        node_id: str,
        action: HITLAction,
        prompt: str,
        context: dict[str, Any] | None = None,
        timeout_seconds: float = 300.0,
        on_timeout: str = "fail",
    ) -> HITLGate:
        """Create a new HITL gate."""
        import uuid

        gate = HITLGate(
            gate_id=str(uuid.uuid4())[:12],
            workflow_id=workflow_id,
            node_id=node_id,
            action=action,
            prompt=prompt,
            context=context or {},
            timeout_seconds=timeout_seconds,
            on_timeout=on_timeout,
        )
        self._gates[gate.gate_id] = gate
        self._waiters[gate.gate_id] = asyncio.Event()
        logger.info(f"HITL gate created: {gate.gate_id} for node {node_id}")

        # Notify callbacks
        for cb in self._callbacks:
            try:
                await cb(gate)
            except Exception as e:
                logger.error(f"HITL callback error: {e}")

        return gate

    async def respond(
        self,
        gate_id: str,
        approved: bool = True,
        modified_data: Any | None = None,
        comment: str = "",
        input_data: Any | None = None,
    ) -> HITLGate | None:
        """Record a human response to a gate."""
        gate = self._gates.get(gate_id)
        if not gate:
            logger.error(f"HITL gate not found: {gate_id}")
            return None

        if gate.status != HITLStatus.PENDING:
            logger.warning(f"HITL gate already resolved: {gate_id} ({gate.status})")
            return gate

        gate.responded_at = time.time()
        gate.human_comment = comment

        if gate.action == HITLAction.APPROVAL:
            gate.status = HITLStatus.APPROVED if approved else HITLStatus.REJECTED
            gate.human_response = approved
        elif gate.action == HITLAction.REVIEW:
            if not approved:
                gate.status = HITLStatus.REJECTED
                gate.human_response = None
            else:
                gate.status = HITLStatus.MODIFIED if modified_data is not None else HITLStatus.APPROVED
                gate.human_response = modified_data
        elif gate.action == HITLAction.INPUT:
            gate.status = HITLStatus.APPROVED
            gate.human_response = input_data
        elif gate.action == HITLAction.CONFIRMATION:
            gate.status = HITLStatus.APPROVED if approved else HITLStatus.REJECTED
            gate.human_response = approved

        # Signal waiters
        if gate_id in self._waiters:
            self._waiters[gate_id].set()

        logger.info(f"HITL gate resolved: {gate_id} -> {gate.status}")
        return gate

    async def wait_for_response(
        self,
        gate_id: str,
        timeout: float | None = None,
    ) -> HITLGate:
        """Wait for a human response to a gate. Returns the gate with updated status."""
        gate = self._gates.get(gate_id)
        if not gate:
            raise ValueError(f"HITL gate not found: {gate_id}")

        if gate.status != HITLStatus.PENDING:
            return gate

        wait_timeout = timeout if timeout is not None else gate.timeout_seconds
        waiter = self._waiters.get(gate_id)

        if waiter:
            try:
                await asyncio.wait_for(waiter.wait(), timeout=wait_timeout)
            except asyncio.TimeoutError:
                # Handle timeout
                if gate.on_timeout == "approve":
                    gate.status = HITLStatus.APPROVED
                    gate.human_comment = "Auto-approved (timeout)"
                elif gate.on_timeout == "skip":
                    gate.status = HITLStatus.APPROVED
                    gate.human_comment = "Auto-skipped (timeout)"
                else:
                    gate.status = HITLStatus.TIMED_OUT
                    gate.human_comment = "Timed out"
                gate.responded_at = time.time()
                waiter.set()

        return gate

    async def list_pending_gates(self, workflow_id: str | None = None) -> list[HITLGate]:
        """List all pending HITL gates."""
        gates = [g for g in self._gates.values() if g.status == HITLStatus.PENDING]
        if workflow_id:
            gates = [g for g in gates if g.workflow_id == workflow_id]
        return sorted(gates, key=lambda g: g.created_at)

    async def get_gate(self, gate_id: str) -> HITLGate | None:
        """Get a specific gate."""
        return self._gates.get(gate_id)

    async def cancel_gate(self, gate_id: str) -> bool:
        """Cancel a pending gate."""
        gate = self._gates.get(gate_id)
        if gate and gate.status == HITLStatus.PENDING:
            gate.status = HITLStatus.CANCELLED
            gate.responded_at = time.time()
            if gate_id in self._waiters:
                self._waiters[gate_id].set()
            return True
        return False

    def register_callback(self, callback: Callable[[HITLGate], Awaitable[None]]):
        """Register a callback for when gates are created."""
        self._callbacks.append(callback)

    def get_gate_stats(self) -> dict[str, Any]:
        """Get statistics about HITL gates."""
        total = len(self._gates)
        pending = sum(1 for g in self._gates.values() if g.status == HITLStatus.PENDING)
        approved = sum(1 for g in self._gates.values() if g.status == HITLStatus.APPROVED)
        rejected = sum(1 for g in self._gates.values() if g.status == HITLStatus.REJECTED)
        timed_out = sum(1 for g in self._gates.values() if g.status == HITLStatus.TIMED_OUT)
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "timed_out": timed_out,
            "approval_rate": approved / (approved + rejected) if (approved + rejected) > 0 else 0,
        }
