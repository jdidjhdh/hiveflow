"""Tests for hiveflow HITL (Human-in-the-Loop) module."""
import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock

from hiveflow import HITLManager, HITLGate, HITLStatus, HITLAction


class TestHITLStatus:
    def test_all_statuses_exist(self):
        assert HITLStatus.PENDING.value == "pending"
        assert HITLStatus.APPROVED.value == "approved"
        assert HITLStatus.REJECTED.value == "rejected"
        assert HITLStatus.MODIFIED.value == "modified"
        assert HITLStatus.TIMED_OUT.value == "timed_out"
        assert HITLStatus.CANCELLED.value == "cancelled"


class TestHITLAction:
    def test_all_actions_exist(self):
        assert HITLAction.APPROVAL.value == "approval"
        assert HITLAction.REVIEW.value == "review"
        assert HITLAction.INPUT.value == "input"
        assert HITLAction.CONFIRMATION.value == "confirmation"


class TestHITLGate:
    def test_create_gate_defaults(self):
        gate = HITLGate(
            gate_id="g1",
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve this?",
            context={"data": "test"},
        )
        assert gate.status == HITLStatus.PENDING
        assert gate.human_response is None
        assert gate.human_comment == ""
        assert gate.timeout_seconds == 300.0
        assert gate.on_timeout == "fail"
        assert gate.created_at > 0
        assert gate.responded_at is None

    def test_create_gate_custom_timeout(self):
        gate = HITLGate(
            gate_id="g1",
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve this?",
            context={},
            timeout_seconds=600,
            on_timeout="approve",
        )
        assert gate.timeout_seconds == 600
        assert gate.on_timeout == "approve"


@pytest.mark.asyncio
class TestHITLManagerCreate:
    async def test_create_approval_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="review_node",
            action=HITLAction.APPROVAL,
            prompt="Review the output",
            context={"output": "test"},
        )
        assert gate.gate_id is not None
        assert gate.workflow_id == "wf_001"
        assert gate.node_id == "review_node"
        assert gate.action == HITLAction.APPROVAL
        assert gate.status == HITLStatus.PENDING

    async def test_create_review_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="edit_node",
            action=HITLAction.REVIEW,
            prompt="Review and edit",
            context={"content": "draft"},
            timeout_seconds=600,
            on_timeout="skip",
        )
        assert gate.action == HITLAction.REVIEW
        assert gate.timeout_seconds == 600
        assert gate.on_timeout == "skip"

    async def test_create_input_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="input_node",
            action=HITLAction.INPUT,
            prompt="Provide additional info",
            context={},
        )
        assert gate.action == HITLAction.INPUT

    async def test_create_confirmation_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="confirm_node",
            action=HITLAction.CONFIRMATION,
            prompt="Confirm you understand",
            context={},
        )
        assert gate.action == HITLAction.CONFIRMATION

    async def test_create_gate_triggers_callback(self):
        mgr = HITLManager()
        callback_called = asyncio.Event()
        captured_gate = None

        async def my_callback(gate):
            nonlocal captured_gate
            captured_gate = gate
            callback_called.set()

        mgr.register_callback(my_callback)
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Test",
            context={},
        )

        await asyncio.wait_for(callback_called.wait(), timeout=1.0)
        assert captured_gate is not None
        assert captured_gate.gate_id == gate.gate_id


