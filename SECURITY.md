# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Email us at [security@hiveflow.dev](mailto:security@hiveflow.dev)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to resolve the issue.

## Security Best Practices

### API Keys

- Never commit API keys to the repository
- Use environment variables or `.env` files
- Rotate API keys regularly
- Use key management services in production

### Blackboard Security

- Enable encryption for sensitive data:
  ```bash
  pip install "hiveflow[security]"
  ```
- Configure proper read/write permissions per agent
- Regularly audit blackboard access logs

### Input Validation

- Always enable input/output guards in production:
  ```python
  from hiveflow import InputGuard, OutputValidator

  guard = InputGuard(max_length=10000)
  validator = OutputValidator(allowed_patterns=[...])
  ```
- Guard against:
  - Prompt injection
  - XSS attacks
  - SQL injection
  - Excessive output

### Network Security

- Use HTTPS for all API communication
- Enable Redis authentication in production
- Use PostgreSQL with SSL for database connections
- Configure firewall rules for internal services

### Deployment

- Never run HiveFlow with debug mode in production
- Use non-root containers
- Set resource limits in Kubernetes
- Enable audit logging
