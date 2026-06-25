"""
automation/execution_engine.py

Phase C Week 4 — Execution Engine

The Execution Engine is the central coordinator of the automation pipeline.
It receives an approved action and:

  1. Looks up the correct executor function in ACTION_MAP
  2. Calls the executor with the full context dict
  3. Handles success → audit log entry "SUCCESS"
  4. Handles failure → calls RollbackManager → audit log entry accordingly
  5. Returns a structured ExecutionResult

Pipeline position:
    Policy Engine → Approval Manager → [HERE] → Action Executor → Rollback? → Audit Logger

Design
------
Separating "what to do" (action_executor.py) from "orchestration"
(this file) keeps each piece testable in isolation.  This is the
Command Pattern: the ENGINE doesn't know HOW to increase fan speed —
it just knows to call increase_fan_speed() and handle the result.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent))

from action_executor import (
    increase_fan_speed,
    reduce_fan_speed,
    restart_service,
    reduce_cpu_frequency,
    enable_cpu_throttling,
    isolate_memory_bank,
    power_cycle_node,
    shutdown_system,
    emergency_shutdown,
    check_psu_voltage,
    switch_to_redundant_psu,
)
from rollback_manager import RollbackManager
from audit_logger     import AuditLogger


# ── Action map ────────────────────────────────────────────────────────────────
# Maps the action string (from agent.diagnose recommendation field) to
# the Python callable that actually performs the action.
#
# IMPORTANT: keys must exactly match the strings in policy_engine.POLICIES
# and the recommendation strings your LLM returns.

ACTION_MAP: dict[str, callable] = {
    "Increase Fan Speed"      : increase_fan_speed,
    "Reduce Fan Speed"        : reduce_fan_speed,
    "Restart Service"         : restart_service,
    "Reduce CPU Frequency"    : reduce_cpu_frequency,
    "Enable CPU Throttling"   : enable_cpu_throttling,
    "Isolate Memory Bank"     : isolate_memory_bank,
    "Power Cycle Node"        : power_cycle_node,
    "Shutdown System"         : shutdown_system,
    "Emergency Shutdown"      : emergency_shutdown,
    "Check PSU Voltage"       : check_psu_voltage,
    "Switch to Redundant PSU" : switch_to_redundant_psu,
}


# ── ExecutionEngine ───────────────────────────────────────────────────────────

class ExecutionEngine:
    """
    Route an approved action through to execution and audit.

    Usage:
        engine = ExecutionEngine()
        result = engine.execute(
            action      = "Increase Fan Speed",
            issue       = "CPU_OVERHEAT",
            sensor      = "CPU0",
            severity    = "CRITICAL",
            policy      = "AUTO",
            executed_by = "auto",
        )
        print(result["status"])  # SUCCESS | FAILED | ROLLED_BACK | NO_ROLLBACK
    """

    def __init__(self) -> None:
        self._rollback = RollbackManager()
        self._audit    = AuditLogger()

    # ── Execute ───────────────────────────────────────────────────────────────

    def execute(
        self,
        action      : str,
        issue       : str,
        sensor      : str  = "UNKNOWN",
        severity    : str  = "UNKNOWN",
        policy      : str  = "AUTO",
        executed_by : str  = "auto",
        metadata    : dict | None = None,
    ) -> dict:
        """
        Execute an approved remediation action.

        Returns:
            {
                "action"      : "Increase Fan Speed",
                "status"      : "SUCCESS" | "FAILED" | "ROLLED_BACK" | ...,
                "success"     : True | False,
                "executed_by" : "auto",
                "policy"      : "AUTO",
                "details"     : "...",
                "rollback"    : {…} | None,
                "audit_id"    : 42,
                "timestamp"   : "2026-06-22T15:31:00Z",
            }
        """
        # Build context for the executor function
        context = {
            "issue"   : issue,
            "sensor"  : sensor,
            "severity": severity,
            **(metadata or {}),
        }

        # Look up the executor
        executor = ACTION_MAP.get(action)
        if executor is None:
            msg = (
                f"No executor registered for action '{action}'. "
                f"Available: {list(ACTION_MAP.keys())}"
            )
            print(f"[ExecutionEngine] ERROR: {msg}")
            audit_id = self._audit.log(
                issue=issue, action=action, status="FAILED",
                executed_by=executed_by, policy=policy,
                sensor=sensor, severity=severity, details=msg,
            )
            return self._make_result(
                action=action, status="FAILED", success=False,
                details=msg, rollback=None,
                executed_by=executed_by, policy=policy, audit_id=audit_id,
            )

        # ── Run the action ────────────────────────────────────────────────────
        print(f"[ExecutionEngine] Starting: '{action}' | issue={issue} | by={executed_by}")
        exec_result = executor(context)
        duration_ms = exec_result.get("duration_ms", 0)

        if exec_result["success"]:
            # ── Happy path ────────────────────────────────────────────────────
            audit_id = self._audit.log(
                issue=issue, action=action, status="SUCCESS",
                executed_by=executed_by, policy=policy,
                sensor=sensor, severity=severity,
                details=exec_result["details"], duration_ms=duration_ms,
            )
            return self._make_result(
                action=action, status="SUCCESS", success=True,
                details=exec_result["details"], rollback=None,
                executed_by=executed_by, policy=policy, audit_id=audit_id,
                duration_ms=duration_ms,
            )

        else:
            # ── Action failed → attempt rollback ──────────────────────────────
            print(f"[ExecutionEngine] Action failed — attempting rollback…")
            rb_result = self._rollback.rollback(action, context)

            final_status = {
                "ROLLED_BACK"     : "ROLLED_BACK",
                "ROLLBACK_FAILED" : "ROLLBACK_FAILED",
                "NO_ROLLBACK"     : "NO_ROLLBACK",
            }.get(rb_result["status"], "FAILED")

            audit_id = self._audit.log(
                issue=issue, action=action, status=final_status,
                executed_by=executed_by, policy=policy,
                sensor=sensor, severity=severity,
                details=f"{exec_result['details']} | Rollback: {rb_result['details']}",
                duration_ms=duration_ms,
            )
            return self._make_result(
                action=action, status=final_status, success=False,
                details=exec_result["details"], rollback=rb_result,
                executed_by=executed_by, policy=policy, audit_id=audit_id,
                duration_ms=duration_ms,
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_result(
        action      : str,
        status      : str,
        success     : bool,
        details     : str,
        rollback    : dict | None,
        executed_by : str,
        policy      : str,
        audit_id    : int,
        duration_ms : float = 0.0,
    ) -> dict:
        return {
            "action"      : action,
            "status"      : status,
            "success"     : success,
            "details"     : details,
            "rollback"    : rollback,
            "executed_by" : executed_by,
            "policy"      : policy,
            "audit_id"    : audit_id,
            "duration_ms" : duration_ms,
            "timestamp"   : datetime.now(timezone.utc).isoformat(),
        }

    def list_supported_actions(self) -> list[str]:
        """Return all action strings this engine can execute."""
        return list(ACTION_MAP.keys())


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = ExecutionEngine()

    print("ExecutionEngine — self-test")
    print(f"Supported actions: {engine.list_supported_actions()}")
    print()

    result = engine.execute(
        action      = "Increase Fan Speed",
        issue       = "CPU_OVERHEAT",
        sensor      = "CPU0",
        severity    = "CRITICAL",
        policy      = "AUTO",
        executed_by = "auto",
    )
    print(f"\nResult status : {result['status']}")
    print(f"Audit row id  : {result['audit_id']}")
    print(f"Details       : {result['details']}")
