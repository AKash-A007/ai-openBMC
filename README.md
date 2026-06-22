# 🖥️ AI OpsBMC

> **An AI-powered operations platform for OpenBMC** — combining RAG-based diagnosis, anomaly detection, failure prediction, and observability into one end-to-end system.
> Redfish telemetry · Semantic search · Qwen3-8B · Isolation Forest · FastAPI · Streamlit · SQLite

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector--db-orange)](https://www.trychroma.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn)](https://scikit-learn.org)
[![SQLite](https://img.shields.io/badge/SQLite-telemetry--store-003B57?logo=sqlite)](https://www.sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 What Is This?

AI OpsBMC is an intelligent diagnostics and observability platform built on top of [OpenBMC](https://github.com/openbmc/openbmc) — the open-source firmware stack used in server Baseboard Management Controllers (BMCs).

It connects to a real or emulated BMC via the **Redfish REST API**, retrieves hardware telemetry (memory health, CPU thermals, PSU status), and runs it through two complementary pipelines:

- **Phase A — Diagnosis Engine:** A RAG + LLM pipeline that generates structured root-cause analyses for individual hardware events — complete with severity, confidence, and actionable recommendations.
- **Phase B — Historical Intelligence:** A telemetry storage, anomaly detection, failure prediction, and observability layer that turns raw sensor readings into trend-aware health scores, alerts, and weekly reports.

```
OpenBMC (QEMU or real hardware)
          ↓  Redfish API
    Python Telemetry Client
          ↓
    ┌─────────────────┴─────────────────┐
    ▼                                   ▼
PHASE A: Diagnosis                PHASE B: Historical Intelligence
    │                                   │
Event Parser                      SQLite Telemetry Store
    ↓                                   ↓
RAG Engine (ChromaDB)             Isolation Forest (Anomaly Detection)
    ↓                                   ↓
Qwen3-8B (HuggingFace)            Rule-Based Predictor + Health Score
    ↓                                   ↓
FastAPI :8000                     Alerts + Reports
    ↓                                   ↓
Streamlit app.py :8501            Streamlit dashboard.py :8501
(trigger diagnoses)                (observe system health)
```

---

## 🎯 Project Status

| Phase | Week | Layer | Status |
|---|---|---|---|
| **A** | 1 | Data Collection — OpenBMC QEMU, Redfish client, mock SEL generator, event parser | ✅ |
| **A** | 2 | Knowledge & Retrieval — domain knowledge base, chunking, embeddings, ChromaDB | ✅ |
| **A** | 3 | AI Diagnosis Engine — Qwen3-8B, RAG-augmented prompting, structured JSON output | ✅ |
| **A** | 4 | Production Service — FastAPI backend, Streamlit dashboard, live QEMU integration | ✅ |
| **B** | 1 | Telemetry Storage — SQLite time-series store, parameterized queries, polling collector | ✅ |
| **B** | 2 | Anomaly Detection — Isolation Forest, unsupervised outlier scoring | ✅ |
| **B** | 3 | Failure Prediction — feature engineering, rule-based risk model, health scoring | ✅ |
| **B** | 4 | Observability & Alerting — metrics, alerts, weekly reports, Streamlit dashboard | ✅ |
| **C** | — | Real-Time AIOps — Prometheus, Grafana, Kafka, multi-server, agentic remediation | 🔭 Planned |

**Phases A and B are both complete.** This README documents the full system as it stands.

---

## 🏗️ Architecture

### Phase A — Diagnosis Pipeline

```
┌─────────────────────────────────────────────────────────┐
│               Streamlit Dashboard :8501 (app.py)          │
│                                                         │
│  [Select Scenario ▼]    Severity:    🔴 CRITICAL        │
│  [🔍 Run Diagnosis]     Confidence:  87%                │
│  [📡 Fetch from QEMU]   Root Cause:  DIMM degradation   │
│  🟢 BMC Online          Action:      Replace DIMM_B2    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend :8000 (main.py)          │
│                                                         │
│  GET  /health          POST /diagnose                   │
│  GET  /scenarios       POST /diagnose/scenario          │
│  POST /fetch           GET  /diagnose/live              │
│  GET  /results         DELETE /results                  │
└──────┬────────────────────────┬────────────────────────┘
       │                        │
       ▼                        ▼
┌─────────────┐    ┌────────────────────────────────────┐
│ QEMU :2443  │    │          Diagnosis Pipeline        │
│             │    │                                    │
│ Redfish API │    │  parser.py    → parse_log()        │
│ /Systems    │    │  rag_engine.py→ ChromaDB search    │
│ /Thermal    │    │               → cosine re-rank     │
│ /Power      │    │  agent.py     → Qwen3-8B prompt    │
└─────────────┘    │               → JSON diagnosis     │
                   └────────────────────────────────────┘
```

### Phase B — Historical Intelligence Pipeline

```
OpenBMC / mock telemetry
        │
        ▼
SQLite — telemetry table (telemetry/database.py)
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
  anomaly_detector.py  features.py       (raw history)
                        predictor.py
                        health_score.py
        │                  │
        └────────┬─────────┘
                  ▼
        ┌──────────────────────┐
        │   metrics.py           │  ← aggregation
        │   alerts.py             │  ← threshold + severity
        │   reports.py             │  ← summarisation + RCA history
        └──────────┬───────────────┘
                   ▼
        SQLite — diagnoses table (RCA history)
                   │
                   ▼
        dashboard.py (Streamlit observability UI)
        ┌─────────────────────────────┐
        │ System Health: 84/100        │
        │ Overall Risk:  MEDIUM         │
        │ Failure Rate:  33%             │
        │ [Sensor Trend Graph]            │
        │ Recent Alerts / Diagnoses        │
        └─────────────────────────────────┘
```

**Note:** `app.py` (Phase A, action-triggering) and `dashboard.py` (Phase B, read-only observability) are deliberately separate Streamlit apps — one is for *doing something*, the other is for *understanding what's happening*. This mirrors how real ops platforms separate a remediation console from a monitoring dashboard.

---

## 🗂️ Project Structure

```
ai-openBMC/
│
├── main.py                  # FastAPI REST backend — Phase A diagnosis API
├── app.py                   # Streamlit dashboard — Phase A (trigger diagnoses)
├── agent.py                 # RAG + LLM diagnosis pipeline
├── rag_engine.py             # Embeddings, ChromaDB, cosine retrieval
├── parser.py                  # Redfish JSON parser + event extractor
├── redfish_client.py           # Redfish API client (live QEMU fetch)
├── mock_bmc.py                  # Mock SEL event generator (offline dev)
│
├── knowledge/                    # Plain-text domain knowledge base
│   ├── dimm_failures.txt
│   ├── cpu_failures.txt
│   └── psu_failures.txt
│
├── telemetry/                     # Phase B — telemetry storage layer
│   ├── database.py                # ALL SQL lives here (telemetry + diagnoses tables)
│   ├── collector.py                # Polling collector — mock sensor readings
│   └── query.py                     # Read-friendly history/stats functions
│
├── analytics/                        # Phase B — anomaly detection & prediction
│   ├── anomaly_detector.py            # IsolationForest wrapper
│   ├── features.py                     # Raw values → summary statistics
│   ├── predictor.py                     # Rule-based failure probability
│   └── health_score.py                   # Probability → 0-100 health score
│
├── monitoring/                             # Phase B — observability & alerting
│   ├── metrics.py                          # Aggregate numbers (avg/max/health/rate)
│   ├── alerts.py                            # Rule-based alert engine
│   ├── reports.py                            # Weekly report + RCA trend detection
│   └── dashboard.py                           # Streamlit observability UI
│
├── redfish_data/        # Saved Redfish JSON snapshots (gitignored)
├── chroma_db/            # ChromaDB vector store (gitignored)
├── db/                     # SQLite telemetry.db (gitignored)
├── diagnosis_results.json    # Persistent diagnosis history (Phase A)
│
├── .env                  # HF_TOKEN (gitignored)
├── .gitignore
└── requirements.txt
```

---

## ⚡ Quick Start

### Prerequisites

- Python 3.12+
- QEMU (for live BMC emulation) — optional, mock scenarios/telemetry work fully offline
- HuggingFace account (free) for Qwen3-8B inference

### 1. Clone and set up environment

```bash
git clone https://github.com/<your-username>/ai-openBMC.git
cd ai-openBMC

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Set your HuggingFace token

```bash
# Get your free token from https://huggingface.co/settings/tokens
echo "HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx" > .env
```

### 3. Run Phase A — Diagnosis Engine

```bash
# Terminal 1 — FastAPI backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Streamlit diagnosis dashboard
streamlit run app.py
```

Open **http://localhost:8501** — select a scenario, click **Run Diagnosis**.

### 4. Run Phase B — Telemetry & Observability

```bash
# Terminal 3 — start the telemetry collector (polls every 5s)
cd telemetry
python3 collector.py

# Terminal 4 — observability dashboard
cd monitoring
streamlit run dashboard.py
```

Open the dashboard URL printed by Streamlit — health scores, trend graphs, alerts, and RCA history populate as the collector accumulates readings.

---

## 🔴 Live QEMU Mode (Optional)

To connect to a real emulated BMC instead of mock data:

```bash
qemu-system-arm \
  -machine romulus-bmc \
  -m 512 \
  -drive file=tmp/deploy/images/romulus/obmc-phosphor-image-romulus.static.mtd,if=mtd,format=raw \
  -serial mon:stdio \
  -serial null \
  -netdev user,id=net0,hostfwd=tcp::2443-:443 \
  -net nic,netdev=net0
```

Wait for the login prompt (~2-3 minutes), then use the **📡 Fetch from QEMU** button in the Phase A dashboard sidebar.

The dashboard detects BMC status automatically:
- 🟢 **BMC Online** — QEMU is running and reachable
- 🟡 **BMC Timeout** — QEMU is still booting
- 🔴 **No BMC Found** — QEMU is not running (fetch button disabled)

```bash
# Verify connectivity manually
curl -k -u root:0penBmc https://localhost:2443/redfish/v1/Systems/system
```

> Note: Romulus QEMU doesn't emulate every Redfish path — `Thermal`/`Power` may 404 depending on the build. `parser.py` handles missing endpoints gracefully.

---

## 🧠 How Phase A's Diagnosis Works

### 1. Event Parsing
Raw Redfish JSON or mock SEL events are normalised into a canonical schema:
```json
{"sensor": "DIMM_B2", "category": "MEMORY", "event_type": "ECC_ERROR", "severity": "WARNING"}
```

### 2. RAG Retrieval
The event is embedded using `all-MiniLM-L6-v2` and queried against ChromaDB. The top chunk is sentence-level cosine re-ranked **with a restatement penalty** — sentences that merely echo the query keywords (cosine score > 0.80) are penalised so genuinely diagnostic sentences win instead.

### 3. LLM Diagnosis
The retrieved sentence is injected into a structured prompt combining four prompting techniques — **role-based, RAG, structured-output, and instruction prompting** — sent to **Qwen3-8B** via the HuggingFace Inference API (`/no_think` mode, `temperature=0.1` for consistent JSON):

```
Role:        OpenBMC diagnostics expert
Event:       DIMM_B2 / MEMORY / ECC_ERROR / WARNING
Knowledge:   "Repeated ECC errors often indicate DIMM degradation."
Output:      JSON { root_cause, severity, confidence, recommendation }
```

### 4. Result
```json
{
  "root_cause": "Repeated ECC errors on DIMM_B2 indicate progressive memory degradation",
  "severity": "HIGH",
  "confidence": "87%",
  "recommendation": "Run memory diagnostics and schedule DIMM_B2 replacement",
  "requires_immediate_action": true,
  "sensor": "DIMM_B2",
  "event_type": "ECC_ERROR",
  "rag_context": "Repeated ECC errors often indicate DIMM degradation."
}
```

---

## 🔮 How Phase B's Historical Intelligence Works

### 1. Telemetry Storage (Week 1)
Every sensor reading is persisted to SQLite with a threshold-derived status:
```sql
CREATE TABLE telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, sensor TEXT, value REAL, status TEXT
);
```
All SQL lives in one file (`telemetry/database.py`) — connection management via context managers, every query parameterized (`?` placeholders) to eliminate SQL injection risk.

### 2. Anomaly Detection (Week 2)
An **Isolation Forest** (unsupervised — no labelled training data required) learns each sensor's normal range from its own history, and isolates outliers by how few random splits it takes to separate them from the rest of the data:
```
[70, 72, 71, 73, 74, 75, 150]  →  150 isolated in 1 split → ANOMALY (score=-0.27)
```

### 3. Failure Prediction + Health Scoring (Week 3)
A **rule-based predictor** (deliberately built before any ML model — no labelled failure data exists yet, and rule-based output is fully explainable) combines three signals into a failure probability:

```python
probability = threshold_breach (0-0.4) + anomaly_history (0-0.3) + trend (0-0.2)
```

That probability is then transformed into a human-friendly **0-100 health score** — the same units every enterprise tool (Dell OpenManage, HPE iLO, Datadog) already uses.

```json
{"sensor": "CPU_TEMP", "health_score": 65, "failure_probability": 0.52, "risk": "MEDIUM"}
```

### 4. Observability & Alerting (Week 4)
`alerts.py` applies thresholds to the existing health-score and anomaly outputs (never recomputing risk itself) to decide what deserves a human's attention:

```json
{"severity": "WARNING", "sensor": "CPU_TEMP", "message": "CPU_TEMP health score is 65/100 — warning condition."}
```

`reports.py` aggregates diagnosis history (persisted in a new `diagnoses` table) to surface recurring root causes — counted by root-cause **text**, not sensor name, since the same sensor can fail for genuinely different reasons.

---

## 🌐 API Reference (Phase A — FastAPI)

Full interactive docs at **http://localhost:8000/docs** (Swagger UI).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service status + RAG index info |
| `GET` | `/scenarios` | List all mock fault scenarios |
| `GET` | `/scenario/{name}` | Get raw event for a scenario |
| `POST` | `/diagnose` | Diagnose a raw event dict |
| `POST` | `/diagnose/scenario` | Diagnose by scenario name |
| `POST` | `/fetch` | Fetch live data from QEMU via Redfish |
| `GET` | `/diagnose/live` | Diagnose all real events from saved JSON |
| `GET` | `/results` | Fetch diagnosis history |
| `DELETE` | `/results` | Clear diagnosis history |

```bash
curl -X POST http://localhost:8000/diagnose/scenario \
     -H "Content-Type: application/json" \
     -d '{"name": "dimm_failure"}'
```

### Available mock scenarios

| Name | Sensor | Event |
|---|---|---|
| `dimm_failure` | DIMM_B2 | Memory ECC Error |
| `cpu_overheat` | CPU0 | CPU Over Temperature |
| `psu_failure` | PSU1 | Power Supply Failure |
| `fan_fault` | FAN_3 | Fan Fault |
| `voltage_fault` | VR_CPU0 | Voltage Fault |

---

## 🔧 Function Reference (Phase B)

### `telemetry/database.py`
```python
init_db()                                          # idempotent — creates telemetry + diagnoses tables
insert_reading(timestamp, sensor, value, status)
fetch_by_sensor(sensor, limit) -> list[Row]
insert_diagnosis(timestamp, sensor, root_cause, confidence)
fetch_recent_diagnoses(limit) -> list[Row]
count_rows() / count_diagnoses()
```

### `telemetry/query.py`
```python
get_sensor_history(sensor, limit) -> list[float]
get_sensor_history_full(sensor, limit) -> list[dict]
get_sensor_stats(sensor, limit) -> dict   # mean/min/max/trend
get_all_sensor_names() -> list[str]
```

### `analytics/anomaly_detector.py`
```python
train_model(sensor, limit, contamination) -> IsolationForest
detect_anomalies(sensor, limit) -> dict
get_anomaly_score(sensor, value, limit) -> dict   # real-time single-reading scoring
get_sensor_health(sensor, limit) -> dict
```

### `analytics/predictor.py` + `health_score.py`
```python
predict_failure(sensor, limit) -> dict            # threshold + anomaly + trend → probability
categorize_risk(probability) -> str               # LOW / MEDIUM / HIGH
calculate_health_score(sensor, limit) -> dict     # probability → 0-100 score
calculate_fleet_health(sensors, limit) -> dict     # worst-case risk labelling across sensors
```

### `monitoring/metrics.py` + `alerts.py` + `reports.py`
```python
get_system_metrics(limit) -> dict                  # one-call dashboard data source
check_all_alerts(limit) -> list[dict]               # sorted CRITICAL → WARNING → INFO
get_alert_summary(limit) -> dict
generate_weekly_report(...) -> dict                  # health + alerts + recurring RCA issues
```

---

## 🧰 Tech Stack & Rationale

| Component | Technology | Why |
|---|---|---|
| BMC firmware | OpenBMC | Open-source, industry standard |
| Telemetry API | Redfish (DMTF) | REST-based, JSON, modern standard over legacy IPMI |
| Embeddings | `all-MiniLM-L6-v2` | Fast, 384-dim, CPU-friendly, Apache 2.0 |
| Vector DB | ChromaDB | Local, persistent, zero cloud dependency |
| LLM | Qwen3-8B | Free (HuggingFace), native JSON, dual think/no_think mode |
| Backend | FastAPI + Uvicorn | Async (handles slow LLM calls without blocking), auto-docs, Pydantic validation |
| Frontend | Streamlit | Python-native UI, zero JS, fast to iterate |
| Telemetry DB | SQLite | Serverless, single-file, edge-device friendly, ACID-compliant |
| Anomaly detection | scikit-learn `IsolationForest` | Unsupervised — no labelled failure data required; same algorithm family used by Datadog/New Relic |
| Failure prediction | Rule-based (v1) | Fully explainable; becomes the baseline a future ML model must beat once labelled data exists |
| Secrets | python-dotenv | `.env` file, never committed |

---

## 📦 Installation

```bash
pip install -r requirements.txt
```

```txt
fastapi
uvicorn
streamlit
sentence-transformers
chromadb
huggingface-hub
requests
numpy
pandas
scikit-learn
urllib3
python-dotenv
pydantic
```

---

## 🐛 Notable Engineering Lessons From This Build

A few real bugs hit during development, documented here because the *reasoning* matters more than the fix:

**1. Score saturation in IsolationForest.** `decision_function()` plateaus for sufficiently extreme outliers — a reading of 160 and 500 can score identically. Fixed by combining the isolation score with a z-score-based distance-from-baseline specifically for severity *ranking* among anomalies, not just anomaly/normal classification.

**2. Relative path resolution across multi-folder imports.** `Path("./db")` resolves relative to the *caller's* working directory — importing `database.py` from a different folder than where it was first run silently created a second, empty database. Fixed by anchoring to `Path(__file__).resolve().parent.parent / "db"`.

**3. Schema-less database file.** `sqlite3.connect()` creates an empty `.db` file as a side effect of opening a connection — independent of whether `init_db()` ever ran to create tables. If a dashboard is opened before any collector has run, this produces a confusing `OperationalError: no such table`. Fixed by making every entry point call idempotent `init_db()` on startup, the same pattern already used by FastAPI's `lifespan` hook for the RAG index.

**4. Alert fatigue from stale anomalies.** An anomaly check that scans full history would re-fire forever on a single anomaly from hours ago. Fixed by only alerting when the *most recent* reading is the one flagged.

**5. The restatement problem in RAG retrieval.** Cosine similarity rewards sentences that merely repeat the query's keywords over sentences that are more semantically *useful*. Fixed with a restatement penalty — any sentence scoring above 0.80 similarity gets its score halved.

---

## 🗓️ Roadmap — Phase C: Real-Time AIOps

- [ ] Replace mock telemetry with live Redfish polling at scale (multi-server)
- [ ] Prometheus integration — export metrics in Prometheus exposition format
- [ ] Grafana dashboards alongside the Streamlit observability layer
- [ ] MQTT/Kafka streaming for telemetry ingestion instead of polling
- [ ] Agentic remediation workflows — closing the loop from "alert fired" to automated corrective action
- [ ] Semantic deduplication of recurring root causes (reusing Phase A's embedding infrastructure to merge near-duplicate diagnosis phrasings)
- [ ] Benchmark a supervised ML failure model against the rule-based baseline once labelled data accumulates
- [ ] WebSocket endpoint for real-time streaming diagnosis
- [ ] FastAPI API key authentication + Docker Compose deployment

---

## 🤝 Contributing

This project is an OpenBMC internship contribution structured across two phases:
- **Phase A** (diagnosis engine) — extend `knowledge/` with new hardware failure domains; each `.txt` file is auto-indexed on next startup.
- **Phase B** (historical intelligence) — extend `analytics/predictor.py`'s `SENSOR_RULES` for new sensor types, or add new alert rules in `monitoring/alerts.py`.

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🔗 References

- [OpenBMC Project](https://github.com/openbmc/openbmc)
- [Redfish API Specification — DMTF](https://www.dmtf.org/standards/redfish)
- [SentenceTransformers — all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [ChromaDB Documentation](https://docs.trychroma.com)
- [Qwen3-8B on HuggingFace](https://huggingface.co/Qwen/Qwen3-8B)
- [RAG — Lewis et al., 2020](https://arxiv.org/abs/2005.11401)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Streamlit Documentation](https://docs.streamlit.io)
- [scikit-learn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)
- [Liu, Ting, Zhou — "Isolation Forest" (2008)](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf)
- [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [Dell OpenManage / HPE iLO — health scoring reference](https://www.dell.com/support/manuals/en-us/openmanage-enterprise)
- [Datadog — Anomaly Detection Monitors](https://docs.datadoghq.com/monitors/types/anomaly/)

---

*Built by Akash A · OpenBMC Internship Project · Amritapuri, Kerala*