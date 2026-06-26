"""
automation/action_executor.py

Phase C Week 4 — Action Executor

Contains one function per remediable action.  Each function:

  1. Accepts a context dict (issue, sensor, severity, metadata)
  2. Simulates (or in production, performs) the actual hardware operation
  3. Returns an ActionResult dict with success/failure + details

Why mock first?
---------------
In real production you would:
  - Fan speed  → Redfish PATCH /redfish/v1/Chassis/{id}/Thermal
  - Service    → OpenBMC D-Bus call via busctl / dbus-send
  - Power cycle → IPMI raw command or Redfish POST to ResetType

Mocking first lets you:
  1. Build and test the full pipeline (policy → approve → execute → audit)
     without needing real hardware
  2. Drop in the real Redfish/IPMI calls later with zero changes to the
     policy engine, approval manager, or audit logger
  3. Demonstrate the architecture in interviews without hardware

Each function is intentionally small and focused.  The Execution Engine
maps action strings → these functions; it doesn't care about internals.
"""

import time
import random
from datetime import datetime, timezone

# ── Result shape ─────────────────────────────────────────────────────────────


def _make_result(
    action: str,
    success: bool,
    details: str,
    context: dict,
    duration_ms: float,
) -> dict:
    return {
        "action": action,
        "success": success,
        "status": "SUCCESS" if success else "FAILED",
        "details": details,
        "sensor": context.get("sensor", "UNKNOWN"),
        "issue": context.get("issue", "UNKNOWN"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 2),
    }


def _simulate(action_name: str, context: dict, delay: float = 0.1) -> dict:
    """
    Generic simulation wrapper — all mock actions call this.
    Introduces a realistic delay and a small random failure rate
    (5%) to let the rollback machinery be exercised.
    """
    start = time.time()
    print(
        f"[ActionExecutor] Executing: {action_name} | "
        f"sensor={context.get('sensor')} | issue={context.get('issue')}"
    )

    time.sleep(delay)  # simulate real I/O latency

    # 5% random failure rate so we can demo rollback
    force_fail = context.get("_force_fail", False)
    failed = force_fail or (random.random() < 0.05)

    elapsed = (time.time() - start) * 1000

    if failed:
        details = (
            f"[MOCK] {action_name} failed — "
            f"simulated hardware error on {context.get('sensor', '?')}"
        )
        print(f"[ActionExecutor] FAILED: {details}")
        return _make_result(action_name, False, details, context, elapsed)
    else:
        details = (
            f"[MOCK] {action_name} executed successfully on "
            f"{context.get('sensor', '?')} "
            f"(issue: {context.get('issue', '?')})"
        )
        print(f"[ActionExecutor] SUCCESS: {details}")
        return _make_result(action_name, True, details, context, elapsed)


# ── Fan / thermal actions ─────────────────────────────────────────────────────


def increase_fan_speed(context: dict) -> dict:
    """
    Increase fan speed to maximum to cool an overheating component.

    Real implementation:
        PATCH /redfish/v1/Chassis/{chassis_id}/Thermal
        Body: {"Fans": [{"MemberId": "0", "Reading": 10000}]}
    """
    return _simulate("Increase Fan Speed", context, delay=0.15)


def reduce_fan_speed(context: dict) -> dict:
    """Reduce fan speed after thermal conditions normalise."""
    return _simulate("Reduce Fan Speed", context, delay=0.10)


# ── Service actions ───────────────────────────────────────────────────────────


def restart_service(context: dict) -> dict:
    """
    Restart a failing OpenBMC service.

    Real implementation:
        busctl call org.freedesktop.systemd1 \
            /org/freedesktop/systemd1/unit/<service>_2eservice \
            org.freedesktop.systemd1.Unit RestartUnit ss "replace"
    """
    return _simulate("Restart Service", context, delay=0.80)


# ── CPU / performance actions ─────────────────────────────────────────────────


def reduce_cpu_frequency(context: dict) -> dict:
    """
    Lower CPU max frequency to reduce thermal load.

    Real implementation:
        Write to /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq
        or via IPMI: ipmitool raw 0x30 0x0D 0x00 0x04
    """
    return _simulate("Reduce CPU Frequency", context, delay=0.20)


def enable_cpu_throttling(context: dict) -> dict:
    """Enable hardware-level thermal throttling as an emergency cooling measure."""
    return _simulate("Enable CPU Throttling", context, delay=0.20)


# ── Memory actions ────────────────────────────────────────────────────────────


def isolate_memory_bank(context: dict) -> dict:
    """
    Take a faulty DIMM bank offline to prevent data corruption.

    Real implementation:
        OpenBMC memory management via D-Bus DIMM object
    """
    return _simulate("Isolate Memory Bank", context, delay=0.50)


# ── Power actions ─────────────────────────────────────────────────────────────


def power_cycle_node(context: dict) -> dict:
    """
    Gracefully power-cycle the node.

    Real implementation:
        POST /redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset
        Body: {"ResetType": "GracefulRestart"}
    """
    return _simulate("Power Cycle Node", context, delay=1.20)


def shutdown_system(context: dict) -> dict:
    """
    Emergency graceful shutdown.

    Real implementation:
        POST /redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset
        Body: {"ResetType": "GracefulShutdown"}
    """
    return _simulate("Shutdown System", context, delay=2.00)


def emergency_shutdown(context: dict) -> dict:
    """
    Immediate power-off — last resort for hardware protection.

    Real implementation:
        POST /redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset
        Body: {"ResetType": "ForceOff"}
    """
    return _simulate("Emergency Shutdown", context, delay=0.50)


# ── PSU / voltage actions ─────────────────────────────────────────────────────


def check_psu_voltage(context: dict) -> dict:
    """
    Read PSU voltage rails and log them for operator review.

    Real implementation:
        GET /redfish/v1/Chassis/{id}/Power  → parse Voltages array
    """
    return _simulate("Check PSU Voltage", context, delay=0.30)


def switch_to_redundant_psu(context: dict) -> dict:
    """
    Fail over to the redundant PSU when primary fails.

    Real implementation:
        Vendor-specific BMC OEM command
    """
    return _simulate("Switch to Redundant PSU", context, delay=0.60)


# ── Rollback actions (called by rollback_manager) ────────────────────────────


def restore_fan_speed(context: dict) -> dict:
    """Rollback for Increase Fan Speed — return to default speed."""
    return _simulate("Restore Fan Speed", context, delay=0.10)


def restore_service_state(context: dict) -> dict:
    """Rollback for Restart Service — attempt to restore previous state."""
    return _simulate("Restore Service State", context, delay=0.40)


def restore_cpu_frequency(context: dict) -> dict:
    """Rollback for Reduce CPU Frequency — restore baseline frequency."""
    return _simulate("Restore CPU Frequency", context, delay=0.15)


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("ActionExecutor — self-test")
    ctx = {"sensor": "CPU0", "issue": "CPU_OVERHEAT", "severity": "CRITICAL"}

    result = increase_fan_speed(ctx)
    print(f"\nResult: {result}")

    result2 = restart_service({"sensor": "bmcweb", "issue": "SERVICE_CRASH"})
    print(f"\nResult: {result2}")
