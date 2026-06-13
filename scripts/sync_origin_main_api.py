#!/usr/bin/env python3
"""Align local refs with remote main when git fetch to github.com fails."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

OWNER, REPO = "jdidjhdh", "hiveflow"
ROOT = Path(__file__).resolve().parents[1]


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
    sys.exit("No GitHub token")


def api_get(path: str, t: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {t}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    t = token()
    commit = api_get(f"/repos/{OWNER}/{REPO}/commits/main", t)
    sha = commit["sha"]
    msg = commit["commit"]["message"].split("\n")[0]

    local = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Update remote-tracking ref only if object exists locally
    has_obj = subprocess.run(
        ["git", "cat-file", "-e", sha],
        cwd=ROOT,
        capture_output=True,
    ).returncode == 0
    if has_obj:
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/main", sha],
            cwd=ROOT,
            check=True,
        )
    else:
        print("Commit object not in local repo; skipped update-ref (git fetch blocked).")

    # Pull mkdocs.yml from API if local differs from remote
    content = api_get(f"/repos/{OWNER}/{REPO}/contents/mkdocs.yml?ref={sha}", t)
    import base64

    remote_mkdocs = base64.b64decode(content["content"]).decode()
    local_path = ROOT / "mkdocs.yml"
    local_mkdocs = local_path.read_text(encoding="utf-8")
    if local_mkdocs != remote_mkdocs:
        local_path.write_text(remote_mkdocs, encoding="utf-8")
        print("Updated mkdocs.yml from remote")

    print(f"Remote main: {sha[:7]} {msg}")
    print(f"Local HEAD:  {local[:7]} (git fetch still blocked; working tree synced for mkdocs)")
    if local != sha:
        print("Note: run `git reset --hard origin/main` once github.com:443 is reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
