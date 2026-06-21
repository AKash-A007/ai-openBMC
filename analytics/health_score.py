"""
analytics/health_score.py

Phase B Week 3 — Health Scoring Layer

Why a health score, separate from failure_probability?
    failure_probability (0.0-1.0) is what the prediction model outputs.
    It's correct and useful, but it's not how humans operating a fleet
    of machines think about server state day to day. Nobody walks past
    a rack and says "that node is at 0.23 probability" — every
    enterprise monitoring tool (Dell OpenManage, HPE iLO, VMware,
    Datadog, Splunk) converts risk into a single 0-100 "health" number
    because it's immediately legible at a glance across a dashboard
    full of machines.

    health_score and failure_probability are two views of the same
    underlying risk — this file is purely a presentation-layer
    transform, not a second independent model. That's an important
    distinction: if you ever need to change *how risk is computed*,
    that change belongs in predictor.py, not here. This file only
    decides how that risk is *displayed*.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))

from predictor import predict_failure, predict_all   # noqa: E402


# ── Config ────────────────────────────────────────────────────────────────────

STARTING_SCORE = 100

# Penalty weights — tuned so a single CRITICAL threshold breach plus a
# handful of anomalies drives score down into the "at risk" band without
# a single anomaly alone tanking the score to zero (one outlier shouldn't
# read as "the machine is dying").
ANOMALY_PENALTY_PER_COUNT = 10
ANOMALY_PENALTY_CAP       = 40     # don't let anomaly count alone zero out the score
TREND_PENALTY_MULTIPLIER  = 5      # per unit of trend factor contribution
PROBABILITY_PENALTY_SCALE = 60     # failure_probability=1.0 → -60 points


# ── Core scoring ───────────────────────────────────────────────────────────────

def calculate_health_score(sensor: str, limit: int = 200) -> dict:
    """
    Combine failure prediction into a single human-friendly 0-100 score.

    Formula (starting from 100):
        - anomaly_penalty   = min(anomaly_factor-derived count * 10, 40)
        - trend_penalty     = trend contributing factor * 5
        - probability_penalty = failure_probability * 60

    Returns:
        {
            "sensor": "CPU_TEMP",
            "health_score": 62,
            "failure_probability": 0.78,
            "risk": "HIGH",
            "penalties": {
                "anomaly": 30,
                "trend": 1,
                "probability": 46.8
            }
        }
    """
    prediction = predict_failure(sensor, limit=limit)

    if "message" in prediction:
        # Not enough data yet — report neutral, not falsely healthy or unhealthy
        return {
            "sensor"             : sensor,
            "health_score"       : None,
            "failure_probability": 0.0,
            "risk"               : "UNKNOWN",
            "message"            : prediction["message"],
        }

    factors = prediction["contributing_factors"]

    # Anomaly contribution to the rule-based probability was already
    # capped at 0.3 in predictor.py — scale it back up to an anomaly
    # "count-equivalent" for an intuitive penalty (anomaly_factor of 0.3
    # means "at or above the danger count", so apply the full per-anomaly
    # penalty cap)
    anomaly_penalty = round(min(
        (factors["anomaly_count"] / 0.3) * ANOMALY_PENALTY_PER_COUNT,
        ANOMALY_PENALTY_CAP,
    ), 2) if factors["anomaly_count"] > 0 else 0.0

    trend_penalty = round(factors["trend"] * TREND_PENALTY_MULTIPLIER, 2)

    probability_penalty = round(
        prediction["failure_probability"] * PROBABILITY_PENALTY_SCALE, 2
    )

    total_penalty = anomaly_penalty + trend_penalty + probability_penalty
    health_score  = max(0, min(STARTING_SCORE, round(STARTING_SCORE - total_penalty)))

    return {
        "sensor"              : sensor,
        "health_score"        : health_score,
        "failure_probability" : prediction["failure_probability"],
        "risk"                : prediction["risk"],
        "penalties"           : {
            "anomaly"    : anomaly_penalty,
            "trend"      : trend_penalty,
            "probability": probability_penalty,
        },
    }


def calculate_fleet_health(sensors: list[str], limit: int = 200) -> dict:
    """
    Aggregate health across multiple sensors into one overall system
    health number — the figure you'd put at the top of a dashboard.

    Overall score = average of all sensor scores that have enough data.
    Sensors with insufficient history are excluded from the average
    rather than treated as a 0 or 100 — neither would be honest.
    """
    per_sensor = {}
    scored     = []

    for sensor in sensors:
        result = calculate_health_score(sensor, limit=limit)
        per_sensor[sensor] = result
        if result["health_score"] is not None:
            scored.append(result["health_score"])

    overall = round(sum(scored) / len(scored)) if scored else None

    # Worst sensor drives the overall risk label — a single HIGH-risk
    # sensor should not be hidden by averaging against healthy ones
    risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": -1}
    worst_risk = "UNKNOWN"
    for result in per_sensor.values():
        if risk_order.get(result["risk"], -1) > risk_order.get(worst_risk, -1):
            worst_risk = result["risk"]

    return {
        "overall_health_score": overall,
        "overall_risk"        : worst_risk,
        "sensors"             : per_sensor,
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Demo: calculate_health_score() against live telemetry.db")
    print("=" * 50)

    sensors = ["CPU_TEMP", "DIMM_TEMP", "FAN_SPEED", "PSU_VOLTAGE"]

    try:
        for sensor in sensors:
            result = calculate_health_score(sensor)
            print(f"\n{sensor}:")
            if result["health_score"] is None:
                print(f"  {result['message']}")
                continue
            print(f"  Health Score        : {result['health_score']}/100")
            print(f"  Failure Probability : {result['failure_probability']}")
            print(f"  Risk                : {result['risk']}")
            print(f"  Penalties           : {result['penalties']}")

        print()
        print("=" * 50)
        print("Demo: calculate_fleet_health() — overall system view")
        print("=" * 50)
        fleet = calculate_fleet_health(sensors)
        print(f"Overall Health Score: {fleet['overall_health_score']}")
        print(f"Overall Risk        : {fleet['overall_risk']}")

    except Exception as e:
        print(f"  (Skipping live demo — {e})")
        print("  Run telemetry/collector.py first to generate real data.")