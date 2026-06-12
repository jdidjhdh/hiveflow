# ==============================================
# HiveFlow Studio Backend - Dockerfile
# Build context: repository root (see docker-compose.yml)
# ==============================================
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/core /packages/core
COPY packages/agent /packages/agent
RUN pip install --no-cache-dir -e /packages/core -e /packages/agent

COPY packages/studio/backend/requirements.txt /tmp/requirements.txt
RUN grep -v '^-e' /tmp/requirements.txt > /tmp/requirements-pip.txt \
    && pip install --no-cache-dir -r /tmp/requirements-pip.txt

COPY packages/studio/backend /app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
