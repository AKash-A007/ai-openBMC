"""
automation/

Phase C Week 4 — Autonomous Remediation & Governance

This package implements the full post-diagnosis pipeline:

    Diagnosis Result
         ↓
    Policy Engine       ← should we auto-execute or wait for approval?
         ↓
    Approval Manager    ← track approval state (AUTO bypasses, MANUAL waits)
         ↓
    Execution Engine    ← route action string → concrete executor function
         ↓
    Action Executor     ← mock OpenBMC actions (fan speed, service restart…)
         ↓
    Audit Logger        ← write every action + outcome to SQLite

    Rollback Manager is called by the Execution Engine if an action fails.
"""

from .policy_engine    import evaluate_policy, POLICIES, ApprovalMode
from .approval_manager import ApprovalManager, ApprovalStatus
from .execution_engine import ExecutionEngine
from .audit_logger     import AuditLogger

__all__ = [
    "POLICIES",
    "ApprovalMode",
    "ApprovalManager",
    "ApprovalStatus",
    "ExecutionEngine",
    "AuditLogger",
    "evaluate_policy",
]
