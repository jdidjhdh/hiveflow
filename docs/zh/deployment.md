# 部署指南

如何在各种环境中部署 HiveFlow。

---

## 本地开发

### 使用 Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

服务：
- **Studio Backend**：`http://localhost:8000`
- **Studio Frontend**：`http://localhost:3000`
- **Redis**：`localhost:6379`
- **PostgreSQL**：`localhost:5432`

### 手动搭建

```bash
# 1. Start Redis and PostgreSQL
# (or use Docker)
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=hiveflow postgres:15-alpine

# 2. Install dependencies
cd packages/core && pip install -e ".[all]"
cd packages/studio/backend && pip install -r requirements.txt
cd packages/studio/frontend && npm install

# 3. Start services
cd packages/studio/backend && uvicorn app.main:app --reload
cd packages/studio/frontend && npm run dev
```

---

## Docker 部署

### 构建镜像

```bash
# Core
docker build -t hiveflow-core packages/core

# Agent
docker build -t hiveflow-agent packages/agent

# Studio Backend
docker build -t hiveflow-studio-backend packages/studio/backend

# Studio Frontend
docker build -t hiveflow-studio-frontend packages/studio/frontend
```

### 使用 Docker 运行

```bash
docker run -d \
  -p 8000:8000 \
  -e REDIS_URL=redis://redis:6379 \
  -e DB_URL=sqlite:///./hiveflow.db \
  -e OPENAI_API_KEY=sk-... \
  hiveflow-studio-backend
```

---

## Kubernetes 部署

### 使用提供的清单

```bash
# Apply Kubernetes manifests
kubectl apply -f kubernetes/hiveflow-deployment.yaml

# Check status
kubectl get pods -l app=hiveflow
kubectl get services -l app=hiveflow
```

### 自定义部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hiveflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hiveflow
  template:
    metadata:
      labels:
        app: hiveflow
    spec:
      containers:
      - name: studio
        image: hiveflow-studio:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Helm Chart（规划中）

Helm Chart 支持计划在未来版本中提供。

---

## 生产最佳实践

### 安全

1. **切勿以 debug 模式运行**：
   ```bash
   HIVEFLOW_DEBUG=false
   ```

2. **使用 HTTPS**：
   - 配置反向代理（nginx、traefik）
   - 使用 Let's Encrypt 获取 TLS 证书

3. **定期轮换 API Key**：
   - 使用 Kubernetes Secrets 或 AWS Secrets Manager
   - 切勿将 Key 提交到版本控制

4. **启用加密**：
   ```bash
   HIVEFLOW_ENCRYPTION_KEY=<min-32-characters>
   pip install "hiveflow[security]"
   ```

### 可扩展性

1. **水平 Pod 自动扩缩（HPA）**：
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: hiveflow-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: hiveflow
     minReplicas: 2
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
   ```

2. **使用 Redis 作为分布式黑板**：
   - 配置 Redis Cluster 以实现高可用
   - 设置合适的内存上限与淘汰策略

3. **数据库连接池**：
   - PostgreSQL 使用 PgBouncer
   - 合理配置连接数上限

### 监控

1. **结构化日志**：
   ```bash
   HIVEFLOW_LOG_LEVEL=INFO
   HIVEFLOW_LOG_FORMAT=json
   ```

2. **指标（Prometheus）**：
   - 暴露 `/metrics` 端点
   - 使用提供的 Grafana 仪表盘（`packages/core/observability/grafana-dashboard.json`）

3. **健康检查**：
   - `/health` — 基础健康检查
   - `/health/ready` — 就绪探针
   - `/health/live` — 存活探针

### 备份

1. **数据库备份**：
   ```bash
   pg_dump hiveflow > hiveflow_backup.sql
   ```

2. **Checkpoint 备份**：
   - 定期对 checkpoint 存储做快照
   - 定期演练恢复流程

---

## 云厂商指南

### AWS

- 使用 ECS 或 EKS 进行容器编排
- RDS 托管 PostgreSQL
- ElastiCache 托管 Redis
- Secrets Manager 管理 API Key

### GCP

- 使用 GKE 进行容器编排
- Cloud SQL 托管 PostgreSQL
- Memorystore 托管 Redis
- Secret Manager 管理 API Key

### Azure

- 使用 AKS 进行容器编排
- Azure Database for PostgreSQL
- Azure Cache for Redis
- Key Vault 管理密钥
