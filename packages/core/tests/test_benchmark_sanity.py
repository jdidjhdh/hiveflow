"""CI sanity checks for benchmark script."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "run_orchestration_latency.py"


def test_benchmark_quick_completes():
    out = ROOT / "benchmarks" / "test-last-run.json"
    proc = subprocess.run(
        [sys.executable, str(BENCH), "--quick", "--json", str(out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["iterations"] == 10
    by_name = {r["name"]: r for r in data["results"]}
    linear = by_name["hiveflow_dag_linear_3node"]
    # Sanity: linear 3-node DAG p50 under 50ms on CI runners
    assert linear["p50_ms"] < 50.0, linear
