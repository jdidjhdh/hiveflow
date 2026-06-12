#!/usr/bin/env python3
"""Build and upload hiveflow-core + hiveflow-agent to PyPI (or TestPyPI).

Usage:
  set TWINE_PASSWORD=pypi-...   # Windows
  export TWINE_PASSWORD=pypi-... # Linux/macOS
  python scripts/publish_pypi.py

  python scripts/publish_pypi.py --test   # upload to https://test.pypi.org
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "packages" / "core"
AGENT = ROOT / "packages" / "agent"


def run(cmd: list[str], *, cwd: Path) -> None:
    print(f"\n→ {' '.join(cmd)}  (cwd={cwd.relative_to(ROOT)})")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish HiveFlow packages to PyPI")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Upload to TestPyPI (https://test.pypi.org) instead of production",
    )
    parser.add_argument("--skip-upload", action="store_true", help="Build only, no twine upload")
    args = parser.parse_args()

    token = os.environ.get("TWINE_PASSWORD") or os.environ.get("PYPI_API_TOKEN")
    if not args.skip_upload and not token:
        print(
            "ERROR: Set TWINE_PASSWORD or PYPI_API_TOKEN to your PyPI API token.\n"
            "Create one at: https://pypi.org/manage/account/token/\n"
            "Then:  set TWINE_PASSWORD=pypi-AgEIcHlwaS5vcmcC...  (Windows PowerShell)\n"
            "Or add PYPI_API_TOKEN to GitHub repo Secrets for CI release on tag push.",
            file=sys.stderr,
        )
        return 1

    env = os.environ.copy()
    if token:
        env.setdefault("TWINE_USERNAME", "__token__")
        env.setdefault("TWINE_PASSWORD", token)

    upload_args: list[str] = []
    if args.test:
        upload_args = ["--repository", "testpypi"]

    py = sys.executable
    run([py, "-m", "pip", "install", "--upgrade", "pip", "build", "twine"], cwd=ROOT)

    for label, pkg_dir in [("hiveflow-core", CORE), ("hiveflow-agent", AGENT)]:
        print(f"\n{'=' * 60}\nBuilding {label}\n{'=' * 60}")
        if label == "hiveflow-agent":
            run([py, "-m", "pip", "install", "-e", str(CORE)], cwd=AGENT)
        run([py, "-m", "build"], cwd=pkg_dir)
        run([py, "-m", "twine", "check", "dist/*"], cwd=pkg_dir)
        if not args.skip_upload:
            run([py, "-m", "twine", "upload", *upload_args, "dist/*"], cwd=pkg_dir)

    repo = "TestPyPI" if args.test else "PyPI"
    print(f"\nDone. Verify: pip install hiveflow-core hiveflow-agent")
    if args.test:
        print("  (from TestPyPI: pip install -i https://test.pypi.org/simple/ hiveflow-core)")
    else:
        print(f"  Packages live on {repo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
