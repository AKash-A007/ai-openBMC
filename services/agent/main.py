import json
import time
import uuid
import os
import hmac
import hashlib
import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Depends, Security, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

# Add project root to sys.path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from rag_engine import build_index, _get_collection
from parser import extract_all_events
from agent import diagnose

from automation.policy_engine import evaluate_policy, ApprovalMode
from automation.approval_manager import ApprovalManager, ApprovalStatus
from automation.execution_engine import ExecutionEngine
from automation.audit_logger import AuditLogger

# ── JWT Config & Security Helpers ──────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "AIOPS_SUPER_SECRET_KEY_12345")
TOKEN_EXPIRE_MINUTES = 60

# In-memory mock database of users
USERS_DB = {
    "admin": {"username": "admin", "password": "admin123", "role": "admin"},
    "operator": {"username": "operator", "password": "op123", "role": "operator"},
    "viewer": {"username": "viewer", "password": "view123", "role": "viewer"},
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().replace("=", "")
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().replace("=", "")
    )
    signature = hmac.new(
        secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().replace("=", "")
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_jwt(token: str, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header_b64, payload_b64, signature_b64 = parts

    signature = hmac.new(
        secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256
    ).digest()
    expected_signature_b64 = (
        base64.urlsafe_b64encode(signature).decode().replace("=", "")
    )

    if not hmac.compare_digest(signature_b64.encode(), expected_signature_b64.encode()):
        raise ValueError("Invalid signature")

    padding = "=" * (4 - len(payload_b64) % 4)
    payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
    payload = json.loads(payload_json)

    if "exp" in payload and payload["exp"] < time.time():
        raise ValueError("Token has expired")

    return payload


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_jwt(token, JWT_SECRET)
        username = payload.get("sub")
        if username not in USERS_DB:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return USERS_DB[username]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Depends(get_current_user)):
        if user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role",
            )
        return user


# ── Rate Limiter ──────────────────────────────────────────────────────────
# In-memory sliding window rate limits (60 requests per minute per IP)
rate_limit_store: Dict[str, List[float]] = {}
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 60.0


def rate_limiter(request: Request):
    ip = request.client.host
    now = time.time()

    if ip not in rate_limit_store:
        rate_limit_store[ip] = []

    # Clean up timestamps older than rate limit window
    rate_limit_store[ip] = [
        ts for ts in rate_limit_store[ip] if now - ts < RATE_LIMIT_WINDOW
    ]

    if len(rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before retrying.",
        )

    rate_limit_store[ip].append(now)


