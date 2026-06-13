#!/usr/bin/env python3
"""Post v0.1.0 announcement to GitHub Discussions."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

OWNER, REPO = "jdidjhdh", "hiveflow"
TITLE = "HiveFlow v0.1.0 (Alpha) 已发布 — 欢迎试用与反馈"

BODY = """# HiveFlow v0.1.0 (Alpha) 已发布

首个公开版本，欢迎试用和反馈。

## 这是什么

多 Agent 协调与 HITL 层，自带可自托管的 **Studio** UI，支持 MCP、Checkpoint、审批流等。

## 快速开始

**文档：** https://jdidjhdh.github.io/hiveflow/

**Docker（推荐体验 Studio）：**
```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
docker compose up --build
```
- Studio: http://localhost:3000
- API: http://localhost:8000

**pip（Core + Agent）：**
```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
pip install -e packages/core -e packages/agent
python examples/01_hello_hiveflow.py
```

**Release 安装包：** https://github.com/jdidjhdh/hiveflow/releases/tag/v0.1.0

## 反馈渠道

- **问题 / Bug** → [Issues](https://github.com/jdidjhdh/hiveflow/issues)
- **用法 / 想法** → 本帖回复
- **改文档** → 文档页右上角 **Edit this page** 提 PR

## 状态说明

这是 **0.1.x Alpha**，API 可能调整，详见 [Versioning](https://jdidjhdh.github.io/hiveflow/en/versioning/)。

感谢试用 🙏
"""


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


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
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
        return json.loads(resp.read().decode())


def main() -> int:
    t = token()
    repo = api("GET", f"/repos/{OWNER}/{REPO}")
    repo_node_id = repo["node_id"]

    cat_query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        discussionCategories(first: 20) {
          nodes { id name slug }
        }
      }
    }
    """
    gql_req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(
            {
                "query": cat_query,
                "variables": {"owner": OWNER, "name": REPO},
            }
        ).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {t}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(gql_req, timeout=60) as resp:
        cat_data = json.loads(resp.read().decode())

    if "errors" in cat_data:
        print("GraphQL errors:", cat_data["errors"], file=sys.stderr)
        return 1

    nodes = cat_data["data"]["repository"]["discussionCategories"]["nodes"]
    if not nodes:
        print("No discussion categories; enable Discussions on the repo.", file=sys.stderr)
        return 1

    general = next((c for c in nodes if c.get("slug") == "announcements"), nodes[0])
    cat_id = general["id"]

    query = """
    mutation($repoId: ID!, $catId: ID!, $title: String!, $body: String!) {
      createDiscussion(input: {
        repositoryId: $repoId
        categoryId: $catId
        title: $title
        body: $body
      }) {
        discussion { url number }
      }
    }
    """
    gql_req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(
            {
                "query": query,
                "variables": {
                    "repoId": repo_node_id,
                    "catId": cat_id,
                    "title": TITLE,
                    "body": BODY,
                },
            }
        ).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {t}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(gql_req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        raise

    if "errors" in data:
        # Fallback: search existing announcement
        err = data["errors"]
        print("GraphQL errors:", err, file=sys.stderr)
        return 1

    disc = data["data"]["createDiscussion"]["discussion"]
    print(f"Discussion #{disc['number']}: {disc['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
