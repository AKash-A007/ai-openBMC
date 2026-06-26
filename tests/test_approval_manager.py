import pytest
from automation.approval_manager import ApprovalManager, ApprovalStatus
from telemetry.database import get_connection


def test_approval_lifecycle():
    mgr = ApprovalManager()

    # Wipe approval_requests table for tests
    with get_connection() as conn:
        conn.execute("DELETE FROM approval_requests")

    req = mgr.request_approval(
        issue="CPU_OVERHEAT",
        action="Power Cycle Node",
        sensor="CPU0",
        severity="CRITICAL",
    )

    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING
    assert req.action == "Power Cycle Node"

    pending = mgr.list_pending()
    assert len(pending) == 1
    assert pending[0].id == req.id

    # Approve request
    approved = mgr.approve(req.id, approved_by="admin-user")
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.resolved_by == "admin-user"

    # Verify no longer pending
    assert len(mgr.list_pending()) == 0

    # Test reject request
    req2 = mgr.request_approval(
        issue="FAN_FAULT",
        action="Isolate Memory Bank",
        sensor="FAN_1",
        severity="WARNING",
    )

    rejected = mgr.reject(req2.id, rejected_by="admin-user", reason="Faulty prediction")
    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.resolved_by == "admin-user"
    assert rejected.notes == "Faulty prediction"
