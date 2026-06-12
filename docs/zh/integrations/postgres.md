# PostgreSQL 集成

生产部署中，Studio 将工作流、凭据元数据与分析数据持久化到 PostgreSQL。

## 安装（Studio backend）

```bash
cd packages/studio/backend
pip install -r requirements.txt
```

依赖包含 `asyncpg` 及 `app/db/postgres_storage.py` 中配置的 SQLAlchemy 驱动。

## 配置

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/hiveflow
cd packages/studio/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker Compose

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+asyncpg://hiveflow:hiveflow@localhost:5432/hiveflow
```

## 存储内容

| 数据 | 位置 |
|------|----------|
| 工作流定义 | Postgres（经 Studio API） |
| 执行历史 | Postgres + 可选 blackboard |
| LLM 凭据 | Postgres 中加密（Studio） |

Core `hiveflow` 包**不**需要 Postgres — 仅 Studio backend 用它做持久化。

## 迁移

Studio 启动时通过 `init_storage()` 初始化 schema。生产环境应固定 schema 版本，并在 rollout 新版 Studio 前通过部署流水线执行迁移。

## 故障排查

| 问题 | 处理 |
|-------|-----|
| `asyncpg` 连接错误 | 确认 `DATABASE_URL` scheme 为 `postgresql+asyncpg://` |
| Permission denied | 为应用角色授予 schema 上的 CREATE 权限 |
