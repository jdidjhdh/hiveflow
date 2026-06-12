"""Simple interval-based trigger scheduler for Studio."""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    from app.api.triggers_api import _triggers
    from app.core.workflow_runner import execute_stored_workflow

    while True:
        try:
            now = time.time()
            for trigger in _triggers.values():
                if not trigger.get("enabled"):
                    continue
                if trigger.get("type") != "schedule":
                    continue
                workflow_id = trigger.get("workflow_id")
                if not workflow_id:
                    continue
                interval = float((trigger.get("config") or {}).get("interval_seconds") or 0)
                if interval <= 0:
                    continue
                last_run = float(trigger.get("last_run_at") or 0)
                if now - last_run < interval:
                    continue
                try:
                    await execute_stored_workflow(workflow_id, wf_id=f"trg_{trigger['id']}_{int(now)}")
                    trigger["last_run_at"] = now
                    trigger["run_count"] = int(trigger.get("run_count") or 0) + 1
                    logger.info("Trigger %s fired workflow %s", trigger["id"], workflow_id)
                except Exception:
                    logger.exception("Trigger %s failed", trigger.get("id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Trigger scheduler loop error")
        await asyncio.sleep(5)


def start_trigger_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="studio-trigger-scheduler")


async def stop_trigger_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    _scheduler_task = None
