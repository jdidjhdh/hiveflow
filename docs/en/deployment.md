# Deployment Guide

How to deploy HiveFlow in various environments.

---

## Local Development

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services:
- **Studio Backend**: `http://localhost:8000`
- **Studio Frontend**: `http://localhost:3000`
- **Redis**: `localhost:6379`
- **PostgreSQL**: `localhost:5432`

### Manual Setup

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

## Docker Deployment

### Build Images

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

### Run with Docker

```bash
docker run -d \
  -p 8000:8000 \
  -e REDIS_URL=redis://redis:6379 \
  -e DB_URL=sqlite:///./hiveflow.db \
  -e OPENAI_API_KEY=sk-... \
  hiveflow-studio-backend
```

---

## Kubernetes Deployment

### Using Provided Manifests

```bash
# Apply Kubernetes manifests
kubectl apply -f kubernetes/hiveflow-deployment.yaml

# Check status
kubectl get pods -l app=hiveflow
kubectl get services -l app=hiveflow
```

### Custom Deployment

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

### Helm Chart (Future)

Helm chart support is planned for a future release.

---

## Production Best Practices

### Security

1. **Never run with debug mode**:
   ```bash
   HIVEFLOW_DEBUG=false
   ```

2. **Use HTTPS**:
   - Configure reverse proxy (nginx, traefik)
   - Use Let's Encrypt for TLS certificates

3. **Rotate API keys regularly**:
   - Use Kubernetes Secrets or AWS Secrets Manager
   - Never commit keys to version control

4. **Enable encryption**:
   ```bash
   HIVEFLOW_ENCRYPTION_KEY=<min-32-characters>
   pip install "hiveflow-core[security]"
   ```

### Scalability

1. **Horizontal Pod Autoscaling**:
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

2. **Use Redis for distributed blackboard**:
   - Configure Redis Cluster for high availability
   - Set appropriate memory limits and eviction policies

3. **Database connection pooling**:
   - Use PgBouncer for PostgreSQL
   - Configure connection limits appropriately

### Monitoring

1. **Structured logging**:
   ```bash
   HIVEFLOW_LOG_LEVEL=INFO
   HIVEFLOW_LOG_FORMAT=json
   ```

2. **Metrics (Prometheus)**:
   - Expose `/metrics` endpoint
   - Use provided Grafana dashboard (`packages/core/observability/grafana-dashboard.json`)

3. **Health checks**:
   - `/health` — Basic health check
   - `/health/ready` — Readiness probe
   - `/health/live` — Liveness probe

### Backup

1. **Database backups**:
   ```bash
   pg_dump hiveflow > hiveflow_backup.sql
   ```

2. **Checkpoint backups**:
   - Regular snapshots of checkpoint storage
   - Test restore procedures periodically

---

## Cloud Provider Guides

### AWS

- Use ECS or EKS for container orchestration
- RDS for PostgreSQL
- ElastiCache for Redis
- Secrets Manager for API keys

### GCP

- Use GKE for container orchestration
- Cloud SQL for PostgreSQL
- Memorystore for Redis
- Secret Manager for API keys

### Azure

- Use AKS for container orchestration
- Azure Database for PostgreSQL
- Azure Cache for Redis
- Key Vault for secrets
