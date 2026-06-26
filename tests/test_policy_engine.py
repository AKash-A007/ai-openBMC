from automation.policy_engine import evaluate_policy, ApprovalMode

def test_evaluate_policy():
    # Test known AUTO policies
    assert evaluate_policy("Increase Fan Speed") == ApprovalMode.AUTO
    assert evaluate_policy("Restart Service") == ApprovalMode.AUTO
    
    # Test known MANUAL policies
    assert evaluate_policy("Power Cycle Node") == ApprovalMode.MANUAL
    assert evaluate_policy("Shutdown System") == ApprovalMode.MANUAL
    
    # Test unknown actions default to MANUAL
    assert evaluate_policy("Invalid Action Name") == ApprovalMode.MANUAL
