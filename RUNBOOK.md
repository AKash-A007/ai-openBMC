# 🚀 AI OpsBMC — Complete Runbook (A to Z)

> **Everything you need** to set up, run, and debug every component — no mocks, all variables initialized, every step separated.

---

## 📑 Table of Contents

1. [Project Architecture](#1-project-architecture)
2. [Prerequisites](#2-prerequisites)
3. [Environment Setup](#3-environment-setup)
4. [Create the `.env` File](#4-create-the-env-file-all-variables)
5. [Install Dependencies](#5-install-dependencies)
6. [Step-by-Step: Run Each Component](#6-step-by-step-run-each-component)
   - [6A — RAG Index (ChromaDB)](#6a--rag-index-chromadb)
   - [6B — FastAPI Backend (`main.py`)](#6b--fastapi-backend-mainpy)
   - [6C — Streamlit Dashboard (`app.py`)](#6c--streamlit-dashboard-apppy)
   - [6D — Agent / LLM Diagnosis Standalone](#6d--agent--llm-diagnosis-standalone)
   - [6E — Parser Standalone](#6e--parser-standalone)
   - [6F — Redfish Client (Live QEMU)](#6f--redfish-client-live-qemu)
   - [6G — Policy Engine Standalone](#6g--policy-engine-standalone)
   - [6H — Execution Engine Standalone](#6h--execution-engine-standalone)
   - [6I — Telemetry Collector](#6i--telemetry-collector)
   - [6J — Monitoring (Prometheus + Grafana)](#6j--monitoring-prometheus--grafana)
   - [6K — Full Docker Stack](#6k--full-docker-stack)
7. [Running Tests](#7-running-tests)
8. [API Endpoints — Full Reference](#8-api-endpoints--full-reference)
9. [Testing Every API Endpoint (curl)](#9-testing-every-api-endpoint-curl)
10. [Debugging Guide](#10-debugging-guide)
11. [Common Errors and Fixes](#11-common-errors-and-fixes)
12. [File Map](#12-file-map)

---

## 1. Project Architecture

```
User Request
    │
    ▼
[Streamlit Dashboard: app.py :8501]
    │  HTTP REST calls
    ▼
[FastAPI Backend: main.py :8000]
    │
    ├──► [RAG Engine: rag_engine.py]  ← ChromaDB + sentence-transformers
    │         └─ knowledge/*.txt
    │
    ├──► [Agent: agent.py]  ← HuggingFace Inference API (Qwen3-8B)
    │         └─ Uses RAG context + LLM for root-cause diagnosis
    │
    ├──► [Parser: parser.py]  ← Reads redfish_data/*.json
    │
    └──► [Automation Pipeline]
              ├─ policy_engine.py    → AUTO or MANUAL?
              ├─ approval_manager.py → Human approval queue
              ├─ execution_engine.py → Executes actions
              ├─ action_executor.py  → Actual action functions
              ├─ rollback_manager.py → Rollback on failure
              └─ audit_logger.py    → Full audit trail
```

**Data flow for a diagnosis:**

```
Event (sensor + fault)
  → parser.py       (parse_log)
  → rag_engine.py   (rag_query → retrieve relevant KB chunk)
  → agent.py        (build_prompt → LLM call → JSON response)
  → main.py         (persist to diagnosis_results.json)
  → app.py          (display in Streamlit)
```

---

## 2. Prerequisites

| Tool | Min Version | Check Command |
|------|-------------|---------------|
| Python | 3.11+ | `python --version` |
| pip | latest | `pip --version` |
| Git | any | `git --version` |
| Docker Desktop | latest (optional) | `docker --version` |
| HuggingFace account | — | https://hf.co/settings/tokens |

> **Windows note:** All commands below are for **PowerShell**. Run as a regular user (not Admin unless noted).

---

## 3. Environment Setup

### 3.1 — Navigate to project root

```powershell
cd "C:\Users\Akash A\OneDrive\Desktop\ai-openBMC"
```

### 3.2 — Create and activate virtual environment

```powershell
# Create venv (only do this ONCE)
python -m venv venv

# Activate it EVERY TIME you open a new terminal
.\venv\Scripts\Activate.ps1
```

> If you get a scripts execution error, run this once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3.3 — Verify you are in the venv

```powershell
# You should see (venv) in your prompt
python -c "import sys; print(sys.prefix)"
# Expected output: ...ai-openBMC\venv
```

---

## 4. Create the `.env` File (All Variables)

```powershell
# Copy the template
Copy-Item .env.example .env
```

Now open `.env` and set **every** variable below:

```dotenv
# ─── BMC Connection ────────────────────────────────────────────────────────────
# For scenario/mock mode (no QEMU): leave as-is below
BMC_HOST=localhost
BMC_PORT=8080
BMC_USERNAME=admin
BMC_PASSWORD=admin
BMC_USE_SSL=false

# For live QEMU OpenBMC (port-forwarded to 2443):
# BMC_HOST=localhost
# BMC_PORT=2443
# BMC_USERNAME=root
# BMC_PASSWORD=0penBmc
# BMC_USE_SSL=true

# ─── Database ──────────────────────────────────────────────────────────────────
# SQLite (development — no server needed, recommended for local)
DATABASE_URL=sqlite:///./telemetry/db/telemetry.db

# PostgreSQL (production) — uncomment if using Docker stack:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/telemetry

# ─── Security ──────────────────────────────────────────────────────────────────
# Generate your own with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-this-to-a-random-64-character-string-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# ─── Telemetry Collection ──────────────────────────────────────────────────────
COLLECTION_INTERVAL_SECONDS=30
ANOMALY_THRESHOLD=0.5

# ─── Health Score Thresholds ───────────────────────────────────────────────────
HEALTH_WARN_THRESHOLD=60
HEALTH_CRITICAL_THRESHOLD=40

# ─── Remediation ───────────────────────────────────────────────────────────────
APPROVAL_TIMEOUT_MINUTES=15
ROLLBACK_HEALTH_DELTA=5

# ─── LLM — REQUIRED for agent.py to work ──────────────────────────────────────
# Get your FREE token at: https://huggingface.co/settings/tokens
# Create token → Type: Read → Copy the hf_xxxx string
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ─── Observability ─────────────────────────────────────────────────────────────
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_ADMIN_PASSWORD=admin

# ─── Service Ports ─────────────────────────────────────────────────────────────
DASHBOARD_PORT=8000
COLLECTOR_PORT=8001
ANALYTICS_PORT=8002
AGENT_PORT=8003

# ─── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
# LOG_LEVEL=DEBUG    # uncomment for verbose output
```

> **Critical:** `HF_TOKEN` is **mandatory**. Without it, `agent.py` crashes with `KeyError: 'HF_TOKEN'`.

### How to get your HuggingFace token (free, 2 minutes):

1. Go to https://huggingface.co/settings/tokens
2. Click **New token** → Name: `ai-openbmc` → Type: **Read**
3. Copy the token (starts with `hf_`)
4. Paste it into `.env` as `HF_TOKEN=hf_...`

---

## 5. Install Dependencies

```powershell
# Make sure venv is ACTIVE first (see step 3.2)
pip install -r requirements.txt
```

> ⚠️ First install takes **5–15 minutes** (PyTorch, sentence-transformers, ChromaDB, etc.)

### Verify key packages installed correctly:

```powershell
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import streamlit; print('Streamlit:', streamlit.__version__)"
python -c "import chromadb; print('ChromaDB:', chromadb.__version__)"
python -c "from sentence_transformers import SentenceTransformer; print('SentenceTransformers: OK')"
python -c "from huggingface_hub import InferenceClient; print('HuggingFace Hub: OK')"
python -c "from dotenv import load_dotenv; print('python-dotenv: OK')"
```

---

## 6. Step-by-Step: Run Each Component

---

### 6A — RAG Index (ChromaDB)

**What it does:** Reads `knowledge/*.txt`, chunks text, embeds with `all-MiniLM-L6-v2`, stores in `./chroma_db/`.

**Run once** (or after editing knowledge files):

```powershell
python rag_engine.py
```

**Expected output:**
```
Batches: 100%|██████████| 1/1 [00:00<00:00]
[RAG] Indexed 3 chunks from knowledge
```

**Verify index has data:**
```powershell
python -c "
from rag_engine import _get_collection
c = _get_collection()
print('Chunks in index:', c.count())
# Must be > 0
"
```

**Force-rebuild** (after editing `.txt` files):
```powershell
python -c "from rag_engine import build_index; build_index(force=True)"
```

**Test a query:**
```powershell
python -c "
from rag_engine import build_index, rag_query
build_index()
print(rag_query('Memory ECC error'))
"
```

---

### 6B — FastAPI Backend (`main.py`)

**What it does:** REST API on port 8000. Builds RAG index on startup. Exposes all diagnosis, remediation, approval, audit, and incident endpoints.

**Open Terminal 1 and run:**
```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected startup output:**
```
INFO:     Started server process [xxxx]
[Main] Starting AI OpsBMC Autonomous Operations service...
[RAG] Index already contains N chunks.
[Main] RAG index ready.
[Main] Automation pipeline ready (Policy → Approve → Execute → Audit).
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Verify in a new terminal:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

**Swagger UI (interactive):** http://localhost:8000/docs

---

### 6C — Streamlit Dashboard (`app.py`)

> ⚠️ **Start FastAPI backend (6B) FIRST.**

**Open Terminal 2 and run:**
```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

**Expected output:**
```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

**Open:** http://localhost:8501

**What you'll see and how to use it:**

| UI Element | What to Do |
|------------|------------|
| Scenario dropdown (left) | Pick a fault: DIMM, CPU, PSU, Fan, Voltage |
| **🔍 Run Diagnosis** | Sends to FastAPI → RAG + LLM → shows results |
| **🔧 Auto-Remediate** | Diagnosis + routes through policy engine |
| Pending Approvals panel | ✅ Approve or ❌ Reject MANUAL actions |
| Audit Log panel | See every action the system took |
| Incident Timeline | Full lifecycle view |
| Sidebar: 📡 Fetch from QEMU | Only active when QEMU/BMC is running |

---

### 6D — Agent / LLM Diagnosis Standalone

**Pre-condition:** `HF_TOKEN` must be in `.env`

```powershell
python agent.py
```

**Expected output:**
```json
{
  "root_cause": "DIMM_B2 is experiencing repeated ECC errors indicating memory degradation.",
  "severity": "HIGH",
  "confidence": "85%",
  "recommendation": "Isolate Memory Bank",
  "requires_immediate_action": true,
  "sensor": "DIMM_B2",
  "event_type": "ECC_ERROR",
  "rag_context": "Repeated ECC errors often indicate DIMM degradation..."
}
```

**Test a specific event:**
```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from rag_engine import build_index
from agent import diagnose
import json

build_index()

# Change event here to test different scenarios
result = diagnose({
    'sensor': 'CPU0',
    'event': 'CPU Over Temperature',
    'severity': 'CRITICAL'
})
print(json.dumps(result, indent=2))
"
```

---

### 6E — Parser Standalone

**What it does:** Maps raw event strings to structured categories for the LLM.

**Test all 5 event patterns:**
```powershell
python -c "
from parser import parse_log

events = [
    {'sensor': 'DIMM_B2',  'event': 'Memory ECC Error',      'severity': 'WARNING'},
    {'sensor': 'CPU0',     'event': 'CPU Over Temperature',   'severity': 'CRITICAL'},
    {'sensor': 'PSU1',     'event': 'Power Supply Failure',   'severity': 'CRITICAL'},
    {'sensor': 'FAN_3',    'event': 'Fan Fault',              'severity': 'WARNING'},
    {'sensor': 'VR_CPU0',  'event': 'Voltage Fault',          'severity': 'CRITICAL'},
]
for e in events:
    result = parse_log(e)
    print(f'{e[\"sensor\"]:12} → {result}')
"
```

**Expected:**
```
DIMM_B2      → {'sensor': 'DIMM_B2', 'category': 'MEMORY', 'event_type': 'ECC_ERROR', 'severity': 'WARNING'}
CPU0         → {'sensor': 'CPU0', 'category': 'CPU', 'event_type': 'OVERHEAT', 'severity': 'CRITICAL'}
PSU1         → {'sensor': 'PSU1', 'category': 'PSU', 'event_type': 'FAILURE', 'severity': 'CRITICAL'}
FAN_3        → {'sensor': 'FAN_3', 'category': 'COOLING', 'event_type': 'FAN_FAULT', 'severity': 'WARNING'}
VR_CPU0      → {'sensor': 'VR_CPU0', 'category': 'POWER', 'event_type': 'VOLTAGE_FAULT', 'severity': 'CRITICAL'}
```

**Parse saved Redfish files** (needs `./redfish_data/`):
```powershell
python -c "
from parser import extract_all_events
events = extract_all_events()
print(f'Found {len(events)} events')
for e in events: print(' -', e)
"
```

---

### 6F — Redfish Client (Live QEMU)

> ⚠️ Requires QEMU running OpenBMC on port 2443. Skip if using scenario mode.

**Check if QEMU BMC is reachable:**
```powershell
python -c "
import requests, urllib3
urllib3.disable_warnings()
try:
    r = requests.get('https://localhost:2443/redfish/v1', auth=('root','0penBmc'), verify=False, timeout=3)
    print('BMC status code:', r.status_code)
    if r.status_code == 200: print('QEMU is running!')
except Exception as e:
    print('QEMU NOT running:', type(e).__name__)
"
```

**Fetch all Redfish endpoints:**
```powershell
python redfish_client.py
```

**Expected (QEMU running):**
```
[Redfish] Fetching all endpoints...
  GET /redfish/v1  →  200
  GET /redfish/v1/Systems/system  →  200
  ...
  Saved → redfish_data\system.json
[Redfish] Done.
```

**View what was fetched:**
```powershell
ls .\redfish_data\
python -c "
import json
d = json.load(open('redfish_data/system.json'))
print('System health:', d.get('Status', {}))
"
```

---

### 6G — Policy Engine Standalone

**What it does:** Decides AUTO (execute now) or MANUAL (wait for approval).

```powershell
python automation/policy_engine.py
```

**Expected output:**
```
AUTO actions (safe to execute immediately):
  ✅ Increase Fan Speed
  ✅ Reduce Fan Speed
  ✅ Restart Service
  ✅ Reduce CPU Frequency
  ✅ Enable CPU Throttling
  ✅ Check PSU Voltage

MANUAL actions (require human approval):
  🔒 Isolate Memory Bank
  🔒 Power Cycle Node
  🔒 Shutdown System
  🔒 Emergency Shutdown
  🔒 Switch to Redundant PSU
```

**Check any action:**
```powershell
python -c "
from automation.policy_engine import evaluate_policy
for action in ['Increase Fan Speed', 'Shutdown System', 'Isolate Memory Bank', 'Unknown Action']:
    print(f'{action:35} → {evaluate_policy(action).value}')
"
```

---

### 6H — Execution Engine Standalone

**What it does:** Executes an approved action, handles rollback on failure, writes to audit log.

```powershell
python automation/execution_engine.py
```

**Expected output:**
```
ExecutionEngine — self-test
Supported actions: ['Increase Fan Speed', ...]

[ExecutionEngine] Starting: 'Increase Fan Speed' | issue=CPU_OVERHEAT | by=auto
Result status : SUCCESS
Audit row id  : 1
Details       : Fan speed increased to 80% on CPU0
```

**Run a custom action:**
```powershell
python -c "
from automation.execution_engine import ExecutionEngine
import json

engine = ExecutionEngine()
result = engine.execute(
    action='Increase Fan Speed',
    issue='CPU_OVERHEAT',
    sensor='CPU0',
    severity='CRITICAL',
    policy='AUTO',
    executed_by='test-user'
)
print(json.dumps(result, indent=2, default=str))
"
```

---

### 6I — Telemetry Collector

**Initialize the SQLite database first:**
```powershell
python -c "
import os
os.environ.setdefault('DB_TYPE', 'sqlite')
os.environ.setdefault('DB_PATH', 'telemetry/db/telemetry.db')
from telemetry.database import init_db
init_db()
print('Database initialized OK')
"
```

**Run the collector:**
```powershell
python -c "
import os
os.environ['DB_TYPE'] = 'sqlite'
os.environ['DB_PATH'] = 'telemetry/db/telemetry.db'
from telemetry.collector import main
main()
"
```

---

### 6J — Monitoring (Prometheus + Grafana)

> Requires Docker Desktop running.

```powershell
# Start only monitoring (no build needed)
docker compose up prometheus grafana -d

# View logs
docker compose logs -f prometheus
docker compose logs -f grafana
```

| Service | URL | Login |
|---------|-----|-------|
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin / admin |

---

### 6K — Full Docker Stack

```powershell
# Build and start all services
docker compose up --build -d

# Monitor all logs
docker compose logs -f

# Individual service logs
docker compose logs -f agent-service
docker compose logs -f dashboard-service
docker compose logs -f collector-service

# Stop everything (keep data)
docker compose down

# Stop and wipe all data
docker compose down -v
```

| Service | URL |
|---------|-----|
| FastAPI backend | http://localhost:8000 |
| Streamlit dashboard | http://localhost:8501 |
| Analytics API | http://localhost:8001 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

---

## 7. Running Tests

> Always run from the project root with venv active.

### 7A — Policy Engine Tests (no dependencies, instant)

```powershell
python -m pytest tests/test_policy_engine.py -v
```

Expected: `1 passed`

---

### 7B — Approval Manager Tests

```powershell
python -m pytest tests/test_approval_manager.py -v
```

---

### 7C — Database Tests (uses SQLite automatically)

```powershell
python -m pytest tests/test_database.py -v
```

---

### 7D — API Tests

```powershell
python -m pytest tests/test_api.py -v
```

---

### 7E — Full Suite with Coverage Report

```powershell
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

**Run only the fast tests** (skip LLM-dependent tests):
```powershell
python -m pytest tests/test_policy_engine.py tests/test_approval_manager.py tests/test_database.py -v
```

---

## 8. API Endpoints — Full Reference

Base URL: `http://localhost:8000`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status + RAG chunk count |
| GET | `/scenarios` | List all 5 fault scenarios |
| GET | `/scenario/{name}` | Get one scenario's event dict |
| POST | `/diagnose` | Diagnose a raw event input |
| POST | `/diagnose/scenario` | Diagnose by scenario name |
| GET | `/diagnose/live` | Diagnose parsed Redfish files |
| GET | `/results?limit=N` | Last N diagnosis results |
| DELETE | `/results` | Clear diagnosis history |
| POST | `/fetch` | Fetch live data from QEMU BMC |
| POST | `/remediate` | Route action through policy engine |
| GET | `/approvals` | List all approval requests |
| GET | `/approvals?pending_only=true` | Pending only |
| POST | `/approvals/{id}/approve` | Approve and execute |
| POST | `/approvals/{id}/reject` | Reject action |
| GET | `/audit?limit=N` | Audit log entries |
| GET | `/incidents?limit=N` | Incident timeline |

**Available scenario names:** `dimm_failure`, `cpu_overheat`, `psu_failure`, `fan_fault`, `voltage_fault`

---

## 9. Testing Every API Endpoint (curl)

> All commands use PowerShell `Invoke-RestMethod`. Backend must be running on port 8000.

### Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

### List Scenarios
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/scenarios"
```

### Get a Specific Scenario
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/scenario/dimm_failure"
Invoke-RestMethod -Uri "http://localhost:8000/scenario/cpu_overheat"
Invoke-RestMethod -Uri "http://localhost:8000/scenario/psu_failure"
Invoke-RestMethod -Uri "http://localhost:8000/scenario/fan_fault"
Invoke-RestMethod -Uri "http://localhost:8000/scenario/voltage_fault"
```

### Diagnose a Raw Event
```powershell
$body = @{sensor="DIMM_B2"; event="Memory ECC Error"; severity="WARNING"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/diagnose" -Method Post -Body $body -ContentType "application/json"
```

### Diagnose by Scenario Name
```powershell
$body = @{name="dimm_failure"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/diagnose/scenario" -Method Post -Body $body -ContentType "application/json"
```

### Get Diagnosis History
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/results?limit=5"
```

### Clear History
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/results" -Method Delete
```

### Remediate (AUTO action — executes immediately)
```powershell
$body = @{
    issue       = "CPU_OVERHEAT"
    action      = "Increase Fan Speed"
    sensor      = "CPU0"
    severity    = "CRITICAL"
    executed_by = "ops-engineer"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/remediate" -Method Post -Body $body -ContentType "application/json"
```

### Remediate (MANUAL action — creates approval request)
```powershell
$body = @{
    issue       = "DIMM_FAILURE"
    action      = "Isolate Memory Bank"
    sensor      = "DIMM_B2"
    severity    = "WARNING"
    executed_by = "ops-engineer"
} | ConvertTo-Json
$response = Invoke-RestMethod -Uri "http://localhost:8000/remediate" -Method Post -Body $body -ContentType "application/json"
# Save the approval_id:
$approvalId = $response.approval_id
Write-Host "Approval ID: $approvalId"
```

### List Pending Approvals
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/approvals?pending_only=true"
```

### Approve an Action
```powershell
# Paste your approval_id from the remediate response above
$approvalId = "paste-uuid-here"
$body = @{resolved_by="ops-engineer"; notes="Reviewed and approved"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/approvals/$approvalId/approve" -Method Post -Body $body -ContentType "application/json"
```

### Reject an Action
```powershell
$approvalId = "paste-uuid-here"
$body = @{resolved_by="ops-engineer"; notes="Too risky right now"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/approvals/$approvalId/reject" -Method Post -Body $body -ContentType "application/json"
```

### Get Audit Log
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/audit?limit=10"
```

### Get Incident Timeline
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/incidents?limit=5"
```

### Fetch Live QEMU Data (only when QEMU is running)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/fetch" -Method Post
```

### Diagnose Live QEMU Events (run fetch first)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/diagnose/live"
```

---

## 10. Debugging Guide

### Debug 1 — Test HuggingFace token

```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
token = os.environ.get('HF_TOKEN', 'NOT SET')
print('HF_TOKEN set:', token != 'NOT SET')
print('Token preview:', token[:10] + '...' if token != 'NOT SET' else 'MISSING - add to .env')

from huggingface_hub import InferenceClient
client = InferenceClient(provider='auto', api_key=token)
resp = client.chat.completions.create(
    model='Qwen/Qwen3-8B',
    messages=[{'role':'user','content':'Reply with the word OK only.'}],
    max_tokens=10
)
print('LLM test response:', resp.choices[0].message.content.strip())
"
```

---

### Debug 2 — Test RAG pipeline

```powershell
python -c "
from rag_engine import build_index, rag_query, _get_collection

col = _get_collection()
print('Step 1 — Chunks in index:', col.count())

if col.count() == 0:
    print('Building index...')
    build_index()

queries = [
    'Memory ECC error DIMM',
    'CPU temperature overheat',
    'power supply failure PSU',
    'fan fault cooling',
    'voltage fault VR',
]
print()
print('Step 2 — Query results:')
for q in queries:
    result = rag_query(q)
    print(f'  Q: {q[:35]:35} -> {result[:70]}')
"
```

---

### Debug 3 — Test full diagnosis pipeline (all 5 scenarios)

```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

from rag_engine import build_index
from agent import diagnose
import json

build_index()

events = [
    {'sensor':'DIMM_B2',  'event':'Memory ECC Error',      'severity':'WARNING'},
    {'sensor':'CPU0',     'event':'CPU Over Temperature',   'severity':'CRITICAL'},
    {'sensor':'PSU1',     'event':'Power Supply Failure',   'severity':'CRITICAL'},
    {'sensor':'FAN_3',    'event':'Fan Fault',              'severity':'WARNING'},
    {'sensor':'VR_CPU0',  'event':'Voltage Fault',          'severity':'CRITICAL'},
]

for ev in events:
    print(f'--- {ev[\"sensor\"]} ---')
    result = diagnose(ev)
    if 'error' in result:
        print('  ERROR:', result['error'])
    else:
        print('  Root cause    :', result['root_cause'])
        print('  Recommendation:', result['recommendation'])
        print('  Confidence    :', result['confidence'])
    print()
"
```

---

### Debug 4 — Test automation pipeline

```powershell
python -c "
from automation.policy_engine import evaluate_policy
from automation.approval_manager import ApprovalManager
from automation.execution_engine import ExecutionEngine
import json

mgr = ApprovalManager()
eng = ExecutionEngine()

print('=== AUTO action test ===')
action = 'Increase Fan Speed'
policy = evaluate_policy(action)
print(f'Policy for [{action}]: {policy.value}')
result = eng.execute(action=action, issue='CPU_OVERHEAT',
    sensor='CPU0', severity='CRITICAL', policy='AUTO', executed_by='debug')
print('Status:', result['status'])
print('Details:', result['details'])

print()
print('=== MANUAL action test ===')
action2 = 'Isolate Memory Bank'
policy2 = evaluate_policy(action2)
print(f'Policy for [{action2}]: {policy2.value}')
approval = mgr.request_approval(issue='DIMM_FAILURE', action=action2,
    sensor='DIMM_B2', severity='WARNING', policy='MANUAL')
print('Approval ID created:', approval.id)
print('Pending count:', len(mgr.list_pending()))
"
```

---

### Debug 5 — Check all required paths exist

```powershell
python -c "
from pathlib import Path

paths = {
    'knowledge/ dir'           : Path('./knowledge'),
    'chroma_db/ dir'           : Path('./chroma_db'),
    'redfish_data/ dir'        : Path('./redfish_data'),
    'telemetry/db/ dir'        : Path('./telemetry/db'),
    'diagnosis_results.json'   : Path('./diagnosis_results.json'),
    'incidents.json'           : Path('./incidents.json'),
    '.env file'                : Path('./.env'),
    'automation/__init__.py'   : Path('./automation/__init__.py'),
}
all_ok = True
for name, p in paths.items():
    status = '✅' if p.exists() else '❌ MISSING'
    if not p.exists(): all_ok = False
    print(f'{name:35} {status}')
print()
print('All paths OK:' if all_ok else 'Some paths are missing — see above')
"
```

---

### Debug 6 — Create all missing directories

```powershell
python -c "
from pathlib import Path
dirs = ['./knowledge', './redfish_data', './telemetry/db', './chroma_db']
for d in dirs:
    Path(d).mkdir(parents=True, exist_ok=True)
    print('OK:', d)
"
```

---

## 11. Common Errors and Fixes

### ❌ `KeyError: 'HF_TOKEN'`

```
KeyError: 'HF_TOKEN'
```

**Fix:**
```powershell
# Check the key exists in .env
Select-String "HF_TOKEN" .env

# Add it if missing:
Add-Content .env "HF_TOKEN=hf_yourRealTokenHere"
```

---

### ❌ `RuntimeError: Index is empty. Run build_index() first.`

**Fix:**
```powershell
python -c "from rag_engine import build_index; build_index(force=True)"
```

---

### ❌ `ValueError: No .txt files found in knowledge`

**Fix:**
```powershell
ls .\knowledge\
# Should show: cpu_failures.txt, dimm_failure.txt, psu_failures.txt
# If missing, check git status:
git status knowledge/
git checkout knowledge/
```

---

### ❌ `ConnectionError: Cannot reach OpenBMC`

**This is expected** when QEMU is not running. Use scenario mode in Streamlit instead (dropdown + Run Diagnosis).

---

### ❌ `No module named 'automation'`

**Fix:** Always run from the project root:
```powershell
cd "C:\Users\Akash A\OneDrive\Desktop\ai-openBMC"
```

---

### ❌ `Address already in use` on port 8000

```powershell
# Find PID using port 8000
netstat -ano | findstr :8000
# Kill it (replace XXXX with the PID from last column)
taskkill /PID XXXX /F
```

---

### ❌ Streamlit shows "❌ Backend offline"

FastAPI is not running. Start it first:
```powershell
# Terminal 1:
python -m uvicorn main:app --port 8000 --reload
# Wait for "Application startup complete" then open Terminal 2:
streamlit run app.py
```

---

### ❌ `json.JSONDecodeError` from LLM response

```powershell
# Debug raw LLM output:
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from huggingface_hub import InferenceClient
client = InferenceClient(provider='auto', api_key=os.environ['HF_TOKEN'])
resp = client.chat.completions.create(
    model='Qwen/Qwen3-8B',
    messages=[
        {'role':'system','content':'Respond with JSON only. /no_think'},
        {'role':'user','content':'Return {\"status\": \"ok\"}'}
    ],
    max_tokens=50, temperature=0.1
)
print('Raw output:', repr(resp.choices[0].message.content))
"
```

---

### ❌ `uvloop` warning on Windows

`uvloop` does not support Windows. This is harmless — uvicorn falls back to asyncio automatically.

---

## 12. File Map

```
ai-openBMC/
│
├── .env                          ← YOUR config (copy from .env.example, fill HF_TOKEN)
├── .env.example                  ← Template with all variable names
│
├── main.py                       ← FastAPI backend (uvicorn main:app)
├── app.py                        ← Streamlit dashboard (streamlit run app.py)
├── agent.py                      ← LLM diagnosis (HuggingFace Qwen3-8B)
├── rag_engine.py                 ← ChromaDB + sentence-transformers RAG
├── parser.py                     ← Event string → structured category parser
├── redfish_client.py             ← Live OpenBMC Redfish HTTP client
├── mock_bmc.py                   ← Legacy mock BMC (not used in current pipeline)
│
├── knowledge/                    ← Knowledge base for RAG
│   ├── cpu_failures.txt          ← CPU fault knowledge
│   ├── dimm_failure.txt          ← Memory ECC fault knowledge
│   └── psu_failures.txt          ← PSU fault knowledge
│
├── automation/                   ← Full autonomous operations pipeline
│   ├── __init__.py
│   ├── policy_engine.py          ← AUTO vs MANUAL decision table
│   ├── approval_manager.py       ← Human approval queue + state machine
│   ├── execution_engine.py       ← Action router (runs executor + audit)
│   ├── action_executor.py        ← Individual remediation functions
│   ├── rollback_manager.py       ← Rollback logic on action failure
│   └── audit_logger.py           ← In-memory audit trail
│
├── telemetry/                    ← Sensor metrics persistence
│   ├── collector.py              ← Polling loop
│   ├── database.py               ← SQLite / PostgreSQL ORM
│   └── query.py                  ← Analytics query helpers
│
├── monitoring/
│   ├── prometheus/               ← Prometheus config (prometheus.yml)
│   └── grafana/                  ← Grafana dashboards + provisioning
│
├── tests/                        ← Pytest test suite
│   ├── conftest.py               ← Shared fixtures (auto SQLite test DB)
│   ├── test_policy_engine.py     ← AUTO/MANUAL policy unit tests
│   ├── test_approval_manager.py  ← Approval workflow tests
│   ├── test_database.py          ← DB init + CRUD tests
│   └── test_api.py               ← FastAPI endpoint tests
│
├── services/                     ← Docker microservice Dockerfiles
│   ├── agent/
│   ├── analytics/
│   ├── collector/
│   └── dashboard/
│
├── chroma_db/                    ← AUTO-CREATED: vector store
├── redfish_data/                 ← AUTO-CREATED: Redfish JSON files
├── diagnosis_results.json        ← AUTO-CREATED: diagnosis history
├── incidents.json                ← AUTO-CREATED: incident records
│
├── requirements.txt              ← All Python dependencies
├── docker-compose.yml            ← Full stack Docker definition
└── pyproject.toml                ← Black / flake8 / mypy config
```

---

## 🏁 Quick Start — The Minimum to Run Everything

```powershell
# === ONE-TIME SETUP ===
cd "C:\Users\Akash A\OneDrive\Desktop\ai-openBMC"
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Edit .env and add your HF_TOKEN (mandatory!)
notepad .env

# Build the RAG index
python -c "from rag_engine import build_index; build_index()"

# === EVERY TIME (2 terminals) ===

# Terminal 1 — FastAPI Backend
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Streamlit UI
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

**Then open:**
- Dashboard: http://localhost:8501
- API Docs:  http://localhost:8000/docs
- Health:    http://localhost:8000/health
