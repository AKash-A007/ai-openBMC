# #this is the file so that we can run the entire pipeline together 
# """
# main.py  —  Orchestrator
# Run this to execute the full pipeline:
#   1. (Optional) Fetch live Redfish data from OpenBMC
#   2. Build RAG index from knowledge base
#   3. Parse events from saved JSON files
#   4. Diagnose each event with RAG + LLM
#   5. Print results
# """

import json
from pathlib import Path
from rag_engine import build_index
from parser import extract_all_events
from agent import diagnose
import signal
import sys
from dotenv import load_dotenv
load_dotenv()          # reads .env automatically, no terminal setup needed
# def run_pipeline(fetch_live: bool = False) -> None:

#     # ── Step 1: Optionally fetch live Redfish data ─────────────────────────────
#     if fetch_live:
#         print("=" * 50)
#         print("STEP 1: Fetching live Redfish data from OpenBMC")
#         print("=" * 50)
#         from redfish_client import fetch_all
#         fetch_all()
#     else:
#         print("[Main] Using saved JSON files from ./redfish_data/")

#     # ── Step 2: Build RAG index ────────────────────────────────────────────────
#     print("\n" + "=" * 50)
#     print("STEP 2: Building RAG index")
#     print("=" * 50)
#     build_index()   # skips automatically if already built

#     # ── Step 3: Extract events from saved JSON files ───────────────────────────
#     print("\n" + "=" * 50)
#     print("STEP 3: Extracting events from saved JSON files")
#     print("=" * 50)
#     events = extract_all_events()

#     if not events:
#         print("[Main] No events to diagnose. Exiting.")
#         return

#     # ── Step 4: Diagnose each event ────────────────────────────────────────────
#     print("\n" + "=" * 50)
#     print(f"STEP 4: Diagnosing {len(events)} event(s)")
#     print("=" * 50)

#     results = []
#     for i, event in enumerate(events, 1):
#         print(f"\n[{i}/{len(events)}] {event['sensor']} — {event['event']}")
#         result = diagnose(event)
#         results.append(result)
#         print(json.dumps(result, indent=2))

#     # ── Step 5: Save results ───────────────────────────────────────────────────
#     output_path = Path("./diagnosis_results.json")
#     with open(output_path, "w") as f:
#         json.dump(results, f, indent=2)
#     print(f"\n[Main] Results saved → {output_path}")


# if __name__ == "__main__":
#     # fetch_live=False  → use saved JSON files (current phase)
#     # fetch_live=True   → hit live OpenBMC Redfish endpoints first
#     run_pipeline(fetch_live=False)
"""
    use the above for refrence to make the fastapi and streamlit work together in one file
"""
"""
main.py  —  Week 4 FastAPI Backend
AI OpsBMC Diagnostics Service

Endpoints:
  GET  /health             → service status + index info
  GET  /scenarios          → list all available mock scenarios
  GET  /scenario/{name}    → get a specific scenario event dict
  POST /diagnose           → run full RAG + LLM diagnosis on an event
  POST /diagnose/scenario  → diagnose by scenario name directly
  GET  /results            → list all past diagnosis results
"""

import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from rag_engine import build_index, _get_collection
from parser import extract_all_events
from agent import diagnose

# ── Phase C Week 4: Automation pipeline ───────────────────────────────────────
from automation.policy_engine    import evaluate_policy, ApprovalMode
from automation.approval_manager import ApprovalManager, ApprovalStatus
from automation.execution_engine import ExecutionEngine
from automation.audit_logger     import AuditLogger


# ── Pydantic models (request / response shapes) ────────────────────────────────

class EventInput(BaseModel):
    """Input for POST /diagnose"""
    sensor: str
    event: str
    severity: str = "WARNING"           # default if caller omits it


class ScenarioRequest(BaseModel):
    """Input for POST /diagnose/scenario"""
    name: str                            # e.g. "dimm_failure"


