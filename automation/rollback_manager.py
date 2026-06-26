"""
automation/rollback_manager.py

Phase C Week 4 — Rollback Manager

When an executed action fails (or produces worse results than before),
the system needs to undo it.  The Rollback Manager handles this.

Design principle: every action with side-effects should have a known
inverse.  We capture that mapping here as ROLLBACKS.

Why rollback matters
--------------------
Without rollback, a failed "Restart Service" leaves the service in an
inconsistent state.  With rollback, the system can attempt to restore
the previous state automatically — and log the rollback attempt in the
audit trail regardless of whether it succeeds.

This is the same concept as:
  • Database transactions (ROLLBACK on error)
  • Kubernetes deployment rollback (kubectl rollout undo)
  • Feature flags (kill switch)

Rollback limitations
--------------------
Not every action is reversible.  "Emergency Shutdown" has no undo —
the system is off.  For those, ROLLBACKS maps to None and the manager
simply logs a "no rollback available" audit event.
"""

import sys
from pathlib import Path
from typing import Callable

sys.path.append(str(Path(__file__).resolve().parent))
from action_executor import (
    restore_fan_speed,
    restore_service_state,
    restore_cpu_frequency,
)

# ── Rollback table ────────────────────────────────────────────────────────────
# Maps: original action string → rollback executor function (or None)

ROLLBACKS: dict[str, Callable | None] = {
    "Increase Fan Speed": restore_fan_speed,
    "Reduce Fan Speed": restore_fan_speed,
    "Restart Service": restore_service_state,
    "Reduce CPU Frequency": restore_cpu_frequency,
    "Enable CPU Throttling": restore_cpu_frequency,
    "Isolate Memory Bank": None,  # data already affected — no safe undo
    "Power Cycle Node": None,  # node is rebooting — can't undo
    "Shutdown System": None,  # system is off
    "Emergency Shutdown": None,  # system is off
    "Check PSU Voltage": None,  # read-only — nothing to undo
    "Switch to Redundant PSU": None,  # PSU switch — manual reversal required
}


# ── RollbackManager ───────────────────────────────────────────────────────────


class RollbackManager:
    """
    Attempt a rollback for a failed action.

    Usage:
        rbm = RollbackManager()
        result = rbm.rollback("Increase Fan Speed", context={"sensor": "CPU0", ...})
        # result["success"] → True/False
        # result["status"]  → "ROLLED_BACK" | "ROLLBACK_FAILED" | "NO_ROLLBACK"
    """

    def rollback(self, action: str, context: dict) -> dict:
        """
        Try to roll back a previously executed action.

        Returns a result dict with:
            status  — "ROLLED_BACK" | "ROLLBACK_FAILED" | "NO_ROLLBACK"
            details — human-readable explanation
        """
        rollback_fn = ROLLBACKS.get(action)

        if rollback_fn is None:
            msg = (
                f"No rollback defined for '{action}' — "
                "manual operator intervention required."
            )
            print(f"[Rollback] {msg}")
            return {
                "original_action": action,
                "status": "NO_ROLLBACK",
                "success": False,
                "details": msg,
            }

        print(f"[Rollback] Attempting rollback for '{action}'…")
        try:
            rb_result = rollback_fn(context)
            if rb_result["success"]:
                return {
                    "original_action": action,
                    "rollback_action": rb_result["action"],
                    "status": "ROLLED_BACK",
                    "success": True,
                    "details": rb_result["details"],
                    "duration_ms": rb_result.get("duration_ms", 0),
                }
            else:
                return {
                    "original_action": action,
                    "rollback_action": rb_result["action"],
                    "status": "ROLLBACK_FAILED",
                    "success": False,
                    "details": rb_result["details"],
                }
        except Exception as e:
            msg = f"Rollback executor raised an exception: {e}"
            print(f"[Rollback] ERROR: {msg}")
            return {
                "original_action": action,
                "status": "ROLLBACK_FAILED",
                "success": False,
                "details": msg,
            }

    def has_rollback(self, action: str) -> bool:
        """True if a rollback function is defined for this action."""
        return ROLLBACKS.get(action) is not None

    def list_reversible(self) -> list[str]:
        """Return all actions that have a defined rollback."""
        return [a for a, fn in ROLLBACKS.items() if fn is not None]


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rbm = RollbackManager()

    print("Rollback Manager — self-test")
    print()
    print("Reversible actions:")
    for a in rbm.list_reversible():
        print(f"  ↩️  {a}")
    print()

    ctx = {"sensor": "CPU0", "issue": "CPU_OVERHEAT"}

    r1 = rbm.rollback("Increase Fan Speed", ctx)
    print(f"Rollback 'Increase Fan Speed' → {r1['status']}")

    r2 = rbm.rollback("Shutdown System", ctx)
    print(f"Rollback 'Shutdown System'    → {r2['status']}")
