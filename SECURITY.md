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

1. **GitHub Security Advisories** (preferred): [Report a vulnerability](https://github.com/hiveflow/hiveflow/security/advisories/new)
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

## Best Practices for Deployments

- Never commit API keys or encryption keys to version control
- Use `.env` files locally and secrets managers in production
- Enable encrypted blackboard for sensitive workloads
- Keep dependencies up to date (`dependabot` is enabled in this repository)
