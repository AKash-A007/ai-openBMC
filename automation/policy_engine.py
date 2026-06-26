"""
automation/policy_engine.py

Phase C Week 4 — Policy Engine

The Policy Engine is the governance layer that sits between
a recommendation and its execution.  It answers one question:

    "Given this recommended action, should the system execute it
     automatically, or wait for a human to approve it first?"

Why this matters in enterprise systems
---------------------------------------
Not every remediation is equally safe.  "Increase fan speed" carries
near-zero risk — the worst outcome is slightly louder servers.
"Shutdown System" can take down a production workload.  Treating them
identically (all auto or all manual) produces either:

  • All-manual  → operator fatigue, slow MTTR, defeats the point of AIOps
  • All-auto    → dangerous — any AI hallucination or bad sensor reading
                  can take down production hardware autonomously

A policy table explicitly records which actions an operator has decided
are safe enough to auto-execute.  That decision lives in code, is
version-controlled, and is auditable.  This is the same model used by:

  • Kubernetes admission controllers (auto vs manual scaling)
  • AWS Systems Manager Automation (auto-approval runbooks)
  • PagerDuty AIOps (noise reduction policies)

Policy levels
-------------
  AUTO   — execute immediately, no human in the loop
  MANUAL — create an ApprovalRequest and wait; human approves via API/UI

Adding a new action
-------------------
1. Add a function in action_executor.py
2. Add the action string → function mapping in execution_engine.ACTION_MAP
3. Add an entry here in POLICIES (AUTO or MANUAL)
That's it — the rest of the pipeline picks it up automatically.
"""

from enum import Enum

# ── Policy level enum ─────────────────────────────────────────────────────────


class ApprovalMode(str, Enum):
    AUTO = "AUTO"  # execute immediately
    MANUAL = "MANUAL"  # wait for human approval


# ── Policy table ──────────────────────────────────────────────────────────────
# Keys must match the action strings returned by the diagnosis agent
# (recommendation field) and the keys in ExecutionEngine.ACTION_MAP.
#
# Conservative defaults: anything that only adjusts a parameter is AUTO;
# anything that stops, resets, or cycles hardware is MANUAL.

POLICIES: dict[str, ApprovalMode] = {
    # ── Fan / thermal management (safe — purely additive) ─────────────────
    "Increase Fan Speed": ApprovalMode.AUTO,
    "Reduce Fan Speed": ApprovalMode.AUTO,
    # ── Service-level remediations ────────────────────────────────────────
    "Restart Service": ApprovalMode.AUTO,
    # ── CPU / performance remediations ────────────────────────────────────
    "Reduce CPU Frequency": ApprovalMode.AUTO,
    "Enable CPU Throttling": ApprovalMode.AUTO,
    # ── Memory remediations ───────────────────────────────────────────────
    "Isolate Memory Bank": ApprovalMode.MANUAL,  # data loss risk
    # ── Power remediations (dangerous — require human sign-off) ──────────
    "Power Cycle Node": ApprovalMode.MANUAL,
    "Shutdown System": ApprovalMode.MANUAL,
    "Emergency Shutdown": ApprovalMode.MANUAL,
    # ── Voltage remediations ──────────────────────────────────────────────
    "Check PSU Voltage": ApprovalMode.AUTO,
    "Switch to Redundant PSU": ApprovalMode.MANUAL,
}

# Default for any action string not listed above — err on the side of safety
DEFAULT_POLICY = ApprovalMode.MANUAL


# ── Evaluator ─────────────────────────────────────────────────────────────────


def evaluate_policy(action: str) -> ApprovalMode:
    """
    Return the approval mode for a given action string.

    Examples:
        evaluate_policy("Increase Fan Speed")  → ApprovalMode.AUTO
        evaluate_policy("Shutdown System")     → ApprovalMode.MANUAL
        evaluate_policy("Unknown Action")      → ApprovalMode.MANUAL  (safe default)
    """
    return POLICIES.get(action, DEFAULT_POLICY)


def is_auto(action: str) -> bool:
    """Convenience helper — True if the action can execute without human approval."""
    return evaluate_policy(action) == ApprovalMode.AUTO


def list_auto_actions() -> list[str]:
    """Return all actions currently cleared for automatic execution."""
    return [a for a, p in POLICIES.items() if p == ApprovalMode.AUTO]


def list_manual_actions() -> list[str]:
    """Return all actions that require human approval before execution."""
    return [a for a, p in POLICIES.items() if p == ApprovalMode.MANUAL]


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Policy Engine — self-test")
    print()
    print("AUTO actions (safe to execute immediately):")
    for a in list_auto_actions():
        print(f"  ✅ {a}")
    print()
    print("MANUAL actions (require human approval):")
    for a in list_manual_actions():
        print(f"  🔒 {a}")
    print()
    test_cases = [
        "Increase Fan Speed",
        "Shutdown System",
        "Restart Service",
        "Unknown New Action",
    ]
    print("evaluate_policy() spot-checks:")
    for action in test_cases:
        mode = evaluate_policy(action)
        print(f"  {action:<30} → {mode.value}")
