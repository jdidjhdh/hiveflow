# Redis 集成

Redis 为多进程 / 多节点部署提供分布式事件总线与黑板。

## 安装

```bash
pip install "hiveflow-core[redis]"
```

## 事件总线（RedisEventBus）

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

## 黑板（RedisBlackboard）

```python
config = HiveFlowConfig(
    scheduler=SchedulerConfig(),
    blackboard_type="redis",
    redis_url="redis://localhost:6379/0",
)
```

## Docker Compose

仓库根目录 `docker-compose.yml` 包含本地开发用 Redis：

```bash
docker compose up -d redis
export REDIS_URL=redis://localhost:6379/0
```

## Studio

运行后端时设置 `REDIS_URL`，以便多个 Studio 实例共享状态：

```bash
cd packages/studio/backend
REDIS_URL=redis://localhost:6379/0 uvicorn app.main:app --reload
```

## 生产检查清单

| 项 | 建议 |
|------|----------------|
| 持久化 | 为黑板耐久性启用 Redis AOF |
| TLS | 生产环境使用 `rediss://` URL |
| 认证 | `redis://:password@host:6379/0` |
| Key 前缀 | 用独立 DB 索引或 key 命名空间隔离租户 |

## 故障排查

| 问题 | 处理 |
|-------|-----|
| Connection refused | 确保 Redis 正在运行（`docker compose up redis`） |
| 跨进程未收到事件 | 确认所有节点使用相同 `redis_url` 且 `bus_type="redis"` |
