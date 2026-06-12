# 发布到 PyPI

维护者发布 `hiveflow` 与 `hiveflow-agent` 的检查清单。

## 前置条件

1. PyPI 账号及已预留的项目名（`hiveflow`、`hiveflow-agent`）
2. GitHub secret `PYPI_API_TOKEN`（具备上传权限）
3. `main` 分支上所有 CI 任务通过

## 发布步骤

```bash
# 1. Update version in packages/core/pyproject.toml and packages/agent/pyproject.toml
# 2. Update CHANGELOG.md [Unreleased] section
git add -A && git commit -m "chore: release v0.1.0"
git tag v0.1.0
git push origin main --tags
```

参见 [Release workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/release.yml) 与 [Docs workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/docs.yml)。

Release notes 通过 [release-drafter.yml](https://github.com/hiveflow/hiveflow/blob/main/.github/release-drafter.yml) 自动生成草稿。

## 验证安装

```bash
python -m venv /tmp/hf-verify
source /tmp/hf-verify/bin/activate  # Windows: Scripts\activate
pip install hiveflow hiveflow-agent
python -c "import hiveflow; print(hiveflow.__name__)"
python examples/01_hello_hiveflow.py
```

## GitHub Pages（文档）

推送至 `main` 后，文档通过 [Docs workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/docs.yml) 自动部署。

在仓库 **Settings → Pages → Build and deployment → GitHub Actions** 中启用。

站点 URL：`https://<org>.github.io/hiveflow/`

## 启用 Discussions

仓库 **Settings → General → Features → Discussions** — 用于 Q&A 与展示（issue 仍用于 bug/功能请求）。

## Release Drafter

合并的 PR 通过 [release-drafter](https://github.com/hiveflow/hiveflow/blob/main/.github/release-drafter.yml) 更新草稿 release notes。打 tag 前将相关章节复制到 `CHANGELOG.md`。
