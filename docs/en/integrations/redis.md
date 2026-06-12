# Redis Integration

Redis backs distributed event bus and blackboard for multi-process / multi-node deployments.

## Install

```bash
pip install "hiveflow-core[redis]"
```

## Event bus (RedisEventBus)

```python
from hiveflow import HiveFlow, HiveFlowConfig, SchedulerConfig

config = HiveFlowConfig(
    scheduler=SchedulerConfig(),
    blackboard_type="memory",
    bus_type="redis",
    redis_url="redis://localhost:6379/0",
)
hf = HiveFlow(config)
await hf.start()
```

## Blackboard (RedisBlackboard)

```python
config = HiveFlowConfig(
    scheduler=SchedulerConfig(),
    blackboard_type="redis",
    redis_url="redis://localhost:6379/0",
)
```

## Docker Compose

The repo root `docker-compose.yml` includes Redis for local development:

```bash
docker compose up -d redis
export REDIS_URL=redis://localhost:6379/0
```

## Studio

Set `REDIS_URL` when running the backend for shared state across Studio instances:

```bash
cd packages/studio/backend
REDIS_URL=redis://localhost:6379/0 uvicorn app.main:app --reload
```

## Production checklist

| Item | Recommendation |
|------|----------------|
| Persistence | Enable Redis AOF for blackboard durability |
| TLS | Use `rediss://` URLs in production |
| Auth | `redis://:password@host:6379/0` |
| Key prefix | Isolate tenants with separate DB index or key namespaces |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection refused | Ensure Redis is running (`docker compose up redis`) |
| Event not received cross-process | Confirm all nodes use same `redis_url` and `bus_type="redis"` |
