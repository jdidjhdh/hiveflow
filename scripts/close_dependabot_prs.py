#!/usr/bin/env python3
"""Close open Dependabot PRs to reduce CI noise."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

OWNER = "jdidjhdh"
REPO = "hiveflow"
API = "https://api.github.com"
CLOSE_COMMENT = (
    "Closing to reduce CI noise during the v0.1.x Alpha stabilization period. "
    "Dependabot will reopen or create fresh PRs on the next monthly schedule. "
    "Revisit upgrades in a dedicated maintenance pass."
)


def token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    sys.exit("Set GITHUB_TOKEN")


def api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    req = urllib.request.Request(
        f"{API}{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def list_dependabot_prs() -> list[dict]:
    q = urllib.parse.quote(f"repo:{OWNER}/{REPO} is:pr is:open author:app/dependabot")
    data = api("GET", f"/search/issues?q={q}&per_page=100")
    return data.get("items", []) if isinstance(data, dict) else []


def close_pr(number: int) -> None:
    api("PATCH", f"/repos/{OWNER}/{REPO}/pulls/{number}", {"state": "closed"})
    try:
        api(
            "POST",
            f"/repos/{OWNER}/{REPO}/issues/{number}/comments",
            {"body": CLOSE_COMMENT},
        )
    except urllib.error.HTTPError:
        pass


def main() -> int:
    prs = list_dependabot_prs()
    if not prs:
        print("No open Dependabot PRs.")
        return 0
    print(f"Closing {len(prs)} Dependabot PR(s)...")
    for pr in prs:
        num = pr["number"]
        title = pr["title"][:70]
        close_pr(num)
        print(f"  closed #{num}: {title}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