# ── Prometheus Metrics Configuration ──────────────────────────────────────
API_REQUESTS_TOTAL = Counter(
    "aiops_api_requests_total",
    "Total number of API requests received",
    ["method", "endpoint", "status"],
)
API_REQUEST_LATENCY = Histogram(
    "aiops_api_request_duration_seconds",
    "API request latency in seconds",
    ["method", "endpoint"],
)
LLM_INFERENCE_LATENCY = Histogram(
    "aiops_llm_inference_duration_seconds",
    "LLM and RAG diagnostic inference duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
REMEDIATIONS_TOTAL = Counter(
    "aiops_remediations_total",
    "Total number of remediation runs",
    ["action", "status", "policy"],
)

# ── Pydantic Request Models ────────────────────────────────────────────────


class EventInput(BaseModel):
    sensor: str
    event: str
    severity: str = "WARNING"


class ScenarioRequest(BaseModel):
    name: str


class RemediateRequest(BaseModel):
    issue: str
    action: str
    sensor: str = "UNKNOWN"
    severity: str = "UNKNOWN"
    executed_by: str = "auto"


class ApprovalActionRequest(BaseModel):
    resolved_by: str = "ops-engineer"
    notes: str = ""


class DiagnosisResponse(BaseModel):
    event: dict
    root_cause: str
    severity: str
    confidence: str
    recommendation: str
    requires_immediate_action: bool
    rag_context: str
    timestamp: str
    duration_ms: float


# ── Service State & Lifecycle ──────────────────────────────────────────────

RESULTS_PATH = Path("./diagnosis_results.json")
INCIDENTS_PATH = Path("./incidents.json")


def _load_results() -> list:
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def _save_results(results: list) -> None:
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


def _load_incidents() -> list:
    if INCIDENTS_PATH.exists():
        with open(INCIDENTS_PATH) as f:
            return json.load(f)
    return []


def _save_incidents(incidents: list) -> None:
    with open(INCIDENTS_PATH, "w") as f:
        json.dump(incidents, f, indent=2)


_approval_manager: ApprovalManager | None = None
_execution_engine: ExecutionEngine | None = None
_audit_logger: AuditLogger | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _approval_manager, _execution_engine, _audit_logger
    print("[Agent Service] Initialising RAG Index and Automation engines...")
    try:
        build_index()
    except Exception as e:
        print(f"[Agent Service] Warning: index construction failed: {e}")

    _approval_manager = ApprovalManager()
    _execution_engine = ExecutionEngine()
    _audit_logger = AuditLogger()
    yield
    print("[Agent Service] Shutting down.")


app = FastAPI(
    title="AI OpsBMC Diagnostic & Agent Service",
    description="Stateless RAG+LLM diagnostic broker and autonomous remediation engine",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(rate_limiter)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware to track request total and duration
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Record metrics
    endpoint = request.url.path
    API_REQUESTS_TOTAL.labels(
        method=request.method, endpoint=endpoint, status=response.status_code
    ).inc()
    API_REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(
        duration
    )

    return response


# Mock Scenarios dictionary
SCENARIOS = {
    "dimm_failure": {
        "sensor": "DIMM_B2",
        "event": "Memory ECC Error",
        "severity": "WARNING",
    },
    "cpu_overheat": {
        "sensor": "CPU0",
        "event": "CPU Over Temperature",
        "severity": "CRITICAL",
    },
    "psu_failure": {
        "sensor": "PSU1",
        "event": "Power Supply Failure",
        "severity": "CRITICAL",
    },
    "fan_fault": {"sensor": "FAN_3", "event": "Fan Fault", "severity": "WARNING"},
    "voltage_fault": {
        "sensor": "VR_CPU0",
        "event": "Voltage Fault",
        "severity": "CRITICAL",
    },
}

# ── Endpoints ──────────────────────────────────────────────────────────────


@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires
    payload = {"sub": user["username"], "role": user["role"], "exp": expire.timestamp()}
    token = create_jwt(payload, JWT_SECRET)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}


@app.get("/metrics", tags=["System"])
def get_metrics():
    from fastapi.responses import Response

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get(
    "/scenarios",
    tags=["Scenarios"],
    dependencies=[Depends(RoleChecker(["viewer", "operator", "admin"]))],
)
def list_scenarios():
    return {
        "scenarios": [
            {
                "name": name,
                "sensor": s["sensor"],
                "event": s["event"],
                "severity": s["severity"],
            }
            for name, s in SCENARIOS.items()
        ]
    }


@app.get(
    "/scenario/{name}",
    tags=["Scenarios"],
    dependencies=[Depends(RoleChecker(["viewer", "operator", "admin"]))],
)
def get_scenario(name: str):
    if name not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"name": name, "event": SCENARIOS[name]}


