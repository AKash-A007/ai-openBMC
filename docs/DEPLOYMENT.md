# AI OpsBMC — Deployment Guide

Covers Docker Compose (local/staging) and Kubernetes (production) deployment.

---

## Table of Contents

1. [Quick Start — Docker Compose](#1-quick-start--docker-compose)
2. [Production Docker Compose](#2-production-docker-compose)
3. [Kubernetes Deployment](#3-kubernetes-deployment)
4. [Environment Variables](#4-environment-variables)
5. [Database Setup](#5-database-setup)
6. [SSL / TLS](#6-ssl--tls)
7. [Scaling](#7-scaling)
8. [Backup and Recovery](#8-backup-and-recovery)
9. [Health Checks](#9-health-checks)

---

## 1. Quick Start — Docker Compose

```bash
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC
cp .env.example .env    # edit as needed
docker compose up --build -d
```

Verify all services are running:
```bash
docker compose ps
curl http://localhost:8000/health
```

---

## 2. Production Docker Compose

For production, set the following in `.env`:

```env
# Use PostgreSQL instead of SQLite
DATABASE_URL=postgresql://aiobmc:securepassword@postgres:5432/aiobmc

# Strong secret key (generate with: openssl rand -hex 32)
SECRET_KEY=a8f3d9c1b2e4f7a0d3c6e9f2b5a8d1c4e7f0a3b6c9d2e5f8a1b4c7d0e3f6a9

# Real BMC
BMC_HOST=192.168.1.100
BMC_USE_SSL=true
```

Then start with:
```bash
docker compose -f docker-compose.yml up -d
```

---

## 3. Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (GKE, EKS, AKS, or kubeadm)
- `kubectl` configured for your cluster
- Container registry (Docker Hub, GCR, ECR)

### Build and Push Images

```bash
# Set your registry
REGISTRY=your-dockerhub-username

# Build all services
docker build -t $REGISTRY/aiobmc-collector:latest services/collector/
docker build -t $REGISTRY/aiobmc-analytics:latest services/analytics/
docker build -t $REGISTRY/aiobmc-agent:latest services/agent/
docker build -t $REGISTRY/aiobmc-dashboard:latest services/dashboard/

# Push to registry
docker push $REGISTRY/aiobmc-collector:latest
docker push $REGISTRY/aiobmc-analytics:latest
docker push $REGISTRY/aiobmc-agent:latest
docker push $REGISTRY/aiobmc-dashboard:latest
```

### Configure Secrets

Edit `k8s/secrets.yaml` with your base64-encoded values:

```bash
# Generate base64 values
echo -n "your-secret-key" | base64
echo -n "your-db-password" | base64
```

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: aiobmc-secrets
data:
  SECRET_KEY: <base64-encoded-value>
  DB_PASSWORD: <base64-encoded-value>
  BMC_PASSWORD: <base64-encoded-value>
```

### Deploy to Kubernetes

```bash
# Apply all manifests in order
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pv-pvc.yaml
kubectl apply -f k8s/postgres.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=60s

kubectl apply -f k8s/collector.yaml
kubectl apply -f k8s/analytics.yaml
kubectl apply -f k8s/agent.yaml
kubectl apply -f k8s/dashboard.yaml
kubectl apply -f k8s/ingress.yaml
```

### Verify Deployment

```bash
kubectl get pods
kubectl get services
kubectl logs -f deployment/aiobmc-dashboard
```

### Access the Dashboard

With the ingress configured:
```
http://aiobmc.yourdomain.com
```

Or with port-forwarding for testing:
```bash
kubectl port-forward service/aiobmc-dashboard 8000:8000
```

---

## 4. Environment Variables

See [Configuration Reference](USER_GUIDE.md#13-configuration-reference) in the User Guide for the full list.

For Kubernetes, environment variables are injected via:
- `k8s/configmap.yaml` — non-sensitive config
- `k8s/secrets.yaml` — sensitive credentials (encrypted at rest by K8s)

---

## 5. Database Setup

### SQLite (Development Only)

No setup required. Database is created automatically at `telemetry/db/telemetry.db`.

### PostgreSQL (Production)

The `k8s/postgres.yaml` and `docker-compose.yml` both provision a PostgreSQL 15 container automatically.

To use an external managed database (Cloud SQL, RDS, Azure Database):

```env
DATABASE_URL=postgresql://username:password@your-db-host:5432/aiobmc
```

Database schema is created automatically on first startup.

### Database Migration

If upgrading between versions:
```bash
# Inside any service container
python -c "from telemetry.database import init_db; init_db()"
```

---

## 6. SSL / TLS

### For the Dashboard API

Place your certificates in a `certs/` directory and configure nginx or the Kubernetes ingress:

```yaml
# k8s/ingress.yaml (with TLS)
spec:
  tls:
  - hosts:
    - aiobmc.yourdomain.com
    secretName: aiobmc-tls
  rules:
  - host: aiobmc.yourdomain.com
    ...
```

### For BMC Communication

If your BMC uses a self-signed certificate:
```env
BMC_USE_SSL=true
BMC_VERIFY_SSL=false    # disable cert verification for self-signed
```

For production, add your BMC CA certificate:
```env
BMC_CA_CERT=/etc/ssl/certs/bmc-ca.pem
```

---

## 7. Scaling

### Horizontal Scaling (Kubernetes)

The Analytics and Agent services are stateless and can be scaled horizontally:

```bash
kubectl scale deployment aiobmc-analytics --replicas=3
kubectl scale deployment aiobmc-agent --replicas=2
```

The Collector service should remain at 1 replica per BMC host to avoid duplicate telemetry writes.

### Vertical Scaling

For larger deployments, increase resource limits in `k8s/*.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

---

## 8. Backup and Recovery

### Database Backup

**SQLite:**
```bash
cp telemetry/db/telemetry.db telemetry.db.backup.$(date +%Y%m%d)
```

**PostgreSQL:**
```bash
docker compose exec postgres pg_dump -U aiobmc aiobmc > backup.sql
# or on Kubernetes:
kubectl exec deployment/postgres -- pg_dump -U aiobmc aiobmc > backup.sql
```

### Restore

```bash
# PostgreSQL
docker compose exec -T postgres psql -U aiobmc aiobmc < backup.sql
```

### RAG Index Backup

```bash
cp -r chroma_db/ chroma_db.backup.$(date +%Y%m%d)/
```

---

## 9. Health Checks

All services expose a `/health` endpoint used by Docker and Kubernetes liveness/readiness probes.

```bash
# Check all services
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

Expected response:
```json
{"status": "healthy", "version": "1.0.0"}
```

Docker Compose health check is configured in `docker-compose.yml` with:
- Interval: 30s
- Timeout: 10s
- Retries: 3

Kubernetes probes are defined in each `k8s/*.yaml` manifest.
