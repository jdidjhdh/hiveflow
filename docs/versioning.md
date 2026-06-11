# Versioning Policy

HiveFlow follows [Semantic Versioning 2.0.0](https://semver.org/) while in **Alpha** (0.y.z).

## Current status: 0.1.x Alpha

- **0.1.x** — Initial public releases; API may change between minors with migration notes in [CHANGELOG](https://github.com/hiveflow/hiveflow/blob/main/CHANGELOG.md).
- **0.2.x** — Developer experience focus: unified high-level API, OpenTelemetry docs, coverage targets.
- **1.0.0** — API freeze after Core + Studio stable for 6 months ([Roadmap](roadmap.md)).

## What counts as breaking

| Change | Bump |
|--------|------|
| Remove/rename public `hiveflow` exports | **Minor** during 0.x (documented); **Major** at 1.0+ |
| Studio REST path or payload change | Minor + migration note |
| Default env behavior change | Minor + CHANGELOG |
| Internal module refactor | Patch |

## Packages

| PyPI name | Scope |
|-----------|-------|
| `hiveflow` | Core engine |
| `hiveflow-agent` | Agent runtime (depends on `hiveflow>=0.1`) |

Version numbers are kept in sync for releases (`v0.1.0` tag publishes both).

## Upgrade checklist

1. Read [CHANGELOG](https://github.com/hiveflow/hiveflow/blob/main/CHANGELOG.md).
2. Run your test suite and `examples/run_smoke_tests.py`.
3. For Studio: check [Studio Agent Operations](studio-agent-ops.md) env vars.
