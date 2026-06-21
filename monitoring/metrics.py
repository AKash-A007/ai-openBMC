"""
monitoring/metrics.py

Phase B Week 4 — Metrics Layer

This file answers the simple aggregate questions an operator asks
before diving into raw trend graphs: "what's the average been," "what's
the worst it's gotten," "how healthy is the fleet right now." These are
deliberately simple — single numbers, not time-series — because they're
the first thing a dashboard's top row shows, before any chart renders.

Every function here is a thin, read-only wrapper combining Week 1's
query layer with Week 3's prediction layer. This file owns NO new
calculation logic of its own beyond simple aggregation (avg/max) — it
composes existing building blocks rather than duplicating their logic,
the same separation-of-concerns principle applied to database.py owning
all SQL.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "analytics"))

from query import get_sensor_history, get_all_sensor_names   # noqa: E402
from health_score import calculate_fleet_health               # noqa: E402
from predictor import predict_failure                          # noqa: E402


# ── Single-sensor metrics ──────────────────────────────────────────────────────

def get_average_value(sensor: str, limit: int = 200) -> float | None:
    """Mean of a sensor's recent readings. None if no data exists yet."""
    values = get_sensor_history(sensor, limit=limit)
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def get_peak_value(sensor: str, limit: int = 200) -> float | None:
    """Highest recent reading for a sensor. None if no data exists yet."""
    values = get_sensor_history(sensor, limit=limit)
    if not values:
        return None
    return max(values)


def get_min_value(sensor: str, limit: int = 200) -> float | None:
    """Lowest recent reading for a sensor. None if no data exists yet."""
    values = get_sensor_history(sensor, limit=limit)
    if not values:
        return None
    return min(values)


def get_sensor_metrics(sensor: str, limit: int = 200) -> dict:
    """
    Combined avg/max/min snapshot for one sensor — the row of numbers
    a dashboard card would show under a sensor's name.
    """
    values = get_sensor_history(sensor, limit=limit)
    if not values:
        return {"sensor": sensor, "count": 0, "message": "No data yet."}

    return {
        "sensor": sensor,
        "count" : len(values),
        "avg"   : round(sum(values) / len(values), 2),
        "max"   : max(values),
        "min"   : min(values),
        "latest": values[-1],
    }


# ── Fleet-wide aggregate metrics ───────────────────────────────────────────────

def get_average_health(limit: int = 200) -> float | None:
    """
    Overall fleet health — delegates entirely to health_score.py's
    calculate_fleet_health() rather than recomputing the averaging
    logic here. Returns None if no sensors have enough data yet.
    """
    sensors = get_all_sensor_names()
    if not sensors:
        return None
    fleet = calculate_fleet_health(sensors, limit=limit)
    return fleet["overall_health_score"]


def get_failure_rate(limit: int = 200) -> dict:
    """
    Across every sensor currently tracked, what fraction are at
    elevated (MEDIUM or HIGH) failure risk right now?

    Returns:
        {
            "total_sensors": 4,
            "at_risk_sensors": 1,
            "failure_rate": 0.25,
            "at_risk": ["CPU_TEMP"]
        }

    This is distinct from any single sensor's failure_probability —
    it's a fleet-wide proportion, answering "how much of my system is
    currently concerning" rather than "how worried should I be about
    this one sensor."
    """
    sensors = get_all_sensor_names()
    if not sensors:
        return {"total_sensors": 0, "at_risk_sensors": 0, "failure_rate": 0.0, "at_risk": []}

    at_risk = []
    for sensor in sensors:
        prediction = predict_failure(sensor, limit=limit)
        if prediction.get("risk") in ("MEDIUM", "HIGH"):
            at_risk.append(sensor)

    return {
        "total_sensors"  : len(sensors),
        "at_risk_sensors": len(at_risk),
        "failure_rate"   : round(len(at_risk) / len(sensors), 3),
        "at_risk"        : at_risk,
    }


def get_system_metrics(limit: int = 200) -> dict:
    """
    The single call a dashboard's top row would make to populate
    every headline number in one shot — combines fleet health,
    failure rate, and per-sensor snapshots.

    Returns:
        {
            "overall_health": 86,
            "overall_risk": "MEDIUM",
            "failure_rate": 0.25,
            "at_risk_sensors": ["CPU_TEMP"],
            "sensors": {
                "CPU_TEMP": {"avg": 82.6, "max": 92.0, "min": 70.0, "latest": 91.0},
                ...
            }
        }
    """
    sensors = get_all_sensor_names()
    fleet   = calculate_fleet_health(sensors, limit=limit) if sensors else {
        "overall_health_score": None, "overall_risk": "UNKNOWN"
    }
    rate    = get_failure_rate(limit=limit)

    return {
        "overall_health" : fleet["overall_health_score"],
        "overall_risk"   : fleet["overall_risk"],
        "failure_rate"   : rate["failure_rate"],
        "at_risk_sensors": rate["at_risk"],
        "sensors"        : {s: get_sensor_metrics(s, limit=limit) for s in sensors},
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 50)
    print("Demo: per-sensor metrics")
    print("=" * 50)

    sensors = get_all_sensor_names()
    if not sensors:
        print("No sensors found — run telemetry/collector.py first.")
    else:
        for sensor in sensors:
            print(f"\n{sensor}:")
            print(json.dumps(get_sensor_metrics(sensor), indent=2))

        print()
        print("=" * 50)
        print("Demo: fleet-wide system metrics")
        print("=" * 50)
        print(json.dumps(get_system_metrics(), indent=2))