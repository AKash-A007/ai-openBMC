"""
automation/approval_manager.py

Phase C Week 4 — Approval Manager

Manages the lifecycle of remediation approval requests:

    PENDING  → human has not yet acted
    APPROVED → human approved; execution engine may proceed
    REJECTED → human rejected; action will NOT be executed
    EXPIRED  → PENDING request was not acted on within TTL

For AUTO actions, the Approval Manager is bypassed entirely —
the Execution Engine calls it only to record a "auto-approved" audit event.

For MANUAL actions, the flow is:
    1. Approval Manager creates an ApprovalRequest (UUID, timestamps, status)
    2. The request sits in PENDING until a human calls approve() or reject()
    3. The Execution Engine polls / gets called back when status changes

Storage
-------
Requests are kept in-memory (fast, no I/O) AND persisted to SQLite via the
shared database module so they survive server restarts.  This mirrors how
enterprise ticketing systems (PagerDuty, ServiceNow) work: in-memory for
speed, database for durability.
"""

import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict

# Allow importing from sibling telemetry/ directory
sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
from database import get_connection, init_db  # noqa: E402

# ── Status enum ───────────────────────────────────────────────────────────────


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class ApprovalRequest:
    id: str
    issue: str  # e.g. "CPU_OVERHEAT"
    action: str  # e.g. "Shutdown System"
    sensor: str  # e.g. "CPU0"
    severity: str  # e.g. "CRITICAL"
    policy: str  # "AUTO" | "MANUAL"
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = field(default_factory=lambda: _now())
    resolved_at: str | None = None
    resolved_by: str | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── SQLite persistence helpers ────────────────────────────────────────────────


def _ensure_table() -> None:
    """Create the approval_requests table if it doesn't exist."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_requests (
                id           TEXT PRIMARY KEY,
                issue        TEXT NOT NULL,
                action       TEXT NOT NULL,
                sensor       TEXT NOT NULL,
                severity     TEXT NOT NULL,
                policy       TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL,
                resolved_at  TEXT,
                resolved_by  TEXT,
                notes        TEXT DEFAULT ''
            );
        """
        )


def _persist(req: ApprovalRequest) -> None:
    """Insert or update a request row in SQLite."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO approval_requests
                (id, issue, action, sensor, severity, policy, status,
                 requested_at, resolved_at, resolved_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                req.id,
                req.issue,
                req.action,
                req.sensor,
                req.severity,
                req.policy,
                req.status.value,
                req.requested_at,
                req.resolved_at,
                req.resolved_by,
                req.notes,
            ),
        )


def _load_all_from_db() -> list[ApprovalRequest]:
    """Load all approval requests from SQLite (used on startup)."""
    try:
        _ensure_table()
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM approval_requests ORDER BY requested_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            req = ApprovalRequest(
                id=row["id"],
                issue=row["issue"],
                action=row["action"],
                sensor=row["sensor"],
                severity=row["severity"],
                policy=row["policy"],
                status=ApprovalStatus(row["status"]),
                requested_at=row["requested_at"],
                resolved_at=row["resolved_at"],
                resolved_by=row["resolved_by"],
                notes=row["notes"] or "",
            )
            result.append(req)
        return result
    except Exception:
        return []


# ── ApprovalManager ───────────────────────────────────────────────────────────


class ApprovalManager:
    """
    Singleton-friendly manager for all approval requests.

    Usage:
        mgr = ApprovalManager()
        req = mgr.request_approval(issue="CPU_OVERHEAT", action="Shutdown System",
                                   sensor="CPU0", severity="CRITICAL", policy="MANUAL")
        # later…
        mgr.approve(req.id, approved_by="ops-engineer@company.com")
    """

    def __init__(self) -> None:
        _ensure_table()
        # In-memory index keyed by request ID
        self._store: dict[str, ApprovalRequest] = {r.id: r for r in _load_all_from_db()}

    # ── Create ────────────────────────────────────────────────────────────────

    def request_approval(
        self,
        issue: str,
        action: str,
        sensor: str = "UNKNOWN",
        severity: str = "UNKNOWN",
        policy: str = "MANUAL",
        notes: str = "",
    ) -> ApprovalRequest:
        """
        Create a new approval request and persist it.
        Returns the new ApprovalRequest object.
        """
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            issue=issue,
            action=action,
            sensor=sensor,
            severity=severity,
            policy=policy,
            notes=notes,
        )
        self._store[req.id] = req
        _persist(req)
        return req

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._store.get(request_id)

    def list_all(self, limit: int = 50) -> list[ApprovalRequest]:
        """Return all requests, newest first."""
        return sorted(
            self._store.values(),
            key=lambda r: r.requested_at,
            reverse=True,
        )[:limit]

    def list_pending(self) -> list[ApprovalRequest]:
        """Return only PENDING requests — the queue a human operator sees."""
        return [r for r in self._store.values() if r.status == ApprovalStatus.PENDING]

    # ── Resolve ───────────────────────────────────────────────────────────────

    def approve(self, request_id: str, approved_by: str = "system") -> ApprovalRequest:
        """
        Mark a request as APPROVED.
        The Execution Engine checks this before running an action.
        """
        req = self._store.get(request_id)
        if req is None:
            raise KeyError(f"ApprovalRequest '{request_id}' not found")
        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is already {req.status.value}")
        req.status = ApprovalStatus.APPROVED
        req.resolved_at = _now()
        req.resolved_by = approved_by
        _persist(req)
        return req

    def reject(
        self, request_id: str, rejected_by: str = "system", reason: str = ""
    ) -> ApprovalRequest:
        """Mark a request as REJECTED — action will not execute."""
        req = self._store.get(request_id)
        if req is None:
            raise KeyError(f"ApprovalRequest '{request_id}' not found")
        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is already {req.status.value}")
        req.status = ApprovalStatus.REJECTED
        req.resolved_at = _now()
        req.resolved_by = rejected_by
        req.notes = reason
        _persist(req)
        return req

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        all_reqs = list(self._store.values())
        return {
            "total": len(all_reqs),
            "pending": sum(1 for r in all_reqs if r.status == ApprovalStatus.PENDING),
            "approved": sum(1 for r in all_reqs if r.status == ApprovalStatus.APPROVED),
            "rejected": sum(1 for r in all_reqs if r.status == ApprovalStatus.REJECTED),
        }


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mgr = ApprovalManager()

    print("Approval Manager — self-test")
    print()

    # Create a MANUAL request
    req = mgr.request_approval(
        issue="CPU_OVERHEAT",
        action="Shutdown System",
        sensor="CPU0",
        severity="CRITICAL",
        policy="MANUAL",
    )
    print(f"Created request : {req.id[:8]}…  status={req.status.value}")

    # Approve it
    mgr.approve(req.id, approved_by="ops-engineer")
    req_after = mgr.get(req.id)
    status_str = req_after.status.value if req_after else "None"
    print(f"After approve   : status={status_str}")

    # Create and reject another
    req2 = mgr.request_approval(
        issue="FAN_FAULT",
        action="Shutdown System",
        sensor="FAN_3",
        severity="WARNING",
        policy="MANUAL",
    )
    mgr.reject(req2.id, rejected_by="ops-lead", reason="Non-critical — monitor first")
    req2_after = mgr.get(req2.id)
    status_str2 = req2_after.status.value if req2_after else "None"
    print(f"After reject    : status={status_str2}")

    print()
    print("Stats:", mgr.stats())
