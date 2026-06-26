# 🖥️ AI OpsBMC

> **An AI-augmented, autonomous AIOps platform for OpenBMC-based server management.**  
> From raw BMC telemetry to audited autonomous remediation — in a single unified system.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://www.docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?logo=kubernetes)](https://kubernetes.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-orange)](https://www.trychroma.com)
[![scikit-learn](https://img.shields.io/badge/IsolationForest-Anomaly_Detection-F7931E?logo=scikitlearn)](https://scikit-learn.org)
[![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6522C?logo=prometheus)](https://prometheus.io)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?logo=grafana)](https://grafana.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🔑 What Is AI OpsBMC?

AI OpsBMC transforms [OpenBMC](https://github.com/openbmc/openbmc) — the open-source server BMC firmware — from a passive telemetry source into an **autonomous, self-healing server management system**.

The platform covers the full AIOps operational loop:

```
Collect → Detect → Diagnose → Predict → Recommend → Approve → Execute → Audit
```

No OS-level agents. No cloud dependency. No labelled training data required.

---

## ✨ Key Features

| Feature | Technology | Description |
|---------|-----------|-------------|
| **Real-time Telemetry** | Redfish REST API | CPU temps, fan speeds, PSU power, DIMM errors |
| **Anomaly Detection** | Isolation Forest | Unsupervised, no labelled data required |
| **Failure Prediction** | Random Forest | Multi-horizon: 1 min, 5 min, 15 min |
| **AI Fault Diagnosis** | RAG + LLM | Grounded diagnosis via ChromaDB + all-MiniLM-L6-v2 |
| **Autonomous Remediation** | Policy Engine | Governance-first: Policy → Approve → Execute → Rollback → Audit |
| **Production Ready** | Docker + K8s | 4 microservices, JWT auth, RBAC, rate limiting |
| **Observability** | Prometheus + Grafana | Full metrics stack with pre-built dashboards |
| **Security** | JWT / RBAC | Role-based access: viewer, operator, admin, automation |

---

## 🏗️ Architecture

AI OpsBMC is composed of four independent microservices:

```
┌──────────────────────────────────────────────────────────────────┐
│                        AI OpsBMC Platform                        │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │   Collector  │──▶│  Analytics   │──▶│    Agent Service     │ │
│  │   :8001      │   │   :8002      │   │        :8003         │ │
│  │              │   │              │   │                      │ │
│  │ Redfish Poll │   │ Iso Forest   │   │ RAG Engine           │ │
│  │ Batch Insert │   │ RF Predictor │   │ Policy Engine        │ │
│  │ DB Writer    │   │ Health Score │   │ Approval Manager     │ │
│  └──────────────┘   └──────────────┘   │ Execution Engine     │ │
│         │                  │           │ Rollback Manager     │ │
│         ▼                  ▼           │ Audit Logger         │ │
│  ┌──────────────────────────────────┐  └──────────────────────┘ │
│  │  PostgreSQL / SQLite Telemetry   │            │               │
│  └──────────────────────────────────┘            ▼               │
│                                      ┌──────────────────────┐   │
│                                      │  Dashboard  :8000    │   │
│                                      │  FastAPI + Prometheus│   │
│                                      └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Intelligence Pipeline

```
BMC Telemetry (Redfish)
        │
        ▼
┌───────────────────┐
│ Anomaly Detection │  ← Isolation Forest (unsupervised)
│ Health Scoring    │  ← Weighted multi-sensor aggregation
│ Failure Prediction│  ← Random Forest, 3-horizon forecast
└───────────────────┘
        │ anomaly event
        ▼
┌───────────────────┐
│  RAG Diagnosis    │  ← all-MiniLM-L6-v2 + ChromaDB + LLM
│  Root Cause       │  ← Grounded in BMC knowledge base
│  Recommendations  │  ← Ranked action list
└───────────────────┘
        │ recommendation
        ▼
┌───────────────────┐
│  Policy Engine    │  ← Is this action permitted?
│  Approval Gate    │  ← Human sign-off if required
│  Execution Engine │  ← Execute with timeout + health check
│  Rollback Manager │  ← Auto-undo if health degrades
│  Audit Logger     │  ← Immutable event record
└───────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ or Docker & Docker Compose

### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC

# Copy and configure environment
cp .env.example .env

# Start all services (mock BMC included)
docker compose up --build -d

# Open dashboard
open http://localhost:8000
```

### Option 2: Local Python

```bash
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build RAG index (first time only)
python -c "from rag_engine import build_index; build_index(force=True)"

# Start mock BMC simulator
python mock_bmc.py &

# Start the platform
python main.py
```

Dashboard available at: **http://localhost:8000**  
Grafana at: **http://localhost:3000**

---

## 📁 Project Structure

```
ai-openBMC/
├── analytics/              # AI analytics layer
│   ├── anomaly_detector.py # Isolation Forest anomaly detection
│   ├── features.py         # Rolling-window feature engineering
│   ├── health_score.py     # Weighted system health aggregation
│   └── predictor.py        # Multi-horizon failure prediction
│
├── automation/             # Autonomous remediation pipeline
│   ├── policy_engine.py    # Rule-based action governance
│   ├── approval_manager.py # Human approval gate + timeout
│   ├── execution_engine.py # Action execution lifecycle
│   ├── rollback_manager.py # Automatic rollback on health degradation
│   └── audit_logger.py     # Immutable append-only audit trail
│
├── knowledge/              # RAG knowledge base (plain text)
│   ├── cpu_failures.txt
│   ├── dimm_failure.txt
│   └── psu_failures.txt
│
├── monitoring/             # Observability stack
│   ├── grafana/            # Pre-built Grafana dashboard JSON
│   ├── prometheus/         # Prometheus scrape configuration
│   ├── metrics.py          # Prometheus metric definitions
│   └── alerts.py           # Alert rule definitions
│
├── services/               # Microservice entrypoints (FastAPI)
│   ├── collector/          # Telemetry collection service
│   ├── analytics/          # Anomaly detection service
│   ├── agent/              # Diagnosis + remediation service
│   └── dashboard/          # REST API + web dashboard
│
├── telemetry/              # Data layer
│   ├── collector.py        # Redfish polling + batch insert
│   ├── database.py         # SQLite/PostgreSQL abstraction
│   └── query.py            # Query helpers + 2s TTL cache
│
├── tests/                  # Pytest test suite
├── k8s/                    # Kubernetes manifests
├── .github/workflows/      # GitHub Actions CI/CD
├── docs/                   # Full documentation
│   ├── USER_GUIDE.md       # Complete usage guide
│   ├── API_REFERENCE.md    # REST API documentation
│   └── DEPLOYMENT.md       # Docker + Kubernetes deployment
│
├── PAPER.md                # Research paper
├── CONTRIBUTING.md         # Contributor guide
├── main.py                 # Monolith entry point (dev/testing)
├── app.py                  # FastAPI application
├── rag_engine.py           # RAG retrieval engine
├── mock_bmc.py             # Redfish-compatible BMC simulator
├── docker-compose.yml      # Full-stack orchestration
└── requirements.txt        # Python dependencies
```

---

## 📊 Performance Results

*(Evaluated on simulated telemetry with controlled fault injection)*

### Anomaly Detection

| Method | Precision | Recall | F1-Score |
|--------|-----------|--------|----------|
| Static Threshold Rules | 0.71 | 0.83 | 0.77 |
| **AI OpsBMC (Isolation Forest)** | **0.91** | **0.93** | **0.92** |

### Diagnosis Accuracy

| Method | Accuracy |
|--------|---------|
| Keyword rules | 58% |
| LLM without RAG | 71% |
| **RAG + Knowledge Base** | **91%** |

### Latency

| Metric | Value |
|--------|-------|
| Anomaly detection | < 25ms (P99) |
| RAG retrieval (warm cache) | < 15ms (P99) |
| End-to-end MTTR | ~1.4 seconds |

### Remediation Safety (500 simulated cycles)

| Metric | Value |
|--------|-------|
| Policy correctness | 97.4% |
| False approvals | **0%** |
| Successful remediations | 89.2% |
| Audit completeness | **100%** |

---

## 🔌 API Overview

Full documentation: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

```bash
# Authenticate
POST /token

# System health
GET  /health
GET  /status

# Telemetry
GET  /telemetry/latest
GET  /telemetry/history/{sensor}

# Anomaly detection
GET  /anomalies
POST /anomalies/detect

# Failure prediction
GET  /predictions/{sensor}

# AI diagnosis
POST /diagnose
GET  /diagnoses

# Remediation
GET  /remediation/actions
POST /remediation/approve/{action_id}
POST /remediation/reject/{action_id}

# Audit
GET  /audit

# Prometheus metrics
GET  /metrics
```

---

## 🔒 Security

- **Authentication**: HS256-signed JWT tokens
- **Authorisation**: Role-Based Access Control (RBAC)
  - `viewer` → read-only telemetry and diagnoses
  - `operator` → trigger scans and diagnoses
  - `admin` → approve/reject remediation actions
  - `automation` → execute actions autonomously
- **Rate limiting**: 100 requests/minute per IP
- **Secrets management**: Kubernetes Secrets / `.env` file (never committed)

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=html

# CI pipeline (runs automatically on PRs)
# See .github/workflows/ci.yml
```

---

## 📦 Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pv-pvc.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/collector.yaml
kubectl apply -f k8s/analytics.yaml
kubectl apply -f k8s/agent.yaml
kubectl apply -f k8s/dashboard.yaml
kubectl apply -f k8s/ingress.yaml
```

Full instructions: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

---

## 📄 Research Paper

The full research paper documenting the system design, experimental evaluation, and results is available at [`PAPER.md`](PAPER.md).

**Title:** *AI OpsBMC: An AI-Augmented Predictive Fault Diagnosis and Autonomous Remediation Framework for OpenBMC-Based Server Management Systems*

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Installation, configuration, and usage walkthrough |
| [API Reference](docs/API_REFERENCE.md) | Full REST API documentation with examples |
| [Deployment Guide](docs/DEPLOYMENT.md) | Docker Compose + Kubernetes deployment |
| [Contributing](CONTRIBUTING.md) | Development setup and contribution guide |
| [Research Paper](PAPER.md) | Full academic paper |
| [Architecture](architectue.md) | System architecture deep-dive |

---

## 🗺️ Project Phases

| Phase | Weeks | Focus | Status |
|-------|-------|-------|--------|
| **Phase A** | W1–W4 | Core prototype: RAG + LLM diagnosis, Redfish integration | ✅ Complete |
| **Phase B** | W1–W4 | AI analytics: anomaly detection, prediction, health scoring | ✅ Complete |
| **Phase C** | W1–W4 | Autonomous remediation: policy engine, approval, audit | ✅ Complete |
| **Phase D** | W1–W6 | Production: microservices, Docker, K8s, CI/CD, security, observability | ✅ Complete |
| **Research** | W7–W8 | Benchmarking datasets, experiments, research paper | ✅ Paper written |

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development environment setup
- Coding standards (PEP 8, type hints, docstrings)
- How to add knowledge base entries
- How to add remediation actions
- PR workflow

---

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [OpenBMC Foundation](https://github.com/openbmc/openbmc) — the BMC firmware platform this project builds upon
- [Sentence Transformers](https://www.sbert.net/) — `all-MiniLM-L6-v2` embedding model
- [ChromaDB](https://www.trychroma.com/) — vector store for RAG retrieval
- [scikit-learn](https://scikit-learn.org/) — Isolation Forest and Random Forest implementations
- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework

---

*Built as a research and learning project exploring the intersection of AI, AIOps, and embedded server management.*