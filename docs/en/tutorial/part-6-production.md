# Part 6 — Production

Deploy HiveFlow, observe running systems, troubleshoot common issues, and navigate the repository.

## 6.1 Deployment options

| Method | Best for | Doc |
|--------|----------|-----|
| Docker Compose | Local / single-node prod | [Deployment](../deployment.md) |
| `docker-compose.release.yml` | Pre-built GHCR images | Release notes |
| Kubernetes | Multi-node clusters | `kubernetes/hiveflow-deployment.yaml` |
| PyPI embed | Custom apps without Studio | [Part 1](part-1-foundation.md) |

### Production Docker Compose

```bash
cp .env.example .env
# Set real API keys; unset HIVEFLOW_AGENT_ECHO_LLM
docker compose -f docker-compose.release.yml up -d
```

GHCR images (from Release v0.1.0):

- `ghcr.io/jdidjhdh/hiveflow-studio-api:0.1.0`
- `ghcr.io/jdidjhdh/hiveflow-studio-web:0.1.0`

### Health checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:3000
redis-cli ping   # PONG
```

## 6.2 Observability

| Signal | Tool | Doc |
|--------|------|-----|
| Metrics | Prometheus exporter, Studio Analytics | [Observability](../observability.md) |
| Traces | OpenTelemetry (optional) | `hiveflow.observability.tracing` |
| Logs | Structured JSON logger | Studio **Events**, **Audit Log** |
| Replay | Checkpoint + audit | Studio **Replay** |

Enable tracing:

```python
from hiveflow.observability.tracing import configure_tracing
configure_tracing(service_name="hiveflow-prod")
```

## 6.3 Security checklist

- [ ] Rotate `HIVEFLOW_ENCRYPTION_KEY` via secrets manager ([Part 3](part-3-advanced.md))
- [ ] Enable input/output guards ([Example 14](../../examples/14_guard_configuration.py))
- [ ] Use HITL for irreversible actions ([Part 2](part-2-workflows.md))
- [ ] Restrict Studio network access (reverse proxy + auth)
- [ ] Report vulnerabilities per [SECURITY.md](https://github.com/jdidjhdh/hiveflow/blob/main/SECURITY.md)

## 6.4 Scaling

```
                    ┌─────────────┐
                    │   Studio    │
                    │  (UI + API) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Agent pod    Agent pod    Agent pod
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │  blackboard │
                    └─────────────┘
```

- Set `blackboard_type=redis` for shared state ([Example 11](../../examples/11_distributed_agents.py))
- Postgres stores Studio metadata (workflows, credentials)
- Horizontal scale: multiple Agent/Core workers behind the same Redis URL

## 6.5 Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named 'hiveflow'` | Core not installed | `pip install -e packages/core` |
| `No module named 'cryptography'` | Missing security extra | `pip install "hiveflow-core[security]"` |
| Redis connection refused | Redis down | `docker compose up redis` |
| Docs build strict fail | Invalid mkdocs i18n key | Use top-level `edit_uri_template` |
| Docker pipe not found | Docker Desktop stopped | Start Docker Desktop |
| `git push` timeout | Network to github.com:443 | Use GitHub API scripts in `scripts/` |

## 6.6 Repository map

### Root files

| File | Purpose |
|------|---------|
| `README.md` / `README.zh.md` | Project overview |
| `docker-compose.yml` | Full local stack |
| `mkdocs.yml` | Documentation site config |
| `CHANGELOG.md` | Version history |
| `ROADMAP.md` | Product roadmap |
| `CONTRIBUTING.md` | How to contribute |
| `OSS_LAUNCH.md` | Launch checklist |

### Packages

| Path | PyPI | Role |
|------|------|------|
| `packages/core/hiveflow/` | `hiveflow-core` | Scheduler, blackboard, DAG, HITL, MCP |
| `packages/agent/` | `hiveflow-agent` | LLM, NL planning, ReAct worker |
| `packages/studio/backend/` | — | FastAPI REST + WebSocket |
| `packages/studio/frontend/` | — | React UI |

### Scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `verify_launch_readiness.py` | Pre-release CI gate |
| `setup_github_repo.py` | GitHub repo configuration |
| `post_discussion_announcement.py` | Post release announcement |
| `blind_test_tarball.py` | Simulate new-user install |

### CI (`.github/workflows/`)

| Workflow | Trigger | Action |
|----------|---------|--------|
| `test.yml` | push/PR | pytest all packages |
| `docs.yml` | push main | Deploy GitHub Pages |
| `release.yml` | tag `v*` | Build wheels + GHCR images |

## 6.7 Release & versioning

HiveFlow is **0.1.x Alpha**. Breaking changes may occur before 1.0.

- Install from GitHub Release wheels or editable source
- PyPI publish is optional (maintainer-controlled)
- See [Versioning](../versioning.md) and [release notes v0.1.0](../release-notes/v0.1.0.md)

## 6.8 Getting help

| Channel | Use for |
|---------|---------|
| [GitHub Issues](https://github.com/jdidjhdh/hiveflow/issues) | Bugs |
| [Discussions](https://github.com/jdidjhdh/hiveflow/discussions) | Questions, ideas |
| [Docs](https://jdidjhdh.github.io/hiveflow/) | Tutorials, API |
| Edit this page (docs) | Doc fixes via PR |

## 6.9 Final exercise — end-to-end

1. `docker compose up --build`
2. Golden Path in Studio (Part 5)
3. Approve a HITL gate
4. Inspect **Replay** and **Analytics**
5. Run `python examples/run_smoke_tests.py` from a fresh venv
6. Export plan to LangGraph JSON

Congratulations — you've completed the full HiveFlow tutorial.

← Back to [Tutorial index](index.md)
