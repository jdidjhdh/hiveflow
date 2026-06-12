#!/usr/bin/env python3
"""Agent maintainer debug session — TaskGraph normalization paths."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

DEBUG_DIR = Path(__file__).resolve().parent
ROOT = DEBUG_DIR.parents[1]
sys.path.insert(0, str(DEBUG_DIR))
sys.path.insert(0, str(ROOT / "packages" / "agent"))

from common import log, reset_log


async def main() -> None:
    from orchestrator.cognitive import CognitiveOrchestrator

    reset_log()
    log("agent_session:main", "session start", {}, "H0")

    nested = {
        "nodes": {
            "calc": {"task": "calculate", "depends_on": []},
            "answer": {"task": "summarize", "depends_on": ["calc"]},
        }
    }
    normalized = CognitiveOrchestrator._normalize_task_graph(nested)
    log(
        "agent_session:normalize",
        "nested nodes graph",
        {"inputKeys": list(nested.keys()), "outputKeys": list(normalized.keys())},
        "H2",
    )

    sink_only = {
        "calc": {"task": "calculate", "depends_on": []},
        "summary": {"task": "summarize", "depends_on": ["calc"]},
    }
    normalized2 = CognitiveOrchestrator._normalize_task_graph(sink_only)
    log(
        "agent_session:normalize",
        "sink rename",
        {"outputKeys": list(normalized2.keys()), "finalTask": normalized2["final_answer"]["task"]},
        "H2",
    )

    log("agent_session:main", "session complete", {}, "H0")


if __name__ == "__main__":
    asyncio.run(main())
