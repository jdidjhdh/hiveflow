#!/usr/bin/env python3
"""Run all HiveFlow examples as smoke tests."""
import subprocess
import sys
from pathlib import Path

EXAMPLES = [
    "01_hello_hiveflow.py",
    "02_multi_agent.py",
    "03_hitl_approval.py",
    "04_checkpoint.py",
    "05_streaming.py",
    "06_rag_pipeline.py",
    "07_mcp_tools.py",
    "08_cognitive_planning.py",
    "09_evaluation.py",
    "10_secure_blackboard.py",
    "11_distributed_agents.py",
    "12_custom_scheduler.py",
    "13_plugin_development.py",
    "14_guard_configuration.py",
    "15_multimodal_pipeline.py",
    "16_langgraph_export.py",
    "17_x_twitter_source_review.py",
]


def main() -> int:
    examples_dir = Path(__file__).parent
    failed = []

    for name in EXAMPLES:
        path = examples_dir / name
        print(f"\n{'=' * 60}\nRunning {name}\n{'=' * 60}")
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(examples_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            failed.append(name)

    if failed:
        print(f"\nFAILED ({len(failed)}): {', '.join(failed)}")
        return 1

    print(f"\nAll {len(EXAMPLES)} examples passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
