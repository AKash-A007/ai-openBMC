"""
telemetry/collector.py

Collector Layer — Phase B Week 1
Generates telemetry readings (mock, since QEMU Romulus lacks real
hwmon sensors) and persists them to SQLite at a fixed polling interval.

Run standalone:
    python3 collector.py
Or import collect_once() into main.py / a FastAPI background task.
"""

import random
import time
from datetime import datetime, timezone

from database import init_db, insert_readings_batch

# ── Config ────────────────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 5  # use 5s for testing, 30s+ for real monitoring

# Each sensor has a realistic value range and warning/critical thresholds.
# This mirrors how real BMC sensors define thresholds in Redfish
# (UpperThresholdCritical, UpperThresholdNonCritical, etc.)
SENSORS = {
    "CPU_TEMP": {
        "unit": "°C",
        "min": 55,
        "max": 90,
        "warning_at": 80,
        "critical_at": 90,
    },
    "DIMM_TEMP": {
        "unit": "°C",
        "min": 40,
        "max": 75,
        "warning_at": 65,
        "critical_at": 75,
    },
    "FAN_SPEED": {
        "unit": "RPM",
        "min": 2000,
        "max": 6000,
        "warning_at": 2500,  # LOW fan speed is the danger here, not high
        "critical_at": 2200,
        "inverted": True,  # below threshold = bad, not above
    },
    "PSU_VOLTAGE": {
        "unit": "V",
        "min": 11.5,
        "max": 12.5,
        "warning_at": 12.3,
        "critical_at": 12.45,
    },
}


# ── Mock value generation ────────────────────────────────────────────────────


def _generate_value(sensor_name: str) -> float:
    """
    Generate a mock sensor reading.
    Uses random.randint/uniform within each sensor's realistic range.
    """
    spec = SENSORS[sensor_name]
    if sensor_name == "PSU_VOLTAGE":
        return round(random.uniform(spec["min"], spec["max"]), 2)
    return float(random.randint(int(spec["min"]), int(spec["max"])))


def _determine_status(sensor_name: str, value: float) -> str:
    """
    Classify a reading as OK / WARNING / CRITICAL based on sensor thresholds.
    Mirrors Redfish Status.Health semantics (OK / Warning / Critical).
    """
    spec = SENSORS[sensor_name]

    if spec.get("inverted"):
        # Lower value = worse (e.g. fan speed dropping)
        if value <= spec["critical_at"]:
            return "CRITICAL"
        elif value <= spec["warning_at"]:
            return "WARNING"
        return "OK"

    # Normal case — higher value = worse (temp, voltage)
    if value >= spec["critical_at"]:
        return "CRITICAL"
    elif value >= spec["warning_at"]:
        return "WARNING"
    return "OK"


# ── Collection ────────────────────────────────────────────────────────────────


def collect_once() -> list[dict]:
    """
    Collect one reading per sensor, insert into database, and return
    the readings collected.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    readings = []

    for sensor_name in SENSORS:
        value = _generate_value(sensor_name)
        status = _determine_status(sensor_name, value)

        readings.append(
            {
                "timestamp": timestamp,
                "sensor": sensor_name,
                "value": value,
                "status": status,
            }
        )

    insert_readings_batch(readings)
    return readings


def run_forever(interval: int = POLL_INTERVAL_SECONDS) -> None:
    """
    Continuous polling loop — collects telemetry every `interval` seconds.
    This is how real monitoring systems work (Prometheus, Nagios, Zabbix
    all poll on a fixed interval rather than running once).

    Stop with Ctrl+C.
    """
    print(f"[Collector] Starting — polling every {interval}s. Ctrl+C to stop.")
    print(f"[Collector] Sensors: {list(SENSORS.keys())}")

    try:
        while True:
            readings = collect_once()
            for r in readings:
                icon = {"OK": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}[r["status"]]
                print(
                    f"  {icon} {r['timestamp']}  {r['sensor']:<12} "
                    f"{r['value']:>8}  {r['status']}"
                )
            print(
                f"[Collector] {len(readings)} readings stored. "
                f"Sleeping {interval}s...\n"
            )
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[Collector] Stopped by user.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    run_forever(interval=POLL_INTERVAL_SECONDS)
