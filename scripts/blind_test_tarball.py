#!/usr/bin/env python3
"""Simulate new-user install path using GitHub tarball (no git clone)."""
from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

OWNER, REPO = "jdidjhdh", "hiveflow"
TARBALL = f"https://api.github.com/repos/{OWNER}/{REPO}/tarball/main"


def token() -> str:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    return ""


def main() -> int:
    t0 = time.perf_counter()
    headers = {"Accept": "application/vnd.github+json"}
    tok = token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    req = urllib.request.Request(TARBALL, headers=headers)
    print(f"Downloading {TARBALL} ...")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dl_sec = time.perf_counter() - t0
    print(f"Download: {len(data) / 1024 / 1024:.1f} MB in {dl_sec:.1f}s")

    tmp = Path(tempfile.mkdtemp(prefix="hiveflow-blind-"))
    print(f"Extract to {tmp}")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        tf.extractall(tmp)
    roots = [p for p in tmp.iterdir() if p.is_dir()]
    root = roots[0] if roots else tmp
    extract_sec = time.perf_counter() - t0 - dl_sec

    venv = root / ".venv-blind"
    t1 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    pip = venv / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
    py = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    subprocess.run(
        [str(pip), "install", "-q", "-e", "packages/core", "-e", "packages/agent"],
        cwd=root,
        check=True,
    )
    install_sec = time.perf_counter() - t1

    t2 = time.perf_counter()
    result = subprocess.run(
        [str(py), "examples/01_hello_hiveflow.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    run_sec = time.perf_counter() - t2
    total = time.perf_counter() - t0

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print("\n--- Blind test timing ---")
    print(f"  download:  {dl_sec:.1f}s")
    print(f"  extract:   {extract_sec:.1f}s")
    print(f"  pip install: {install_sec:.1f}s")
    print(f"  hello run: {run_sec:.1f}s")
    print(f"  TOTAL:     {total:.1f}s")
    print(f"  exit code: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
