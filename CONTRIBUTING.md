# Contributing to AI OpsBMC

Thank you for your interest in contributing to **AI OpsBMC**! This document explains how to set up a development environment, coding standards, and the PR workflow.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Running Tests](#running-tests)
- [Submitting Changes](#submitting-changes)
- [Adding to the Knowledge Base](#adding-to-the-knowledge-base)
- [Adding Remediation Actions](#adding-remediation-actions)

---

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Quick Start (Local / Mock BMC)

```bash
# 1. Clone the repository
git clone https://github.com/Akash-A007/ai-openBMC.git
cd ai-openBMC

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start with mock BMC (no real hardware needed)
python mock_bmc.py &            # start the simulated BMC

# 5. Run the main application
python main.py

# 6. Open dashboard
# Navigate to http://localhost:8000
```

### Docker Compose (Full Stack)

```bash
docker compose up --build
```

Services will be available at:
| Service | Port |
|---------|------|
| Dashboard API | 8000 |
| Collector | 8001 |
| Analytics | 8002 |
| Agent | 8003 |
| Grafana | 3000 |
| Prometheus | 9090 |

---

## Project Structure

```
ai-openBMC/
├── analytics/              # Anomaly detection, prediction, health scoring
│   ├── anomaly_detector.py # Isolation Forest engine
│   ├── features.py         # Feature engineering
│   ├── health_score.py     # System health aggregation
│   └── predictor.py        # Multi-horizon failure prediction
│
├── automation/             # Autonomous remediation pipeline
│   ├── action_executor.py  # Low-level action implementation
│   ├── approval_manager.py # Human approval gate
│   ├── audit_logger.py     # Immutable audit trail
│   ├── execution_engine.py # Orchestrates execution lifecycle
│   ├── policy_engine.py    # Rule-based action governance
│   └── rollback_manager.py # Automatic remediation undo
│
├── knowledge/              # RAG knowledge base (plain text)
│   ├── cpu_failures.txt
│   ├── dimm_failure.txt
│   └── psu_failures.txt
│
├── monitoring/             # Observability stack configs
│   ├── grafana/            # Grafana dashboard JSON
│   ├── prometheus/         # Prometheus scrape config
│   ├── alerts.py           # Alert rule definitions
│   ├── dashboard.py        # Monitoring dashboard
│   ├── metrics.py          # Prometheus metric definitions
│   └── reports.py          # Report generation
│
├── services/               # Microservice entrypoints
│   ├── agent/              # Agent service (FastAPI)
│   ├── analytics/          # Analytics service (FastAPI)
│   ├── collector/          # Collector service (FastAPI)
│   └── dashboard/          # Dashboard service (FastAPI)
│
├── telemetry/              # Data layer
│   ├── collector.py        # BMC polling + batch insert
│   ├── database.py         # SQLite/PostgreSQL abstraction
│   └── query.py            # Query helpers + caching
│
├── k8s/                    # Kubernetes manifests
├── tests/                  # Pytest test suite
├── .github/workflows/      # CI/CD pipelines
├── main.py                 # Monolith entry point (dev)
├── app.py                  # FastAPI app definition
├── agent.py                # Diagnosis agent
├── rag_engine.py           # RAG retrieval engine
├── mock_bmc.py             # BMC simulator
└── docker-compose.yml
```

---

## Coding Standards

### Style

- Follow **PEP 8** for all Python code.
- Use **type hints** on all function signatures.
- Use **docstrings** on all public functions and classes.
- Maximum line length: **100 characters**.

### Linting

```bash
# Run linter
flake8 . --max-line-length=100

# Auto-format
black . --line-length 100
```

### Naming Conventions

| Entity | Convention | Example |
|--------|------------|---------|
| Functions | `snake_case` | `get_anomaly_score()` |
| Classes | `PascalCase` | `AnomalyDetector` |
| Constants | `UPPER_SNAKE` | `DEFAULT_CONTAMINATION` |
| Files | `snake_case.py` | `anomaly_detector.py` |

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run a specific test file
pytest tests/test_database.py -v
```

The CI pipeline runs tests automatically on every PR against `main`.

---

## Submitting Changes

1. **Fork** the repository on GitHub.
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make your changes with appropriate tests.
4. Run `pytest` and `flake8` to confirm all checks pass.
5. Commit with a descriptive message:
   ```
   feat(analytics): add LSTM-based predictor for DIMM errors
   
   Replaces the Random Forest predictor for DIMM error forecasting
   with a lightweight LSTM model that better captures temporal
   error accumulation patterns. Maintains the same predictor.py API.
   ```
6. Push and open a **Pull Request** against `main`.
7. PRs require at least one approval before merging.

### Commit Message Format

```
<type>(<scope>): <short description>

<optional body>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Adding to the Knowledge Base

The RAG knowledge base lives in `knowledge/`. To add a new fault category:

1. Create `knowledge/your_fault_type.txt`.
2. Write plain-text descriptions of:
   - Symptoms (what sensor readings indicate this fault)
   - Root causes (what typically causes this fault)
   - Recommended actions (what should be done)
3. Rebuild the RAG index:
   ```python
   from rag_engine import build_index
   build_index(force=True)
   ```

Keep entries factual and hardware-specific. Avoid vague language.

---

## Adding Remediation Actions

To add a new autonomous remediation action:

1. **Implement the action** in `automation/action_executor.py`:
   ```python
   async def my_new_action(params: dict) -> dict:
       """
       Perform the action. Return a dict with:
         - success: bool
         - message: str
         - details: dict (optional)
       """
       ...
   ```

2. **Register the action** in `automation/execution_engine.py`'s `ACTION_REGISTRY`.

3. **Add a policy rule** in `automation/policy_engine.py` specifying which fault conditions permit this action and whether it requires human approval.

4. **Write a test** in `tests/` verifying the action's success and failure paths.

5. **Add a rollback** in `automation/rollback_manager.py` if the action is reversible.

---

## Questions?

Open a [GitHub Discussion](https://github.com/Akash-A007/ai-openBMC/discussions) or file an issue with the `question` label.
