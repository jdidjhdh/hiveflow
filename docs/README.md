# Documentation / 文档

HiveFlow documentation is published in **English** and **简体中文**.

| Language | Path | Site |
|----------|------|------|
| English | [`docs/en/`](en/) | [hiveflow.github.io/hiveflow/en/](https://hiveflow.github.io/hiveflow/en/) |
| 简体中文 | [`docs/zh/`](zh/) | [hiveflow.github.io/hiveflow/zh/](https://hiveflow.github.io/hiveflow/zh/) |

Shared assets (logo, images): [`docs/assets/`](https://github.com/hiveflow/hiveflow/tree/main/docs/assets)

## Build locally

```bash
pip install mkdocs-material "mkdocstrings[python]" mkdocs-static-i18n
pip install -e packages/core
python -m mkdocs build --strict
python -m mkdocs serve   # language switcher in the Material theme
```

## Adding or updating docs

1. Edit the **English** source under `docs/en/`.
2. Apply the same change to the matching file under `docs/zh/` (keep code/API in English).
3. Run `python -m mkdocs build --strict` before opening a PR.

Navigation is defined per locale in [`mkdocs.yml`](https://github.com/hiveflow/hiveflow/blob/main/mkdocs.yml) under the `i18n` plugin.

See also: [`docs/en/i18n.md`](en/i18n.md) · [`docs/zh/i18n.md`](zh/i18n.md)