class RemediateRequest(BaseModel):
    """Input for POST /remediate — wraps a diagnosis result"""
    issue        : str
    action       : str               # recommendation from diagnosis
    sensor       : str  = "UNKNOWN"
    severity     : str  = "UNKNOWN"
    executed_by  : str  = "auto"     # override to record human initiator


class ApprovalActionRequest(BaseModel):
    """Input for POST /approvals/{id}/approve or /reject"""
    resolved_by : str  = "ops-engineer"
    notes       : str  = ""


class DiagnosisResponse(BaseModel):
    """Structured response returned by all diagnosis endpoints"""
    event: dict
    root_cause: str
    severity: str
    confidence: str
    recommendation: str
    requires_immediate_action: bool
    rag_context: str
    timestamp: str
    duration_ms: float


# ── Mock scenarios (replaces generate_sel_log from Week 3) ────────────────────

SCENARIOS: dict[str, dict] = {
    "dimm_failure": {
        "sensor"  : "DIMM_B2",
        "event"   : "Memory ECC Error",
        "severity": "WARNING",
    },
    "cpu_overheat": {
        "sensor"  : "CPU0",
        "event"   : "CPU Over Temperature",
        "severity": "CRITICAL",
    },
    "psu_failure": {
        "sensor"  : "PSU1",
        "event"   : "Power Supply Failure",
        "severity": "CRITICAL",
    },
    "fan_fault": {
        "sensor"  : "FAN_3",
        "event"   : "Fan Fault",
        "severity": "WARNING",
    },
    "voltage_fault": {
        "sensor"  : "VR_CPU0",
        "event"   : "Voltage Fault",
        "severity": "CRITICAL",
    },
}


# ── Results store (in-memory, persisted to JSON) ──────────────────────────────

RESULTS_PATH = Path("./diagnosis_results.json")

def _load_results() -> list:
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []

def _save_results(results: list) -> None:
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


# ── Lifespan: startup tasks (build index once when server starts) ──────────────

# ── Incident Store ─────────────────────────────────────────────────────────────
# Tracks the full lifecycle of each incident (detected → diagnosed → executed → resolved)

INCIDENTS_PATH = Path("./incidents.json")

def _load_incidents() -> list:
    if INCIDENTS_PATH.exists():
        with open(INCIDENTS_PATH) as f:
            return json.load(f)
    return []

def _save_incidents(incidents: list) -> None:
    with open(INCIDENTS_PATH, "w") as f:
        json.dump(incidents, f, indent=2)


