# Part 3 — Advanced

Cognitive planning, evaluation, encrypted blackboard, distributed deployment, custom schedulers, plugins, and guards.

## 3.1 Cognitive planning (Example 08)

Dynamic plan generation when steps are not known upfront.

```bash
python examples/08_cognitive_planning.py
```

The cognitive orchestrator:

1. Analyzes the goal.
2. Generates a multi-step plan with rationale.
3. Executes steps and logs reasoning.

Output includes `plan rationale`, `steps executed`, and a `reasoning log` — useful for debugging Agent mode plans in Studio.

## 3.2 Evaluation & A/B testing (Example 09)

Measure output quality with keyword overlap, completeness, and clarity scores.

```bash
python examples/09_evaluation.py
```

```python
# Conceptual usage
report = evaluator.evaluate(output, reference, criteria=["accuracy", "completeness", "clarity"])
print(report.total_score, report.passed)
winner = ab_runner.compare_variant_a_vs_b(output_a, output_b)
```

Integrate with CI to gate prompt or model changes. Studio **A/B Testing** page exposes similar workflows.

## 3.3 Secure blackboard (Example 10)

Encrypt sensitive keys at rest with audit logging.

```bash
pip install "hiveflow-core[security]"
python examples/10_secure_blackboard.py
```

```python
import os
from cryptography.fernet import Fernet
from hiveflow import HiveFlow, HiveFlowConfig, EnvKeyProvider

os.environ["HIVEFLOW_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

config = HiveFlowConfig(
    blackboard_type="encrypted",
    encryption_key_provider=EnvKeyProvider("HIVEFLOW_ENCRYPTION_KEY"),
)
hf = HiveFlow(config)
```

**Never commit encryption keys.** Use a secrets manager in production.

## 3.4 Distributed agents (Example 11)

Share state across processes with Redis-backed blackboard and bus.

```bash
docker run -d -p 6379:6379 redis:7-alpine
python examples/11_distributed_agents.py
```

```python
config = HiveFlowConfig(
    blackboard_type="redis",
    redis_url="redis://localhost:6379",
)
```

If Redis is unavailable, Example 11 falls back to in-memory mode with a warning — fine for local dev, not for production.

See [Redis integration](../integrations/redis.md).

## 3.5 Custom scheduler (Example 12)

Plug in your own agent selection strategy.

```bash
python examples/12_custom_scheduler.py
```

Built-in strategies:

| Strategy | Behavior |
|----------|----------|
| `least_loaded` | Pick agent with smallest queue |
| `auction` | Agents bid based on load/capability |
| `load_aware` | Weighted by CPU/memory hints |

Subclass or register a custom strategy for domain-specific routing (e.g. GPU agents, region affinity).

## 3.6 Plugin development (Example 13)

Browse, search, and install MCP plugins from the marketplace.

```bash
python examples/13_plugin_development.py
```

Built-in plugins include Filesystem, Web Search, Database, API Client, and Code Executor. Categories: `data`, `tools`, `development`, `communication`, `ai`.

```python
from hiveflow import PluginMarketplace, MCPPluginManager

marketplace = PluginMarketplace()
plugin_manager = MCPPluginManager()
await marketplace.install_plugin("filesystem", plugin_manager)
```

Studio **Capability Market** lists the same plugins with install/uninstall actions.

## 3.7 Input/output guards (Example 14)

Block prompt injection and validate outputs before they reach users or tools.

```bash
python examples/14_guard_configuration.py
```

Guards integrate with agents and Studio for defense in depth:

- **Input guard** — regex / pattern blocklists (e.g. "ignore previous instructions").
- **Output guard** — size limits, schema validation.

Configure per-agent or globally via `HiveFlowConfig`.

## 3.8 Advanced topics checklist

| Topic | Example | Extra |
|-------|---------|-------|
| Dynamic planning | `08` | Studio Agent plan-only |
| Quality gates | `09` | [Quality Gates](../quality-gates.md) |
| Encryption | `10` | `[security]` extra |
| Redis scale-out | `11` | `docker-compose.yml` redis service |
| Scheduler policy | `12` | `SchedulerConfig` |
| MCP plugins | `13` | `/api/plugins` in Studio |
| Safety guards | `14` | HITL + guards combined |

## 3.9 Exercises

1. Run Example 10 with a key rotated mid-session — observe decrypt behavior.
2. Register a custom scheduler that always picks agent `specialist`.
3. Block a known injection string in Example 14 and verify the workflow stops cleanly.

## Next

→ [Part 4 — Integrations](part-4-integrations.md): multimodal pipelines and LangGraph export.