def _run_diagnosis(event_dict: dict) -> DiagnosisResponse:
    start = time.time()
    try:
        raw = diagnose(event_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {e}")

    duration_ms = round((time.time() - start) * 1000, 2)
    LLM_INFERENCE_LATENCY.observe(duration_ms / 1000.0)

    timestamp = datetime.now(timezone.utc).isoformat() + "Z"

    response = DiagnosisResponse(
        event=event_dict,
        root_cause=raw.get("root_cause", "Unknown"),
        severity=raw.get("severity", "UNKNOWN"),
        confidence=raw.get("confidence", "0%"),
        recommendation=raw.get("recommendation", "No action available"),
        requires_immediate_action=raw.get("requires_immediate_action", False),
        rag_context=raw.get("rag_context", ""),
        timestamp=timestamp,
        duration_ms=duration_ms,
    )

    results = _load_results()
    results.append(response.model_dump())
    _save_results(results)
    return response


@app.post(
    "/diagnose",
    response_model=DiagnosisResponse,
    tags=["Diagnosis"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def diagnose_event(event: EventInput):
    return _run_diagnosis(event.model_dump())


@app.post(
    "/diagnose/scenario",
    response_model=DiagnosisResponse,
    tags=["Diagnosis"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def diagnose_by_scenario(req: ScenarioRequest):
    if req.name not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _run_diagnosis(SCENARIOS[req.name])


@app.get(
    "/results",
    tags=["History"],
    dependencies=[Depends(RoleChecker(["viewer", "operator", "admin"]))],
)
def get_results(limit: int = 20):
    results = _load_results()
    return {
        "total": len(results),
        "results": results[-limit:][::-1],
    }


@app.delete(
    "/results", tags=["History"], dependencies=[Depends(RoleChecker(["admin"]))]
)
def clear_results():
    _save_results([])
    return {"message": "Results cleared."}


@app.post(
    "/remediate",
    tags=["Remediation"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def remediate(req: RemediateRequest):
    policy = evaluate_policy(req.action)

    if policy == ApprovalMode.AUTO:
        result = _execution_engine.execute(
            action=req.action,
            issue=req.issue,
            sensor=req.sensor,
            severity=req.severity,
            policy=policy.value,
            executed_by=req.executed_by,
        )

        REMEDIATIONS_TOTAL.labels(
            action=req.action, status=result["status"], policy="AUTO"
        ).inc()

        incidents = _load_incidents()
        incident_id = str(uuid.uuid4())
        incidents.append(
            {
                "id": incident_id,
                "issue": req.issue,
                "sensor": req.sensor,
                "severity": req.severity,
                "action": req.action,
                "policy": policy.value,
                "execution": result,
                "detected_at": result["timestamp"],
                "executed_at": result["timestamp"],
                "resolved": result["success"],
                "resolved_at": result["timestamp"] if result["success"] else None,
            }
        )
        _save_incidents(incidents)

        return {
            "mode": "AUTO",
            "incident_id": incident_id,
            "action": req.action,
            "status": result["status"],
            "success": result["success"],
            "details": result["details"],
            "audit_id": result.get("audit_id"),
            "rollback": result.get("rollback"),
            "timestamp": result["timestamp"],
        }
    else:
        approval = _approval_manager.request_approval(
            issue=req.issue,
            action=req.action,
            sensor=req.sensor,
            severity=req.severity,
            policy=policy.value,
        )

        _audit_logger.log(
            issue=req.issue,
            action=req.action,
            status="PENDING",
            executed_by=req.executed_by,
            policy=policy.value,
            sensor=req.sensor,
            severity=req.severity,
            details=f"Approval request created: {approval.id}",
        )

        return {
            "mode": "MANUAL",
            "approval_id": approval.id,
            "action": req.action,
            "status": "PENDING",
            "message": "Action requires human approval.",
            "requested_at": approval.requested_at,
        }


@app.get(
    "/approvals",
    tags=["Remediation"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def list_approvals(pending_only: bool = False):
    requests_list = (
        _approval_manager.list_pending()
        if pending_only
        else _approval_manager.list_all(limit=50)
    )
    return {
        "total": len(requests_list),
        "requests": [r.to_dict() for r in requests_list],
        "stats": _approval_manager.stats(),
    }


@app.post(
    "/approvals/{request_id}/approve",
    tags=["Remediation"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def approve_action(request_id: str, body: ApprovalActionRequest):
    try:
        approval = _approval_manager.approve(request_id, approved_by=body.resolved_by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Request not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    result = _execution_engine.execute(
        action=approval.action,
        issue=approval.issue,
        sensor=approval.sensor,
        severity=approval.severity,
        policy=approval.policy,
        executed_by=body.resolved_by,
    )

    REMEDIATIONS_TOTAL.labels(
        action=approval.action, status=result["status"], policy="MANUAL"
    ).inc()

    incidents = _load_incidents()
    incident_id = str(uuid.uuid4())
    incidents.append(
        {
            "id": incident_id,
            "issue": approval.issue,
            "sensor": approval.sensor,
            "severity": approval.severity,
            "action": approval.action,
            "policy": "MANUAL",
            "approval_id": approval.id,
            "execution": result,
            "detected_at": approval.requested_at,
            "approved_at": approval.resolved_at,
            "executed_at": result["timestamp"],
            "resolved": result["success"],
            "resolved_at": result["timestamp"] if result["success"] else None,
        }
    )
    _save_incidents(incidents)

    return {
        "approval_id": request_id,
        "incident_id": incident_id,
        "action": approval.action,
        "status": result["status"],
        "success": result["success"],
        "details": result["details"],
        "audit_id": result.get("audit_id"),
    }


@app.post(
    "/approvals/{request_id}/reject",
    tags=["Remediation"],
    dependencies=[Depends(RoleChecker(["operator", "admin"]))],
)
def reject_action(request_id: str, body: ApprovalActionRequest):
    try:
        approval = _approval_manager.reject(
            request_id, rejected_by=body.resolved_by, reason=body.notes
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Request not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _audit_logger.log(
        issue=approval.issue,
        action=approval.action,
        status="REJECTED",
        executed_by=body.resolved_by,
        policy=approval.policy,
        sensor=approval.sensor,
        severity=approval.severity,
        details=f"Rejected by {body.resolved_by}. Reason: {body.notes}",
    )

    return {
        "approval_id": request_id,
        "action": approval.action,
        "status": "REJECTED",
        "resolved_by": body.resolved_by,
    }


@app.get(
    "/audit",
    tags=["Governance"],
    dependencies=[Depends(RoleChecker(["viewer", "operator", "admin"]))],
)
def get_audit_log(limit: int = 50):
    entries = _audit_logger.get_log(limit=limit)
    return {
        "total": _audit_logger.count(),
        "limit": limit,
        "entries": entries,
        "stats": _audit_logger.stats(),
    }


@app.get(
    "/incidents",
    tags=["Governance"],
    dependencies=[Depends(RoleChecker(["viewer", "operator", "admin"]))],
)
def get_incidents_timeline(limit: int = 20):
    incidents = _load_incidents()
    return {
        "total": len(incidents),
        "incidents": incidents[-limit:][::-1],
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
