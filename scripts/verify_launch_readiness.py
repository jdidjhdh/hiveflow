#!/usr/bin/env python3
"""Phase 0 launch readiness checks (local / CI). Run from repo root."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks: list[tuple[str, list[str], Path | None]] = [
        ("Core pytest", [sys.executable, "-m", "pytest", "-q", "--tb=no"], ROOT / "packages/core"),
        (
            "Agent pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "--ignore=tests/test_real_llm.py",
                "--ignore=tests/test_llm_connection.py",
                "-q",
                "--tb=no",
                "--cov",
                "--cov-fail-under=60",
            ],
            ROOT / "packages/agent",
        ),
        (
            "Studio backend pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=no",
                "--cov=app",
                "--cov-fail-under=60",
            ],
            ROOT / "packages/studio/backend",
        ),
        ("Examples smoke", [sys.executable, "examples/run_smoke_tests.py"], ROOT),
        ("MkDocs strict", [sys.executable, "-m", "mkdocs", "build", "--strict"], ROOT),
        (
            "Core twine check",
            [sys.executable, "-m", "twine", "check", "dist/*"],
            ROOT / "packages/core",
        ),
        (
            "Agent twine check",
            [sys.executable, "-m", "twine", "check", "dist/*"],
            ROOT / "packages/agent",
        ),
    ]

    env = {"HIVEFLOW_AGENT_ECHO_LLM": "true"}
    failed: list[str] = []
    for label, cmd, cwd in checks:
        print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
        result = subprocess.run(cmd, cwd=cwd or ROOT, env={**os.environ, **env})
        ok = result.returncode == 0
        print(f"→ {'PASS' if ok else 'FAIL'}: {label}")
        if not ok:
            failed.append(label)

    print("\n" + "=" * 60)
    if failed:
        print(f"LAUNCH READINESS: NOT READY ({len(failed)} failed)")
        for name in failed:
            print(f"  - {name}")
        return 1

    print("LAUNCH READINESS: LOCAL CHECKS PASSED")
    print("Manual steps still required — see OSS_LAUNCH.md Phase 0 Day 1–3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