@pytest.mark.asyncio
class TestHITLManagerRespond:
    async def test_respond_approval(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        result = await mgr.respond(gate.gate_id, approved=True, comment="Looks good!")
        assert result is not None
        assert result.status == HITLStatus.APPROVED
        assert result.human_response is True
        assert result.human_comment == "Looks good!"
        assert result.responded_at is not None

    async def test_respond_rejection(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        result = await mgr.respond(gate.gate_id, approved=False, comment="Not good")
        assert result is not None
        assert result.status == HITLStatus.REJECTED
        assert result.human_response is False

    async def test_respond_review_with_modification(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.REVIEW,
            prompt="Review?",
            context={},
        )

        result = await mgr.respond(
            gate.gate_id, modified_data="Modified content", comment="Fixed it"
        )
        assert result is not None
        assert result.status == HITLStatus.MODIFIED
        assert result.human_response == "Modified content"

    async def test_respond_review_without_modification(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.REVIEW,
            prompt="Review?",
            context={},
        )

        result = await mgr.respond(gate.gate_id, comment="Looks fine")
        assert result is not None
        assert result.status == HITLStatus.APPROVED

    async def test_respond_input(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.INPUT,
            prompt="Provide info",
            context={},
        )

        result = await mgr.respond(
            gate.gate_id, input_data={"key": "value"}, comment="Here's the data"
        )
        assert result is not None
        assert result.status == HITLStatus.APPROVED
        assert result.human_response == {"key": "value"}

    async def test_respond_confirmation(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.CONFIRMATION,
            prompt="Confirm?",
            context={},
        )

        result = await mgr.respond(gate.gate_id, approved=True, comment="Confirmed")
        assert result.status == HITLStatus.APPROVED

        gate2 = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_2",
            action=HITLAction.CONFIRMATION,
            prompt="Confirm?",
            context={},
        )
        result2 = await mgr.respond(gate2.gate_id, approved=False, comment="Not confirmed")
        assert result2.status == HITLStatus.REJECTED

    async def test_respond_nonexistent_gate(self):
        mgr = HITLManager()
        result = await mgr.respond("nonexistent", approved=True)
        assert result is None

    async def test_respond_already_resolved(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        await mgr.respond(gate.gate_id, approved=True)
        result = await mgr.respond(gate.gate_id, approved=False)
        assert result is not None
        assert result.status == HITLStatus.APPROVED  # Should not change


@pytest.mark.asyncio
class TestHITLManagerWait:
    async def test_wait_for_response_immediate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        # Respond in a separate task
        async def respond_later():
            await asyncio.sleep(0.05)
            await mgr.respond(gate.gate_id, approved=True)

        task = asyncio.create_task(respond_later())
        result = await mgr.wait_for_response(gate.gate_id, timeout=2.0)
        await task

        assert result.status == HITLStatus.APPROVED

    async def test_wait_timeout_fail(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
            timeout_seconds=0.1,
            on_timeout="fail",
        )

        result = await mgr.wait_for_response(gate.gate_id, timeout=0.2)
        assert result.status == HITLStatus.TIMED_OUT

    async def test_wait_timeout_approve(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
            timeout_seconds=0.1,
            on_timeout="approve",
        )

        result = await mgr.wait_for_response(gate.gate_id, timeout=0.2)
        assert result.status == HITLStatus.APPROVED
        assert "Auto-approved" in result.human_comment

    async def test_wait_timeout_skip(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
            timeout_seconds=0.1,
            on_timeout="skip",
        )

        result = await mgr.wait_for_response(gate.gate_id, timeout=0.2)
        assert result.status == HITLStatus.APPROVED
        assert "Auto-skipped" in result.human_comment

    async def test_wait_nonexistent_gate(self):
        mgr = HITLManager()
        with pytest.raises(ValueError, match="not found"):
            await mgr.wait_for_response("nonexistent")

    async def test_wait_already_resolved_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )
        await mgr.respond(gate.gate_id, approved=True)

        result = await mgr.wait_for_response(gate.gate_id)
        assert result.status == HITLStatus.APPROVED


@pytest.mark.asyncio
class TestHITLManagerListGet:
    async def test_list_pending_gates(self):
        mgr = HITLManager()
        gate1 = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve 1?",
            context={},
        )
        gate2 = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_2",
            action=HITLAction.APPROVAL,
            prompt="Approve 2?",
            context={},
        )

        pending = await mgr.list_pending_gates()
        assert len(pending) == 2

    async def test_list_pending_gates_by_workflow(self):
        mgr = HITLManager()
        await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )
        await mgr.create_gate(
            workflow_id="wf_002",
            node_id="node_2",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        pending_wf1 = await mgr.list_pending_gates(workflow_id="wf_001")
        assert len(pending_wf1) == 1
        assert pending_wf1[0].workflow_id == "wf_001"

    async def test_list_pending_excludes_resolved(self):
        mgr = HITLManager()
        gate1 = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )
        gate2 = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_2",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        await mgr.respond(gate1.gate_id, approved=True)

        pending = await mgr.list_pending_gates()
        assert len(pending) == 1
        assert pending[0].gate_id == gate2.gate_id

    async def test_get_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        result = await mgr.get_gate(gate.gate_id)
        assert result is not None
        assert result.gate_id == gate.gate_id

    async def test_get_nonexistent_gate(self):
        mgr = HITLManager()
        result = await mgr.get_gate("nonexistent")
        assert result is None


@pytest.mark.asyncio
class TestHITLManagerCancel:
    async def test_cancel_pending_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )

        result = await mgr.cancel_gate(gate.gate_id)
        assert result is True

        updated = await mgr.get_gate(gate.gate_id)
        assert updated.status == HITLStatus.CANCELLED

    async def test_cancel_already_resolved_gate(self):
        mgr = HITLManager()
        gate = await mgr.create_gate(
            workflow_id="wf_001",
            node_id="node_1",
            action=HITLAction.APPROVAL,
            prompt="Approve?",
            context={},
        )
        await mgr.respond(gate.gate_id, approved=True)

        result = await mgr.cancel_gate(gate.gate_id)
        assert result is False

    async def test_cancel_nonexistent_gate(self):
        mgr = HITLManager()
        result = await mgr.cancel_gate("nonexistent")
        assert result is False


@pytest.mark.asyncio
class TestHITLManagerStats:
    async def test_empty_stats(self):
        mgr = HITLManager()
        stats = mgr.get_gate_stats()
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0
        assert stats["timed_out"] == 0
        assert stats["approval_rate"] == 0

    async def test_stats_with_gates(self):
        mgr = HITLManager()
        gate1 = await mgr.create_gate("wf_001", "n1", HITLAction.APPROVAL, "Approve?", {})
        gate2 = await mgr.create_gate("wf_001", "n2", HITLAction.APPROVAL, "Approve?", {})
        gate3 = await mgr.create_gate("wf_001", "n3", HITLAction.APPROVAL, "Approve?", {})
        gate4 = await mgr.create_gate("wf_001", "n4", HITLAction.APPROVAL, "Approve?", {})

        await mgr.respond(gate1.gate_id, approved=True)
        await mgr.respond(gate2.gate_id, approved=True)
        await mgr.respond(gate3.gate_id, approved=False)

        stats = mgr.get_gate_stats()
        assert stats["total"] == 4
        assert stats["pending"] == 1
        assert stats["approved"] == 2
        assert stats["rejected"] == 1
        assert stats["approval_rate"] == pytest.approx(2/3, abs=0.01)
