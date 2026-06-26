"""
automation/audit_logger.py

Phase C Week 4 — Audit Logger

Enterprise systems are required to answer three questions after any
autonomous action:

    Who did what?  When?  Why?

The AuditLogger writes every action + outcome to the audit_log table in
the shared SQLite database so that:

  • Operators can review "what did the system do overnight?"
  • Security teams can audit AI-driven actions for compliance
  • Incident commanders can replay the exact sequence of events
  • Engineers can debug: "why did the system restart that service at 3 AM?"

Table schema
------------
    audit_log(
        id          INTEGER PRIMARY KEY,
        timestamp   TEXT NOT NULL,
        issue       TEXT NOT NULL,   -- e.g. "CPU_OVERHEAT"
        sensor      TEXT NOT NULL,   -- e.g. "CPU0"
        action      TEXT NOT NULL,   -- e.g. "Increase Fan Speed"
        executed_by TEXT NOT NULL,   -- "auto" | "ops-engineer@company.com"
        policy      TEXT NOT NULL,   -- "AUTO" | "MANUAL"
        status      TEXT NOT NULL,   -- "SUCCESS" | "FAILED" | "ROLLED_BACK"
        severity    TEXT NOT NULL,   -- original diagnosis severity
        details     TEXT,            -- free-form notes / error message
        duration_ms REAL             -- wall-clock execution time
    )
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
from database import get_connection, init_db  # noqa: E402

# ── Table bootstrap ───────────────────────────────────────────────────────────


def _ensure_table() -> None:
    init_db()  # creates telemetry + diagnoses tables first
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                issue       TEXT    NOT NULL,
                sensor      TEXT    NOT NULL DEFAULT 'UNKNOWN',
                action      TEXT    NOT NULL,
                executed_by TEXT    NOT NULL DEFAULT 'system',
                policy      TEXT    NOT NULL DEFAULT 'AUTO',
                status      TEXT    NOT NULL,
                severity    TEXT    NOT NULL DEFAULT 'UNKNOWN',
                details     TEXT,
                duration_ms REAL    DEFAULT 0
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log (timestamp);
        """)


# ── AuditLogger ───────────────────────────────────────────────────────────────


class AuditLogger:
    """
    Write and read audit log entries for autonomous remediation actions.

    Usage:
        logger = AuditLogger()

        # Log a successful auto-execution
        logger.log(
            issue       = "CPU_OVERHEAT",
            action      = "Increase Fan Speed",
            status      = "SUCCESS",
            executed_by = "auto",
            policy      = "AUTO",
            sensor      = "CPU0",
            severity    = "CRITICAL",
            details     = "Fan speed increased to 100%",
            duration_ms = 145.2,
        )
    """

    def __init__(self) -> None:
        _ensure_table()

    # ── Write ─────────────────────────────────────────────────────────────────

    def log(
        self,
        issue: str,
        action: str,
        status: str,
        executed_by: str = "auto",
        policy: str = "AUTO",
        sensor: str = "UNKNOWN",
        severity: str = "UNKNOWN",
        details: str = "",
        duration_ms: float = 0.0,
    ) -> int:
        """
        Insert one audit record.  Returns the auto-generated row id.

        status values:
            SUCCESS        — action completed without error
            FAILED         — action raised an error
            ROLLED_BACK    — action failed and was rolled back
            ROLLBACK_FAILED— action failed AND rollback also failed
            NO_ROLLBACK    — action failed, no rollback defined
            PENDING        — action created as MANUAL approval request
            REJECTED       — human rejected the action
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_log
                    (timestamp, issue, sensor, action, executed_by, policy,
                     status, severity, details, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    issue,
                    sensor,
                    action,
                    executed_by,
                    policy,
                    status,
                    severity,
                    details,
                    duration_ms,
                ),
            )
            return cursor.lastrowid

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_log(self, limit: int = 50) -> list[dict]:
        """Return the most recent `limit` audit records, newest first."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_log_for_issue(self, issue: str, limit: int = 20) -> list[dict]:
        """Return audit records for a specific issue / incident."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE issue = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (issue, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        """Total number of audit log entries."""
        with get_connection() as conn:
            return conn.execute("SELECT COUNT(*) as c FROM audit_log").fetchone()["c"]

    def stats(self) -> dict:
        """Aggregate counts by status — useful for the dashboard summary."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT status, COUNT(*) as cnt
                FROM audit_log
                GROUP BY status
                """).fetchall()
        return {row["status"]: row["cnt"] for row in rows}


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger = AuditLogger()

    print("AuditLogger — self-test")

    row_id = logger.log(
        issue="CPU_OVERHEAT",
        action="Increase Fan Speed",
        status="SUCCESS",
        executed_by="auto",
        policy="AUTO",
        sensor="CPU0",
        severity="CRITICAL",
        details="Fan speed set to 100%. CPU temp: 105°C → 82°C",
        duration_ms=145.2,
    )
    print(f"Logged row id: {row_id}")

    row_id2 = logger.log(
        issue="POWER_SUPPLY_FAILURE",
        action="Shutdown System",
        status="PENDING",
        executed_by="ops-engineer@company.com",
        policy="MANUAL",
        sensor="PSU1",
        severity="CRITICAL",
        details="Waiting for human approval",
    )
    print(f"Logged row id: {row_id2}")

    print(f"\nTotal audit entries : {logger.count()}")
    print(f"Stats               : {logger.stats()}")

    print("\nLast 5 entries:")
    for entry in logger.get_log(limit=5):
        print(
            f"  [{entry['timestamp'][:19]}] {entry['action']} "
            f"({entry['status']}) — {entry['issue']}"
        )
