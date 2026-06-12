# Publishing to PyPI

Maintainer checklist for releasing `hiveflow` and `hiveflow-agent`.

## Prerequisites

1. PyPI account and project names reserved (`hiveflow`, `hiveflow-agent`)
2. GitHub secret `PYPI_API_TOKEN` with upload scope
3. All CI jobs green on `main`

## Release steps

```bash
# 1. Update version in packages/core/pyproject.toml and packages/agent/pyproject.toml
# 2. Update CHANGELOG.md [Unreleased] section
git add -A && git commit -m "chore: release v0.1.0"
git tag v0.1.0
git push origin main --tags
```

See [Release workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/release.yml) and [Docs workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/docs.yml).

Release notes are drafted via [release-drafter.yml](https://github.com/hiveflow/hiveflow/blob/main/.github/release-drafter.yml).

## Verify install

```bash
python -m venv /tmp/hf-verify
source /tmp/hf-verify/bin/activate  # Windows: Scripts\activate
pip install hiveflow hiveflow-agent
python -c "import hiveflow; print(hiveflow.__name__)"
python examples/01_hello_hiveflow.py
```

## GitHub Pages (docs)

Docs deploy automatically on push to `main` via the [Docs workflow](https://github.com/hiveflow/hiveflow/blob/main/.github/workflows/docs.yml).

Enable in repo **Settings → Pages → Build and deployment → GitHub Actions**.

Site URL: `https://<org>.github.io/hiveflow/`

## Enable Discussions

Repo **Settings → General → Features → Discussions** — use for Q&A and show-and-tell (issues stay for bugs/features).

## Release Drafter

Merged PRs update the draft release notes via [release-drafter](https://github.com/hiveflow/hiveflow/blob/main/.github/release-drafter.yml). Copy relevant sections into `CHANGELOG.md` before tagging.
