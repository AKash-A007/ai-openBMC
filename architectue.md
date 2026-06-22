# AI OpsBMC — Architecture Diagrams

These render natively on GitHub — no image hosting needed. Paste any block directly into a `.md` file inside a ` ```mermaid ` fence.

---

## 1. Full System Architecture (Phase A + Phase B)

```mermaid
flowchart TB
    subgraph BMC["🖥️ OpenBMC (QEMU Romulus / Real Hardware)"]
        REDFISH["Redfish REST API\n/Systems /Chassis /Thermal /Power"]
    end

    subgraph PHASE_A["PHASE A — Diagnosis Engine"]
        direction TB
        RC["redfish_client.py\nfetch + save JSON"]
        PARSER["parser.py\nnormalise events\n(category, event_type)"]
        RAG["rag_engine.py\nall-MiniLM-L6-v2 embeddings\nChromaDB + cosine re-rank"]
        AGENT["agent.py\nQwen3-8B via HuggingFace\nRAG-augmented prompt"]
        KNOWLEDGE[("knowledge/*.txt\nDIMM · CPU · PSU docs")]

        RC --> PARSER --> RAG
        KNOWLEDGE -.indexed into.-> RAG
        RAG --> AGENT
    end

    subgraph PHASE_B["PHASE B — Historical Intelligence"]
        direction TB
        COLLECTOR["collector.py\npolls every 5s"]
        DB[("SQLite\ntelemetry + diagnoses")]
        ANOMALY["anomaly_detector.py\nIsolationForest"]
        PREDICTOR["predictor.py\nthreshold + anomaly + trend"]
        HEALTH["health_score.py\n0-100 score"]
        ALERTS["alerts.py\nseverity rules"]
        REPORTS["reports.py\nrecurring RCA issues"]

        COLLECTOR --> DB
        DB --> ANOMALY
        DB --> PREDICTOR
        ANOMALY --> PREDICTOR
        PREDICTOR --> HEALTH
        HEALTH --> ALERTS
        DB --> REPORTS
    end

    subgraph SERVICE["Service Layer"]
        FASTAPI["FastAPI :8000\n/diagnose /health /results"]
        APP_UI["Streamlit app.py :8501\n(trigger diagnoses)"]
        DASH_UI["Streamlit dashboard.py\n(observe health)"]
    end

    REDFISH --> RC
    AGENT --> FASTAPI
    FASTAPI --> APP_UI
    REDFISH -.mock fallback.-> COLLECTOR
    ALERTS --> DASH_UI
    REPORTS --> DASH_UI
    HEALTH --> DASH_UI

    style PHASE_A fill:#1a1a2e,stroke:#6366f1,color:#fff
    style PHASE_B fill:#16213e,stroke:#06b6d4,color:#fff
    style SERVICE fill:#0f0f1a,stroke:#f59e0b,color:#fff
    style BMC fill:#000000,stroke:#ef4444,color:#fff
```

---

## 2. Phase A — Diagnosis Request Flow (Sequence)

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit (app.py)
    participant API as FastAPI (main.py)
    participant Parser as parser.py
    participant RAG as rag_engine.py
    participant Chroma as ChromaDB
    participant LLM as Qwen3-8B (HuggingFace)

    User->>UI: Select scenario, click "Run Diagnosis"
    UI->>API: POST /diagnose/scenario {"name": "dimm_failure"}
    API->>Parser: parse_log(event)
    Parser-->>API: {category: MEMORY, event_type: ECC_ERROR}
    API->>RAG: rag_query("MEMORY ECC_ERROR")
    RAG->>Chroma: similarity search
    Chroma-->>RAG: top chunk
    RAG->>RAG: sentence-level cosine re-rank\n(restatement penalty)
    RAG-->>API: "Repeated ECC errors indicate DIMM degradation."
    API->>LLM: structured prompt (role+RAG+JSON format)
    LLM-->>API: {root_cause, severity, confidence, recommendation}
    API->>API: save to diagnosis_results.json
    API-->>UI: DiagnosisResponse JSON
    UI-->>User: Render severity badge, root cause, recommendation
```

---

## 3. Phase B — Telemetry to Alert Flow (Sequence)

```mermaid
sequenceDiagram
    participant Collector as collector.py
    participant DB as SQLite
    participant Iso as IsolationForest
    participant Pred as predictor.py
    participant Health as health_score.py
    participant Alert as alerts.py
    participant Dash as dashboard.py

    loop Every 5 seconds
        Collector->>Collector: generate reading + classify status
        Collector->>DB: INSERT INTO telemetry
    end

    Dash->>DB: get_sensor_history(sensor)
    DB-->>Dash: [70, 72, 74, ... 91]

    Dash->>Iso: detect_anomalies(sensor)
    Iso-->>Dash: {anomaly_count, anomalies[]}

    Dash->>Pred: predict_failure(sensor)
    Pred->>Pred: threshold_score + anomaly_score + trend_score
    Pred-->>Dash: {failure_probability: 0.52, risk: MEDIUM}

    Dash->>Health: calculate_health_score(sensor)
    Health-->>Dash: {health_score: 65}

    Dash->>Alert: check_all_alerts()
    Alert->>Alert: apply thresholds to health + anomaly output
    Alert-->>Dash: [{severity: WARNING, message: "..."}]

    Dash-->>Dash: render trend graph + alerts + RCA history
```

---

## 4. Data Model (Entity Relationship)

```mermaid
erDiagram
    TELEMETRY {
        int id PK
        text timestamp
        text sensor
        real value
        text status
    }
    DIAGNOSES {
        int id PK
        text timestamp
        text sensor
        text root_cause
        real confidence
    }
    KNOWLEDGE_CHUNK {
        string chunk_id PK
        string source
        int chunk_index
        vector embedding
        text content
    }

    TELEMETRY ||--o{ DIAGNOSES : "informs"
    KNOWLEDGE_CHUNK ||--o{ DIAGNOSES : "grounds via RAG"
```

---

## 5. Phase Roadmap (Gantt-style status)

```mermaid
gantt
    title AI OpsBMC — Development Timeline
    dateFormat YYYY-MM-DD
    section Phase A
    Week 1 Data Collection        :done, a1, 2026-06-01, 5d
    Week 2 Knowledge & Retrieval  :done, a2, after a1, 5d
    Week 3 AI Diagnosis Engine    :done, a3, after a2, 5d
    Week 4 Production Service     :done, a4, after a3, 5d
    section Phase B
    Week 1 Telemetry Storage      :done, b1, after a4, 5d
    Week 2 Anomaly Detection      :done, b2, after b1, 3d
    Week 3 Failure Prediction     :done, b3, after b2, 3d
    Week 4 Observability & Alerts :done, b4, after b3, 5d
    section Phase C
    Real-Time AIOps               :active, c1, after b4, 10d
```

---

### How to use these

1. Paste any block into `README.md` inside a ` ```mermaid ` code fence — GitHub renders it automatically, no plugin needed.
2. For a standalone image (e.g. for the Medium blog or PDF report), use the [Mermaid Live Editor](https://mermaid.live) — paste the code, export as PNG/SVG.
3. For VS Code, install the "Markdown Preview Mermaid Support" extension to preview locally before pushing.