# ── Singletons for automation pipeline ────────────────────────────────────────
# Shared across all requests — initialised once on startup
_approval_manager : ApprovalManager | None = None
_execution_engine : ExecutionEngine | None = None
_audit_logger     : AuditLogger     | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup — builds RAG index and initialises automation singletons."""
    global _approval_manager, _execution_engine, _audit_logger
    print("[Main] Starting AI OpsBMC Autonomous Operations service...")
    try:
        build_index()           # skips if already built
        print("[Main] RAG index ready.")
    except Exception as e:
        print(f"[Main] WARNING: Could not build index: {e}")

    # Initialise automation pipeline components
    _approval_manager = ApprovalManager()
    _execution_engine = ExecutionEngine()
    _audit_logger     = AuditLogger()
    print("[Main] Automation pipeline ready (Policy → Approve → Execute → Audit).")
    yield
    print("[Main] Shutting down.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI OpsBMC Diagnostics",
    description="RAG + LLM-powered OpenBMC hardware diagnostics engine",
    version="0.4.0",
    lifespan=lifespan,
)

# Allow Streamlit (running on :8501) to call this API
"""
CORS Middleware is a component used in web frameworks to manage Cross-Origin Resource Sharing by 
setting appropriate HTTP headers (like Access-Control-Allow-Origin) and handling preflight requests 
(OPTIONS requests) for complex cross-domain requests"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_diagnosis(event_dict: dict) -> DiagnosisResponse:
    """
    Core helper: run the full diagnosis pipeline and return a structured response.
    Wraps agent.diagnose() with timing, error handling, and result persistence.
    """
    start = time.time()

    try:
        raw = diagnose(event_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {e}")

    if "error" in raw:
        raise HTTPException(status_code=422, detail=raw["error"])

    duration_ms = round((time.time() - start) * 1000, 2)
    timestamp   = datetime.utcnow().isoformat() + "Z"

    response = DiagnosisResponse(
        event                    = event_dict,
        root_cause               = raw.get("root_cause", "Unknown"),
        severity                 = raw.get("severity",   "UNKNOWN"),
        confidence               = raw.get("confidence", "0%"),
        recommendation           = raw.get("recommendation", "No action available"),
        requires_immediate_action= raw.get("requires_immediate_action", False),
        rag_context              = raw.get("rag_context", ""),
        timestamp                = timestamp,
        duration_ms              = duration_ms,
    )

    # Persist to results file
    results = _load_results()
    results.append(response.model_dump())
    _save_results(results)

    return response


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    """
    Returns service status and RAG index info.
    Streamlit uses this to verify the backend is alive.
    """
    try:
        collection  = _get_collection()
        chunk_count = collection.count()
        index_ok    = chunk_count > 0
    except Exception:
        chunk_count = 0
        index_ok    = False

    return {
        "status"      : "healthy" if index_ok else "degraded",
        "rag_index"   : "ready"   if index_ok else "empty — run build_index()",
        "chunks"      : chunk_count,
        "scenarios"   : list(SCENARIOS.keys()),
        "timestamp"   : datetime.utcnow().isoformat() + "Z",
    }


@app.get("/scenarios", tags=["Scenarios"])
def list_scenarios():
    """Return all available mock scenarios."""
    return {
        "scenarios": [
            {"name": name, "sensor": s["sensor"], "event": s["event"],
             "severity": s["severity"]}
            for name, s in SCENARIOS.items()
        ]
    }


@app.get("/scenario/{name}", tags=["Scenarios"])
def get_scenario(name: str):
    """
    Return the raw event dict for a named scenario.
    Streamlit calls this before POST /diagnose.

    Example: GET /scenario/dimm_failure
    → {"sensor": "DIMM_B2", "event": "Memory ECC Error", "severity": "WARNING"}
    """
    if name not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{name}' not found. "
                   f"Available: {list(SCENARIOS.keys())}"
        )
    return {"name": name, "event": SCENARIOS[name]}


@app.post("/diagnose", response_model=DiagnosisResponse, tags=["Diagnosis"])
def diagnose_event(event: EventInput):
    """
    Run full RAG + LLM diagnosis on a raw event.

    Input:
        {"sensor": "DIMM_B2", "event": "Memory ECC Error", "severity": "WARNING"}

    Output:
        {"root_cause": "...", "severity": "HIGH", "confidence": "87%", ...}
    """
    return _run_diagnosis(event.model_dump())


@app.post("/diagnose/scenario", response_model=DiagnosisResponse, tags=["Diagnosis"])
def diagnose_by_scenario(req: ScenarioRequest):
    """
    Diagnose by scenario name — Streamlit's main call after user selects from dropdown.

    Input:  {"name": "dimm_failure"}
    Output: full DiagnosisResponse
    """
    if req.name not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{req.name}' not found."
        )
    return _run_diagnosis(SCENARIOS[req.name])


@app.get("/results", tags=["History"])
def get_results(limit: int = 20):
    """
    Return the last `limit` diagnosis results from the persistent store.
    Streamlit uses this to show history.
    """
    results = _load_results()
    return {
        "total"  : len(results),
        "results": results[-limit:][::-1],   # newest first
    }


@app.delete("/results", tags=["History"])
def clear_results():
    """Clear all stored diagnosis results."""
    _save_results([])
    return {"message": "Results cleared."}

