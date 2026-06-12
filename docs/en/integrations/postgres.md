# PostgreSQL Integration

Studio persists workflows, credentials metadata, and analytics to PostgreSQL in production deployments.

## Install (Studio backend)

```bash
cd packages/studio/backend
pip install -r requirements.txt
```

Requirements include `asyncpg` and SQLAlchemy drivers as configured in `app/db/postgres_storage.py`.

## Configuration

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

## What is stored

| Data | Location |
|------|----------|
| Workflow definitions | Postgres via Studio API |
| Execution history | Postgres + optional blackboard |
| LLM credentials | Encrypted in Postgres (Studio) |

Core `hiveflow` package does **not** require Postgres — only Studio backend uses it for persistence.

## Migrations

Studio initializes schema on startup via `init_storage()`. For production, pin schema version and run migrations through your deployment pipeline before rolling out new Studio versions.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `asyncpg` connection errors | Verify `DATABASE_URL` scheme is `postgresql+asyncpg://` |
| Permission denied | Grant CREATE on schema to application role |
