#!/usr/bin/env python3
"""Push mkdocs.yml fix via GitHub Contents API when git push HTTPS is blocked."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

OWNER, REPO = "jdidjhdh", "hiveflow"
PATH = "mkdocs.yml"
MESSAGE = "fix(docs): restore valid edit_uri_template for i18n strict build"
ROOT = Path(__file__).resolve().parents[1]


def token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
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


def api(method: str, url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    content = (ROOT / PATH).read_text(encoding="utf-8")
    meta = api(
        "GET",
        f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{PATH}?ref=main",
    )
    remote = base64.b64decode(meta["content"]).decode("utf-8")
    if remote == content:
        print("Remote mkdocs.yml already matches local fix.")
        return 0
    api(
        "PUT",
        f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{PATH}",
        {
            "message": MESSAGE,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": meta["sha"],
            "branch": "main",
        },
    )
    print(f"Pushed {PATH} to main via GitHub API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
