"""
HiveFlow - 16: LangGraph Export (PoC)

Export a TaskGraph plan to LangGraph-oriented JSON and optional Python stub.

Usage:
    python 16_langgraph_export.py
"""
import json

from hiveflow.adapters.langgraph import (
    langgraph_to_taskgraph,
    render_langgraph_python,
    taskgraph_to_langgraph,
)

PLAN = {
    "research": {"task": "search", "depends_on": []},
    "draft": {"task": "write", "depends_on": ["research"]},
    "final_answer": {"task": "summarize", "depends_on": ["draft"]},
}


def main():
    print("=== LangGraph Export PoC ===\n")

    spec = taskgraph_to_langgraph(PLAN, workflow_id="demo_export")
    print("LangGraph spec (JSON):")
    print(json.dumps(spec, indent=2))

    roundtrip = langgraph_to_taskgraph(spec)
    print("\nRound-trip TaskGraph keys:", list(roundtrip.keys()))

    code = render_langgraph_python(spec)
    print("\nGenerated Python (first 12 lines):")
    for line in code.splitlines()[:12]:
        print(line)
    print("...")


if __name__ == "__main__":
    main()
