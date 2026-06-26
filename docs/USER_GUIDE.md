# AI OpsBMC — User Guide

**Complete guide to deploying, configuring, and using the AI OpsBMC platform.**

---

## Table of Contents

1. [What is AI OpsBMC?](#1-what-is-ai-openbmc)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Running the Platform](#4-running-the-platform)
5. [The Dashboard](#5-the-dashboard)
6. [Understanding the Telemetry Feed](#6-understanding-the-telemetry-feed)
7. [Anomaly Alerts](#7-anomaly-alerts)
8. [Reading Diagnoses](#8-reading-diagnoses)
9. [Managing Remediation Actions](#9-managing-remediation-actions)
10. [The Audit Log](#10-the-audit-log)
11. [Monitoring with Grafana](#11-monitoring-with-grafana)
12. [Connecting a Real BMC](#12-connecting-a-real-bmc)
13. [Configuration Reference](#13-configuration-reference)
14. [Troubleshooting](#14-troubleshooting)
15. [FAQ](#15-faq)

---

## 1. What is AI OpsBMC?

AI OpsBMC is an intelligent, autonomous server management platform built on top of OpenBMC. It connects to your server's Baseboard Management Controller (BMC) via the Redfish API, collects sensor telemetry (temperatures, fan speeds, power consumption, memory errors), and uses AI to:

- **Detect** anomalies in real-time using Isolation Forest
- **Predict** failures up to 15 minutes in advance using Random Forest models
- **Diagnose** root causes using a RAG-powered AI that reads your BMC knowledge base
- **Recommend** remediation actions ranked by priority
- **Execute** approved actions autonomously within policy boundaries
- **Audit** every action with an immutable log

The system is designed for server administrators, SREs, and data-centre operators who want to move from reactive firefighting to proactive, autonomous infrastructure management.

---

## 2. Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Core runtime |
| Docker | 24+ | Container orchestration |
| Docker Compose | 2.x | Multi-service orchestration |
| Git | Any | Version control |
| 4 GB RAM | minimum | For all services + models |
| BMC with Redfish | (optional) | Live telemetry source |

If you don't have a physical BMC, no problem — the built-in `mock_bmc.py` simulates one for you.

---

## 3. Installation

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC

# 2. Copy the example environment file
cp .env.example .env

# 3. Edit .env with your settings (see Configuration Reference)
nano .env

# 4. Start all services
docker compose up --build -d

# 5. Check that all services are healthy
docker compose ps
```

### Option B: Local Python Environment

```bash
# 1. Clone and enter the project
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Build the RAG knowledge base index (first time only)
python -c "from rag_engine import build_index; build_index(force=True)"

# 5. Start the mock BMC (if no physical BMC available)
python mock_bmc.py &

# 6. Start the main application
python main.py
```

---

## 4. Running the Platform

### Start

```bash
docker compose up -d       # start in background
docker compose up          # start in foreground (shows logs)
```

### Stop

```bash
docker compose down
```

### View Logs

```bash
docker compose logs -f             # all services
docker compose logs -f agent       # agent service only
docker compose logs -f analytics   # analytics service only
```

### Restart a Single Service

```bash
docker compose restart agent
```

### Service Ports

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:8000 | Main web interface + API |
| Collector | http://localhost:8001 | Raw telemetry collector |
| Analytics | http://localhost:8002 | Anomaly detection / prediction |
| Agent | http://localhost:8003 | Diagnosis + remediation |
| Grafana | http://localhost:3000 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics store |

---

## 5. The Dashboard

Open http://localhost:8000 in your browser.

### Main Sections

**Overview Panel**
- System Health Score (0-100 gauge)
- Risk Level badge (LOW / MEDIUM / HIGH / CRITICAL)
- Active anomaly count
- Last detection timestamp

**Telemetry Charts**
- Live time-series charts for CPU temperature, fan speeds, PSU power, memory error counts
- Automatic update every 5 seconds
- Anomaly markers shown as red dots on the timeline

**Anomaly List**
- Table of recent anomalies with sensor, value, score, and timestamp
- Click any row to trigger diagnosis for that anomaly

**Remediation Queue**
- Pending approval requests that need administrator action
- Approve/Reject buttons visible to admin role users

**Audit Log**
- Scrollable list of all system events in reverse-chronological order

### Login

Default credentials (change in `.env` before production):
```
Username: admin
Password: admin
```

---

## 6. Understanding the Telemetry Feed

The system collects the following sensor categories:

| Sensor Category | Examples | Normal Range |
|-----------------|----------|-------------|
| CPU Temperature | `cpu0_temp`, `cpu1_temp` | 40-85°C |
| Inlet Temperature | `inlet_temp` | 18-35°C |
| Fan Speed | `fan1_speed`, `fan2_speed` | 2000-6000 RPM |
| PSU Input Power | `psu0_input_watts` | 100-400W |
| PSU Voltage | `psu0_input_volts` | 200-240V |
| DIMM Errors | `dimm0_cecc_count` | 0-50/hr (correctable) |

**System Health Score** combines all sensors into one 0-100 value:

| Score | Status | Meaning |
|-------|--------|---------|
| 80-100 | Healthy | All sensors nominal |
| 60-79 | Warning | Minor anomalies present |
| 40-59 | Degraded | Investigation required |
| 0-39 | Critical | Immediate action required |

---

## 7. Anomaly Alerts

When the Isolation Forest model detects an anomaly, the system:

1. Records the anomaly with a score (0=normal, 1=strongly anomalous)
2. Updates the System Health Score
3. Highlights the reading on the dashboard chart
4. Triggers an automatic diagnosis (if health score < 60)

### Alert Severity

| Anomaly Score | Risk Level | Automatic Action |
|---------------|------------|-----------------|
| 0.3 - 0.5 | LOW | Log only |
| 0.5 - 0.7 | MEDIUM | Alert + operator notification |
| 0.7 - 0.85 | HIGH | Immediate diagnosis + recommendation |
| > 0.85 | CRITICAL | Autonomous remediation review |

---

## 8. Reading Diagnoses

Every diagnosis includes:

**Fault Type**
A structured identifier for the detected fault class:
- `CPU_OVERHEAT` — CPU temperature exceeding safe limits
- `CPU_THROTTLE` — CPU frequency reduction detected
- `FAN_FAILURE` — Fan RPM drop to near-zero
- `PSU_UNDERVOLT` — Power supply input voltage drop
- `PSU_EFFICIENCY_DROP` — PSU operating outside efficiency curve
- `DIMM_CECC_ESCALATION` — Correctable memory errors escalating
- `DIMM_UECC` — Uncorrectable memory error (critical)

**Root Cause**
A natural-language explanation grounded in the BMC knowledge base. This is generated by an LLM anchored to the relevant knowledge documents via RAG.

**Evidence**
The specific sensor readings that triggered the diagnosis, with actual values and thresholds.

**Recommended Actions**
Ordered list of remediation steps, from least to most invasive:
1. Monitoring/alerting actions (no system impact)
2. Tuning actions (e.g. increase fan speed)
3. Protective actions (e.g. reduce CPU frequency)
4. Failover actions (e.g. switch to redundant PSU)
5. Shutdown/isolation actions (last resort)

---

## 9. Managing Remediation Actions

### Autonomous Execution (No Human Required)

Actions with `requires_approval: false` in the policy are executed automatically when triggered. Examples:
- Increasing fan speed for CPU overheating
- Reducing CPU frequency during thermal stress

### Approval-Required Actions

High-risk actions appear in the **Remediation Queue** on the dashboard and require admin approval:

1. Navigate to the dashboard → **Remediation Queue**
2. Review the action details, fault context, and risk level
3. Click **Approve** or **Reject**
4. Optionally enter a comment
5. Approved actions execute within seconds

**Approval Timeout:** If not actioned within 15 minutes (configurable), the request is automatically rejected and the operator is alerted.

### After Execution

The system automatically:
- Measures health score improvement post-execution
- Triggers **automatic rollback** if health score worsens
- Writes a complete audit entry regardless of outcome

---

## 10. The Audit Log

The audit log records every system event with full context:

| Field | Description |
|-------|-------------|
| Timestamp | UTC time of event |
| Event Type | e.g. ANOMALY_DETECTED, DIAGNOSIS_GENERATED, ACTION_APPROVED, ACTION_EXECUTED, ROLLBACK_TRIGGERED |
| Actor | Human username or "system" for autonomous events |
| Action | The specific action taken |
| Pre-Health Score | Health score before the action |
| Post-Health Score | Health score after the action |
| Duration | How long execution took |
| Status | SUCCEEDED / FAILED / ROLLED_BACK |

Access the audit log:
- **Dashboard**: Audit Log tab
- **API**: `GET /audit` (requires `admin` role)
- **Database**: `audit_log` table in `telemetry.db` or PostgreSQL

---

## 11. Monitoring with Grafana

Grafana is available at http://localhost:3000 (default credentials: `admin/admin`).

### Pre-built Dashboards

**System Overview**
- System Health Score over time
- Anomaly count per hour
- Failure probability trends
- Active alert list

**Telemetry Metrics**
- Per-sensor time-series charts
- Min/max/mean overlays
- Anomaly event markers

**AI Performance**
- RAG inference latency histogram
- Diagnosis accuracy trend
- Remediation success rate
- Rollback frequency

**Service Health**
- HTTP request rate per service
- P50/P95/P99 latency per endpoint
- Error rate per endpoint

---

## 12. Connecting a Real BMC

### Configuration

Edit `.env`:
```env
BMC_HOST=192.168.1.100       # your BMC's IP address
BMC_USERNAME=root             # BMC admin username
BMC_PASSWORD=your_password    # BMC admin password
BMC_USE_SSL=true              # set false for self-signed certs in dev
```

### Verify Connectivity

```bash
curl -k -u root:password \
  https://192.168.1.100/redfish/v1/Chassis/1/Thermal
```

If you see JSON with `Temperatures` and `Fans` arrays, connectivity is working.

### Supported BMC Firmware

| Platform | Redfish Support |
|----------|----------------|
| OpenBMC | Full |
| Dell iDRAC 9 | Full |
| HP iLO 5 | Full |
| Lenovo XCC | Full |
| Supermicro IPMI | Partial (Redfish v1.1+) |
| AMI MegaRAC | Full |

---

## 13. Configuration Reference

### Environment Variables (`.env`)

```env
# BMC Connection
BMC_HOST=localhost            # BMC hostname or IP
BMC_PORT=8080                 # BMC port (8080 = mock, 443 = real)
BMC_USERNAME=admin            # BMC credentials
BMC_PASSWORD=admin
BMC_USE_SSL=false             # enable for real BMCs

# Database
DATABASE_URL=sqlite:///./telemetry/db/telemetry.db
# For PostgreSQL:
# DATABASE_URL=postgresql://user:password@postgres:5432/aiobmc

# Security
SECRET_KEY=change-this-in-production-to-a-random-64-char-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Telemetry Collection
COLLECTION_INTERVAL_SECONDS=30    # how often to poll BMC
ANOMALY_THRESHOLD=0.5             # minimum score to flag as anomaly

# Health Score Thresholds
HEALTH_WARN_THRESHOLD=60          # trigger diagnosis below this score
HEALTH_CRITICAL_THRESHOLD=40      # trigger autonomous review below this

# Remediation
APPROVAL_TIMEOUT_MINUTES=15       # auto-reject after this many minutes
ROLLBACK_HEALTH_DELTA=5           # rollback if health drops by this much

# LLM (for diagnosis generation)
OPENAI_API_KEY=sk-...             # or leave blank for local model
LLM_MODEL=gpt-4o-mini             # OpenAI model to use
LLM_BASE_URL=                     # set for local LLM (e.g. Ollama)

# Observability
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

---

## 14. Troubleshooting

### "No readings appearing in dashboard"

1. Check the collector logs: `docker compose logs collector`
2. Verify BMC connectivity: `curl http://localhost:8080/redfish/v1`
3. Check the mock BMC is running: `python mock_bmc.py`
4. Confirm the database file exists: `ls telemetry/db/`

### "Diagnosis returns empty result"

1. Rebuild the RAG index:
   ```bash
   python -c "from rag_engine import build_index; build_index(force=True)"
   ```
2. Check ChromaDB is populated: `ls chroma_db/`
3. Verify `knowledge/` directory contains `.txt` files

### "Remediation action stuck in PENDING"

1. Check the agent logs: `docker compose logs agent`
2. Verify policy allows the action for that fault type (`automation/policy_engine.py`)
3. Check if approval is required and approve it via the dashboard

### "JWT authentication failing"

1. Confirm `SECRET_KEY` matches across all services in `.env`
2. Tokens expire after `JWT_EXPIRE_MINUTES` — re-authenticate
3. Check system clock is synchronised (JWT uses timestamps)

### "High memory usage"

The sentence-transformer model (`all-MiniLM-L6-v2`) loads into memory once per process (~400 MB). This is expected. For low-memory environments, use a smaller model or enable swap.

---

## 15. FAQ

**Q: Can I use this without an OpenBMC device?**  
A: Yes. `mock_bmc.py` simulates a full Redfish-compatible BMC. You can develop and test the entire system without any physical hardware.

**Q: Does the system require internet access?**  
A: Only for LLM-based diagnosis generation (if using OpenAI). The anomaly detection, prediction, and RAG retrieval components are fully offline. Set `LLM_BASE_URL` to use a local Ollama server for fully air-gapped operation.

**Q: How do I add a new sensor type?**  
A: Add the Redfish endpoint path to `telemetry/collector.py`'s polling list, normalise the reading to the standard schema, and optionally add a knowledge base document for diagnosis context.

**Q: Is the audit log tamper-proof?**  
A: The audit log is append-only within the application. For production tamper-evidence, configure PostgreSQL row-level security or export audit entries to an immutable object store (S3, GCS) after each write.

**Q: What LLM providers are supported?**  
A: Any provider with an OpenAI-compatible API endpoint, including: OpenAI (GPT-4o, GPT-4o-mini), Anthropic (via proxy), Ollama (Llama 3, Mistral, Gemma), and vLLM self-hosted deployments.

**Q: How do I scale for multiple servers?**  
A: Deploy the full stack per rack, or configure a single Collector with multiple `BMC_HOST` entries. The Kubernetes manifests in `k8s/` support horizontal pod autoscaling for the Analytics and Agent services.
