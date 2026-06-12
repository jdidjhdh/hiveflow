#!/usr/bin/env python3
"""Pre-push hygiene checks before first public GitHub publish. Run from repo root."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths that must never be committed (patterns relative to repo root)
FORBIDDEN_TRACKED = [
    ".env",
    ".env.local",
    "packages/studio/frontend/playwright-report/",
    "packages/studio/frontend/coverage/",
    "packages/studio/backend/data/*.db",
    "packages/studio/backend/data/*.sqlite3",
]

SECRET_LINE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"]?[a-zA-Z0-9_\-]{20,}"
)


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    return subprocess.run(cmd, cwd=cwd or ROOT).returncode


def git_tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def check_forbidden_tracked() -> list[str]:
    tracked = git_tracked_files()
    bad: list[str] = []
    for pattern in FORBIDDEN_TRACKED:
        if pattern.endswith("/"):
            prefix = pattern.rstrip("/")
            bad.extend(p for p in tracked if p.startswith(prefix + "/") or p == prefix)
        elif "*" in pattern:
            import fnmatch

            bad.extend(p for p in tracked if fnmatch.fnmatch(p, pattern))
        else:
            if pattern in tracked:
                bad.append(pattern)
    return bad


def check_secret_like_lines() -> list[str]:
    """Light scan of tracked text files for accidental credential literals."""
    hits: list[str] = []
    skip_suffix = {".png", ".svg", ".jpg", ".ico", ".woff", ".woff2", ".lock", ".json"}
    for rel in git_tracked_files():
        path = ROOT / rel
        if not path.is_file() or path.suffix.lower() in skip_suffix:
            continue
        if "kubernetes" in rel or "docker-compose" in rel or "SECURITY" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "your-" in line.lower() or "example" in line.lower() or "placeholder" in line.lower():
                continue
            if "get_decrypted" in line or "credential_id" in line or "os.environ.get" in line:
                continue
            if SECRET_LINE.search(line):
                hits.append(f"{rel}:{i}")
    return hits[:20]


def ensure_package_dists() -> None:
    for pkg in ("packages/core", "packages/agent"):
        dist = ROOT / pkg / "dist"
        if dist.exists() and list(dist.glob("*.whl")):
            continue
        print(f"\n-> Building {pkg} dist for twine check...")
        run([sys.executable, "-m", "pip", "install", "build", "-q"])
        if run([sys.executable, "-m", "build"], cwd=ROOT / pkg) != 0:
            raise SystemExit(f"Failed to build {pkg}")


def main() -> int:
    print("=" * 60)
    print("PRE-RELEASE CHECK")
    print("=" * 60)

    failed: list[str] = []

    forbidden = check_forbidden_tracked()
    if forbidden:
        failed.append(f"Forbidden tracked paths ({len(forbidden)})")
        for p in forbidden[:15]:
            print(f"  FAIL tracked: {p}")
        if len(forbidden) > 15:
            print(f"  ... and {len(forbidden) - 15} more")

    secrets = check_secret_like_lines()
    if secrets:
        failed.append(f"Possible secret literals ({len(secrets)})")
        for h in secrets:
            print(f"  WARN review: {h}")

    untracked_ignored = [
        "OPTIMIZATION_SUMMARY.md",
        "PROGRESS_TRACKER.md",
        "TEST_COVERAGE_ROADMAP.md",
    ]
    for name in untracked_ignored:
        if (ROOT / name).exists():
            print(f"  OK planning note gitignored: {name}")

    try:
        ensure_package_dists()
    except SystemExit as e:
        failed.append(str(e))

    print("\n" + "=" * 60)
    print("Running verify_launch_readiness.py …")
    print("=" * 60)
    if run([sys.executable, "scripts/verify_launch_readiness.py"]) != 0:
        failed.append("verify_launch_readiness")

    print("\n" + "=" * 60)
    if failed:
        print(f"PRE-RELEASE: NOT READY ({len(failed)} issue(s))")
        for item in failed:
            print(f"  - {item}")
        print("\nFix items above, then: git add -A && git status")
        return 1

    print("PRE-RELEASE: READY FOR GITHUB PUSH")
    print("\nNext (maintainer):")
    print("  1. git add -A && git status   # review staged files")
    print("  2. git commit -m 'chore: prepare v0.1.0 public release'")
    print("  3. Create public repo → git push -u origin main")
    print("  4. OSS_LAUNCH.md Phase 0 — Pages, Discussions, tag v0.1.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