@app.post("/fetch", tags=["Live QEMU"])
@app.post("/fetch", tags=["Live QEMU"])
def fetch_live_data():
    """
    Pull fresh data from QEMU OpenBMC via Redfish.
    Returns clear error if QEMU is not running.
    """
    try:
        from redfish_client import fetch_all
        fetch_all()
        return {
            "status"  : "success",
            "message" : "Live Redfish data fetched from QEMU",
            "saved_to": "./redfish_data/",
        }

    except ConnectionError as e:
        # QEMU not running — port refused
        raise HTTPException(
            status_code=503,
            detail={
                "error"  : "BMC_NOT_FOUND",
                "message": str(e),
                "hint"   : "Start QEMU first: qemu-system-arm -machine romulus-bmc ...",
            }
        )

    except TimeoutError as e:
        # QEMU booting
        raise HTTPException(
            status_code=504,
            detail={
                "error"  : "BMC_TIMEOUT",
                "message": str(e),
                "hint"   : "Wait 2-3 minutes for QEMU to fully boot, then retry.",
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error"  : "FETCH_FAILED",
                "message": str(e),
                "hint"   : "Check QEMU terminal for errors.",
            }
        )

@app.get("/diagnose/live", tags=["Live QEMU"])
def diagnose_live():
    """
    Step 2: Parse the saved Redfish JSON files and diagnose all real events.
    Run /fetch first to get fresh data from QEMU.
    
    Returns all diagnosed events found in the real hardware state.
    """
    # Parse real events from saved redfish_data/ JSON files
    try:
        events = extract_all_events()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse Redfish data: {e}. Run POST /fetch first."
        )

    if not events:
        return {
            "status" : "ok",
            "message": "No faults detected in live QEMU data — system healthy",
            "events" : [],
            "results": [],
        }

    # Diagnose each real event
    results = []
    for event in events:
        try:
            result = _run_diagnosis(event)
            results.append(result.model_dump())
        except HTTPException as e:
            results.append({
                "event" : event,
                "error" : e.detail,
            })

    return {
        "status"      : "ok",
        "source"      : "live_qemu",
        "events_found": len(results),
        "results"     : results,
    }
# ── Phase C Week 4: Autonomous Remediation Endpoints ─────────────────────────

@app.post("/remediate", tags=["Remediation"])
def remediate(req: RemediateRequest):
    """
    Feed a diagnosis recommendation into the full automation pipeline:

        Policy Engine → AUTO? Execute immediately
                      → MANUAL? Create approval request and wait

    Returns the execution result (AUTO) or the pending approval (MANUAL).
    """
    policy = evaluate_policy(req.action)

    if policy == ApprovalMode.AUTO:
        # Execute immediately — no human needed
        result = _execution_engine.execute(
            action      = req.action,
            issue       = req.issue,
            sensor      = req.sensor,
            severity    = req.severity,
            policy      = policy.value,
            executed_by = req.executed_by,
        )

        # Record in incident store
        incidents = _load_incidents()
        incident_id = str(uuid.uuid4())
        incidents.append({
            "id"           : incident_id,
            "issue"        : req.issue,
            "sensor"       : req.sensor,
            "severity"     : req.severity,
            "action"       : req.action,
            "policy"       : policy.value,
            "execution"    : result,
            "detected_at"  : result["timestamp"],
            "executed_at"  : result["timestamp"],
            "resolved"     : result["success"],
            "resolved_at"  : result["timestamp"] if result["success"] else None,
        })
        _save_incidents(incidents)

        return {
            "mode"        : "AUTO",
            "incident_id" : incident_id,
            "action"      : req.action,
            "status"      : result["status"],
            "success"     : result["success"],
            "details"     : result["details"],
            "audit_id"    : result.get("audit_id"),
            "rollback"    : result.get("rollback"),
            "timestamp"   : result["timestamp"],
        }

    else:
        # MANUAL — create approval request
        approval = _approval_manager.request_approval(
            issue    = req.issue,
            action   = req.action,
            sensor   = req.sensor,
            severity = req.severity,
            policy   = policy.value,
        )
        # Log the pending action in audit log
        _audit_logger.log(
            issue       = req.issue,
            action      = req.action,
            status      = "PENDING",
            executed_by = req.executed_by,
            policy      = policy.value,
            sensor      = req.sensor,
            severity    = req.severity,
            details     = f"Approval request created: {approval.id}",
        )
        return {
            "mode"          : "MANUAL",
            "approval_id"   : approval.id,
            "action"        : req.action,
            "status"        : "PENDING",
            "message"       : "Action requires human approval. Use POST /approvals/{id}/approve.",
            "requested_at"  : approval.requested_at,
        }


