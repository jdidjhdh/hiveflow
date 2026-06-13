#!/usr/bin/env python3
"""One-click GitHub repo setup for HiveFlow (Discussions, metadata, security, release)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

OWNER = "jdidjhdh"
REPO = "hiveflow"
API = "https://api.github.com"


def token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    print("Set GITHUB_TOKEN (PAT with repo admin scope).", file=sys.stderr)
    sys.exit(1)


def request(method: str, path: str, body: dict | None = None) -> dict | list | None:
    url = f"{API}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        print(f"HTTP {e.code} {method} {path}\n{detail}", file=sys.stderr)
        raise


def patch_repo(settings: dict) -> dict:
    return request("PATCH", f"/repos/{OWNER}/{REPO}", settings)


def enable_private_vulnerability_reporting() -> None:
    try:
        request(
            "PUT",
            f"/repos/{OWNER}/{REPO}/private-vulnerability-reporting",
            {"enabled": True},
        )
        print("  private vulnerability reporting: enabled")
    except urllib.error.HTTPError:
        patch_repo(
            {
                "security_and_analysis": {
                    "private_vulnerability_reporting": {"status": "enabled"}
                }
            }
        )
        print("  private vulnerability reporting: enabled (via security_and_analysis)")


def ensure_release_editable(tag: str = "v0.1.0") -> None:
    rel = request("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{tag}")
    if not isinstance(rel, dict):
        return
    rid = rel["id"]
    # Keep Alpha pre-release; ensure body matches repo file (idempotent refresh).
    notes_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "en", "release-notes", f"{tag}.md"
    )
    body = rel.get("body") or ""
    if os.path.isfile(notes_path):
        with open(notes_path, encoding="utf-8") as f:
            body = f.read()
    request(
        "PATCH",
        f"/repos/{OWNER}/{REPO}/releases/{rid}",
        {
            "name": tag,
            "body": body,
            "draft": False,
            "prerelease": True,
            "make_latest": False,
        },
    )
    print(f"  release {tag}: body synced (pre-release, editable via API/UI)")


def main() -> int:
    print("HiveFlow GitHub one-click setup\n")

    repo = patch_repo(
        {
            "description": "Multi-agent coordination & HITL layer — self-hosted Studio, MCP tools, LangGraph sidecar. Alpha 0.1.x",
            "homepage": "https://jdidjhdh.github.io/hiveflow/",
            "has_discussions": True,
            "has_issues": True,
            "has_wiki": True,
            "has_pull_requests": True,
            "pull_request_creation_policy": "all",
            "allow_update_branch": True,
            "delete_branch_on_merge": True,
            "allow_merge_commit": True,
            "allow_squash_merge": True,
            "allow_rebase_merge": True,
        }
    )
    print(f"  discussions: {repo.get('has_discussions')}")
    print(f"  homepage: {repo.get('homepage')}")
    print(f"  pull_request_creation_policy: {repo.get('pull_request_creation_policy')}")

    topics = [
        "multi-agent",
        "hitl",
        "langgraph",
        "mcp",
        "python",
        "orchestration",
        "fastapi",
        "react",
    ]
    request("PUT", f"/repos/{OWNER}/{REPO}/topics", {"names": topics})
    print(f"  topics: {', '.join(topics)}")

    enable_private_vulnerability_reporting()
    ensure_release_editable("v0.1.0")

    print("\nDone. Verify:")
    print(f"  https://github.com/{OWNER}/{REPO}/discussions")
    print(f"  https://github.com/{OWNER}/{REPO}/releases/tag/v0.1.0")
    print(
        "\nOptional (web UI): Settings → General → Features → "
        "uncheck 'Restrict wiki editing to collaborators only' so any signed-in user can edit the Wiki:"
    )
    print(f"  https://github.com/{OWNER}/{REPO}/settings#features")
    return 0


if __name__ == "__main__":
    sys.exit(main())
