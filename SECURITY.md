# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in HiveFlow,
please report it responsibly.

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report via one of:

1. **GitHub Security Advisories** (preferred): [Report a vulnerability](https://github.com/jdidjhdh/hiveflow/security/advisories/new)
2. **Email:** security@hiveflow.dev (if configured for your deployment)

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix or mitigation plan | Within 14 days for critical issues |

## Security Features

HiveFlow includes built-in security primitives:

- **InputGuard** — prompt injection, XSS, and SQLi pattern detection
- **OutputValidator** — output sanitization and schema validation
- **SecureBlackboard** — audit logging and access control
- **EncryptedBlackboard** — AES encryption at rest (requires `hiveflow[security]`)

See [Guard Configuration](examples/14_guard_configuration.py) and
[Secure Blackboard](examples/10_secure_blackboard.py) examples.

## HiveFlow Studio (self-hosted UI)

Studio v0.1.x is a **technical preview**. It does **not** include built-in authentication or authorization.

| Risk | Mitigation |
|------|------------|
| Unauthenticated API / WebSocket | Deploy on a private network, VPN, or behind an identity-aware reverse proxy (OAuth2, mTLS, IP allowlist) |
| Default database passwords in compose examples | Change `POSTGRES_PASSWORD` and secrets before any non-local deployment |
| Mock / demo pages | Some UI pages use in-browser demo data — see [CAPABILITIES.md](packages/studio/CAPABILITIES.md) |
| Electron desktop scripts | **Experimental** — not part of v0.1 release artifacts; do not use for production |

### Recommended deployment

1. Use tagged images from GHCR via [`docker-compose.release.yml`](docker-compose.release.yml) (not dev bind mounts).
2. Terminate TLS at your ingress; do not expose Studio API port `8000` directly to the public internet.
3. Store LLM API keys in environment variables or a secrets manager — never commit them.
4. Enable HiveFlow runtime guards (`InputGuard`, `SecureBlackboard`) for agent workloads handling untrusted input.

Details: [Studio README](packages/studio/README.md) · [Studio security notes (zh)](packages/studio/README.zh.md#部署安全)

## Best Practices for Deployments

- Never commit API keys or encryption keys to version control
- Use `.env` files locally and secrets managers in production
- Enable encrypted blackboard for sensitive workloads
- Keep dependencies up to date (`dependabot` is enabled in this repository)
