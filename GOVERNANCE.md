# Governance

How HiveFlow is maintained and how decisions are made.

## Project leadership

HiveFlow is maintained by the core team listed in [README.md](README.md#maintainers). The team is responsible for:

- Release tagging and PyPI publishes
- Security advisory triage ([SECURITY.md](SECURITY.md))
- Roadmap updates ([ROADMAP.md](ROADMAP.md))

## Decision process

| Change type | Process |
|-------------|---------|
| Bug fix, docs, tests | Any maintainer or contributor PR; 1 approval |
| New feature (backward compatible) | RFC optional; PR + tests + docs; 1 maintainer approval |
| Breaking API change | Issue/RFC + migration note in CHANGELOG; 2 maintainer approvals |
| Security fix | Private advisory → patch release → CVE if applicable |

## Contributing

All contributors must follow [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Release management

- Versions follow [docs/versioning.md](docs/versioning.md).
- Releases are tagged `v*` on `main`; GitHub Actions publishes to PyPI ([`.github/workflows/release.yml`](.github/workflows/release.yml)).
- Release notes are drafted via Release Drafter and summarized in [CHANGELOG.md](CHANGELOG.md).

## Intellectual property

- Code: [MIT License](LICENSE)
- Contributors retain copyright; contributions are licensed under MIT by submission

## Community channels

- **GitHub Issues** — bugs and feature requests
- **GitHub Discussions** — Q&A and show-and-tell (enable in repo settings)
- **Discord** — real-time chat (link in README when available)

## Becoming a maintainer

Regular, high-quality contributions over several months may lead to triage or maintainer access. Nomination by an existing maintainer; no formal CLA required (MIT).