@app.get("/approvals", tags=["Remediation"])
def list_approvals(pending_only: bool = False):
    """
    List all approval requests (MANUAL-policy actions waiting for human sign-off).
    Set ?pending_only=true to show only unresolved requests.
    """
    requests = (
        _approval_manager.list_pending()
        if pending_only
        else _approval_manager.list_all(limit=50)
    )
    return {
        "total"    : len(requests),
        "requests" : [r.to_dict() for r in requests],
        "stats"    : _approval_manager.stats(),
    }


@app.post("/approvals/{request_id}/approve", tags=["Remediation"])
def approve_action(request_id: str, body: ApprovalActionRequest):
    """
    Human approves a MANUAL action — triggers immediate execution.
    """
    try:
        approval = _approval_manager.approve(request_id, approved_by=body.resolved_by)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Approval request '{request_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Now execute
    result = _execution_engine.execute(
        action      = approval.action,
        issue       = approval.issue,
        sensor      = approval.sensor,
        severity    = approval.severity,
        policy      = approval.policy,
        executed_by = body.resolved_by,
    )

    # Record incident
    incidents = _load_incidents()
    incident_id = str(uuid.uuid4())
    incidents.append({
        "id"           : incident_id,
        "issue"        : approval.issue,
        "sensor"       : approval.sensor,
        "severity"     : approval.severity,
        "action"       : approval.action,
        "policy"       : "MANUAL",
        "approval_id"  : approval.id,
        "execution"    : result,
        "detected_at"  : approval.requested_at,
        "approved_at"  : approval.resolved_at,
        "executed_at"  : result["timestamp"],
        "resolved"     : result["success"],
        "resolved_at"  : result["timestamp"] if result["success"] else None,
    })
    _save_incidents(incidents)

    return {
        "approval_id" : request_id,
        "incident_id" : incident_id,
        "action"      : approval.action,
        "status"      : result["status"],
        "success"     : result["success"],
        "details"     : result["details"],
        "audit_id"    : result.get("audit_id"),
    }


@app.post("/approvals/{request_id}/reject", tags=["Remediation"])
def reject_action(request_id: str, body: ApprovalActionRequest):
    """Human rejects a MANUAL action — it will NOT be executed."""
    try:
        approval = _approval_manager.reject(
            request_id,
            rejected_by = body.resolved_by,
            reason      = body.notes,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Approval request '{request_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _audit_logger.log(
        issue       = approval.issue,
        action      = approval.action,
        status      = "REJECTED",
        executed_by = body.resolved_by,
        policy      = approval.policy,
        sensor      = approval.sensor,
        severity    = approval.severity,
        details     = f"Rejected by {body.resolved_by}. Reason: {body.notes}",
    )
    return {
        "approval_id" : request_id,
        "action"      : approval.action,
        "status"      : "REJECTED",
        "resolved_by" : body.resolved_by,
    }


@app.get("/audit", tags=["Governance"])
def get_audit_log(limit: int = 50):
    """
    Return the most recent `limit` entries from the audit log.
    Shows every autonomous action the system has taken or attempted.
    """
    entries = _audit_logger.get_log(limit=limit)
    return {
        "total"   : _audit_logger.count(),
        "limit"   : limit,
        "entries" : entries,
        "stats"   : _audit_logger.stats(),
    }


@app.get("/incidents", tags=["Governance"])
def get_incidents(limit: int = 20):
    """
    Return the full incident timeline:
    detected_at → approved_at → executed_at → resolved_at
    """
    incidents = _load_incidents()
    return {
        "total"    : len(incidents),
        "incidents": incidents[-limit:][::-1],   # newest first
    }


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)