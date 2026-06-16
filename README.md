# 🖥️ AI OpsBMC

> **RAG + LLM powered hardware diagnostics on OpenBMC**  
> Redfish telemetry · Semantic search · Qwen3-8B · FastAPI · Streamlit

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit)](https://streamlit.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector--db-orange)](https://www.trychroma.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 What Is This?

AI OpsBMC is an intelligent diagnostics engine built on top of [OpenBMC](https://github.com/openbmc/openbmc) — the open-source firmware stack used in server Baseboard Management Controllers (BMCs).

It connects to a real or emulated BMC via the **Redfish REST API**, retrieves hardware telemetry (memory health, CPU thermals, PSU status), and runs it through a **RAG + LLM pipeline** to generate structured root cause analyses — complete with severity rating, confidence score, and actionable recommendations.

```
OpenBMC (QEMU or real hardware)
          ↓  Redfish API
    Python Telemetry Client
          ↓  JSON
       Event Parser
          ↓  Normalised events
    RAG Engine (ChromaDB)
          ↓  Retrieved knowledge
    Qwen3-8B via HuggingFace
          ↓  Structured JSON
    FastAPI Backend :8000
          ↓  HTTP
    Streamlit Dashboard :8501
```

---

## 🎯 Phase A — What's Implemented

Phase A covers four weeks of foundational work:

| Week | Layer | What Was Built |
|---|---|---|
| **1** | Data Collection | OpenBMC QEMU setup, Redfish client, mock SEL generator, event parser |
| **2** | Knowledge & Retrieval | Domain knowledge base, chunking, Sentence Transformer embeddings, ChromaDB semantic search |
| **3** | AI Diagnosis Engine | Qwen3-8B integration, RAG-augmented prompting, structured JSON diagnosis |
| **4** | Production Service | FastAPI REST backend, Streamlit dashboard, live QEMU integration, persistent result storage |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Streamlit Dashboard :8501                  │
│                                                         │
│  [Select Scenario ▼]    Severity:    🔴 CRITICAL        │
│  [🔍 Run Diagnosis]     Confidence:  87%                │
│  [📡 Fetch from QEMU]   Root Cause:  DIMM degradation   │
│  🟢 BMC Online          Action:      Replace DIMM_B2    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend :8000                   │
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

---

## 🗂️ Project Structure

```
ai-openBMC/
│
├── main.py              # FastAPI REST backend (8 endpoints)
├── app.py               # Streamlit web dashboard
├── agent.py             # RAG + LLM diagnosis pipeline
├── rag_engine.py        # Embeddings, ChromaDB, cosine retrieval
├── parser.py            # Redfish JSON parser + event extractor
├── redfish_client.py    # Redfish API client (live QEMU fetch)
├── mock_bmc.py          # Mock SEL event generator (offline dev)
│
├── knowledge/           # Plain-text domain knowledge base
│   ├── dimm_failures.txt
│   ├── cpu_failures.txt
│   └── psu_failures.txt
│
├── redfish_data/        # Saved Redfish JSON snapshots (gitignored)
├── chroma_db/           # ChromaDB vector store (gitignored)
├── diagnosis_results.json  # Persistent diagnosis history
│
├── .env                 # HF_TOKEN (gitignored)
├── .gitignore
└── requirements.txt
```

---

## ⚡ Quick Start

### Prerequisites

- Python 3.12+
- QEMU (for live BMC emulation) — optional, mock scenarios work offline
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

### 3. Start the FastAPI backend

```bash
uvicorn main:app --reload --port 8000
```

### 4. Start the Streamlit dashboard

```bash
# In a new terminal
source venv/bin/activate
streamlit run app.py
```

Open **http://localhost:8501** — select a scenario, click **Run Diagnosis**.

---

## 🔴 Live QEMU Mode (Optional)

To connect to a real emulated BMC:

```bash
# Boot OpenBMC Romulus in QEMU
qemu-system-arm \
  -machine romulus-bmc \
  -m 512 \
  -drive file=tmp/deploy/images/romulus/obmc-phosphor-image-romulus.static.mtd,if=mtd,format=raw \
  -serial mon:stdio \
  -serial null \
  -netdev user,id=net0,hostfwd=tcp::2443-:443 \
  -net nic,netdev=net0
```

Wait for the login prompt (~2-3 minutes), then use the **📡 Fetch from QEMU** button in the dashboard sidebar.

The dashboard detects BMC status automatically:
- 🟢 **BMC Online** — QEMU is running and reachable
- 🟡 **BMC Timeout** — QEMU is still booting
- 🔴 **No BMC Found** — QEMU is not running (fetch button disabled)

---

## 🧠 How the Diagnosis Works

### 1. Event Parsing
Raw Redfish JSON or mock SEL events are normalised into a canonical schema:
```json
{"sensor": "DIMM_B2", "category": "MEMORY", "event_type": "ECC_ERROR", "severity": "WARNING"}
```

### 2. RAG Retrieval
The event is embedded using `all-MiniLM-L6-v2` and queried against ChromaDB. The top chunk is sentence-level cosine re-ranked with a restatement penalty to surface actionable sentences over literal restatements.

### 3. LLM Diagnosis
The retrieved sentence is injected into a structured prompt sent to **Qwen3-8B** via HuggingFace Inference API (`/no_think` mode for fast, consistent JSON output):

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

## 🌐 API Reference

Full interactive docs available at **http://localhost:8000/docs** (Swagger UI).

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

### Example — diagnose a DIMM failure

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

## 🧰 Tech Stack

| Component | Technology | Why |
|---|---|---|
| BMC firmware | OpenBMC | Open-source, industry standard |
| Telemetry API | Redfish (DMTF) | REST-based, JSON, modern standard |
| Embeddings | `all-MiniLM-L6-v2` | Fast, 384-dim, CPU-friendly, Apache 2.0 |
| Vector DB | ChromaDB | Local, persistent, zero cloud dependency |
| LLM | Qwen3-8B | Free (HuggingFace), native JSON, thinking mode |
| Backend | FastAPI + Uvicorn | Async, auto-docs, Pydantic validation |
| Frontend | Streamlit | Python-native UI, zero JS |
| Secrets | python-dotenv | `.env` file, never committed |

---

## 📦 Installation

```bash
pip install -r requirements.txt
```

```
fastapi
uvicorn
streamlit
sentence-transformers
chromadb
huggingface-hub
requests
numpy
urllib3
python-dotenv
pydantic
```

---

## 🗓️ Roadmap

### Phase B (Planned)
- [ ] WebSocket endpoint for real-time streaming diagnosis
- [ ] SQLite result storage (`aiosqlite`) replacing JSON file
- [ ] FastAPI API key authentication
- [ ] Docker Compose deployment (FastAPI + Streamlit + ChromaDB)
- [ ] `/metrics` endpoint in Prometheus format
- [ ] Batch diagnosis — multiple events in one LLM call
- [ ] Sentence-aware chunking (`nltk.sent_tokenize`) replacing character chunking
- [ ] Confidence threshold — skip LLM if RAG score too low
- [ ] Multi-sensor correlation (`/think` mode for complex events)

---

## 🤝 Contributing

This project is part of an OpenBMC internship contribution.  
Knowledge base files under `knowledge/` can be extended with new hardware failure domains — each `.txt` file added is automatically indexed on next startup.

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
- [RAG — Lewis et al. 2020](https://arxiv.org/abs/2005.11401)
- [FastAPI Documentation](https://fastapi.tiangolo.com)

---

*Built at my home Akash A  · OpenBMC Project · Phase A*