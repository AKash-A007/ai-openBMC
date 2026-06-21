"""
analytics/predictor.py

Phase B Week 3 — Failure Prediction Engine (Version 1: Rule-Based)

Why rule-based before ML?
    A rule-based model is fully explainable — every probability can be
    traced back to "temp > 90 contributed 0.4, trend > 3 contributed
    0.2." That transparency matters twice over here:

    1. Engineering: you cannot validate or debug an XGBoost model's
       behaviour against real hardware failure modes until you first
       understand which signals actually matter and how they combine.
       Writing the rules forces that understanding.

    2. Data: supervised ML (XGBoost, random forest classifiers) needs
       labelled training examples — actual past instances of "this
       sensor pattern preceded a real failure." This project has no
       such labelled failure history yet. A rule-based model requires
       zero training data and starts producing useful output on day one.

    The rule-based model becomes the *baseline* that a future ML model
    must beat before it's worth the added complexity and opacity.

Pipeline:
    SQLite → get_sensor_history() → extract_features() → predict_failure()
                                           ↑                    ↑
                                     features.py          this file
"""

import sys
from pathlib import Path

# Allow importing from sibling directories when run standalone
sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
sys.path.append(str(Path(__file__).resolve().parent))

from query import get_sensor_history             # noqa: E402
from features import extract_features            # noqa: E402
from anomaly_detector import detect_anomalies     # noqa: E402


# ── Config — sensor-specific thresholds ───────────────────────────────────────

# Different sensors have different danger zones. CPU_TEMP and PSU_VOLTAGE
# are NOT interchangeable — 90 is dangerously hot for a CPU but means
# nothing for a fan's RPM. Each sensor gets its own rule thresholds,
# mirroring the per-sensor thresholds already used in collector.py.
SENSOR_RULES = {
    "CPU_TEMP": {
        "critical_max": 90,
        "warning_max" : 80,
        "trend_danger": 3.0,     # °C per reading — fast climb
    },
    "DIMM_TEMP": {
        "critical_max": 75,
        "warning_max" : 65,
        "trend_danger": 2.0,
    },
    "FAN_SPEED": {
        "critical_max": 2200,    # inverted — LOW rpm is the danger
        "warning_max" : 2500,
        "trend_danger": -50.0,   # falling fast is the danger sign
        "inverted"    : True,
    },
    "PSU_VOLTAGE": {
        "critical_max": 12.45,
        "warning_max" : 12.30,
        "trend_danger": 0.05,
    },
}

DEFAULT_RULES = {
    "critical_max": 90,
    "warning_max" : 80,
    "trend_danger": 3.0,
}

ANOMALY_COUNT_DANGER = 5   # more than this many recent anomalies is itself a risk signal


# ── Risk category mapping ─────────────────────────────────────────────────────

def categorize_risk(probability: float) -> str:
    """
    Map a 0.0-1.0 failure probability onto a human-readable risk band.

        0-30%   LOW
        30-60%  MEDIUM
        60-100% HIGH
    """
    if probability < 0.30:
        return "LOW"
    elif probability < 0.60:
        return "MEDIUM"
    return "HIGH"


# ── Core prediction logic ─────────────────────────────────────────────────────

def predict_failure(sensor: str, limit: int = 200) -> dict:
    """
    Estimate failure probability for a sensor using:
        1. Current value vs critical/warning thresholds
        2. Recent anomaly count (from Isolation Forest, Week 2)
        3. Trend — how fast the value is moving in a dangerous direction

    Returns:
        {
            "sensor": "CPU_TEMP",
            "failure_probability": 0.78,
            "risk": "HIGH",
            "contributing_factors": {
                "threshold": 0.4,
                "anomaly_count": 0.3,
                "trend": 0.08
            },
            "features": { ...from features.py... }
        }
    """
    values   = get_sensor_history(sensor, limit=limit)
    rules    = SENSOR_RULES.get(sensor, DEFAULT_RULES)
    inverted = rules.get("inverted", False)

    if len(values) < 3:
        return {
            "sensor"              : sensor,
            "failure_probability" : 0.0,
            "risk"                : "UNKNOWN",
            "message"             : "Not enough history to predict — need at least 3 readings.",
        }

    features = extract_features(values)
    latest   = values[-1]

    probability = 0.0
    factors     = {}

    # ── Factor 1: threshold breach ──────────────────────────────────────────
    threshold_score = 0.0
    if inverted:
        if latest <= rules["critical_max"]:
            threshold_score = 0.4
        elif latest <= rules["warning_max"]:
            threshold_score = 0.2
    else:
        if latest >= rules["critical_max"]:
            threshold_score = 0.4
        elif latest >= rules["warning_max"]:
            threshold_score = 0.2
    probability += threshold_score
    factors["threshold"] = threshold_score

    # ── Factor 2: anomaly history (Week 2 Isolation Forest) ────────────────
    anomaly_score = 0.0
    try:
        anomaly_result = detect_anomalies(sensor, limit=limit)
        anomaly_count  = anomaly_result.get("anomaly_count", 0)
        if anomaly_count > ANOMALY_COUNT_DANGER:
            anomaly_score = 0.3
        elif anomaly_count > 0:
            # Scale partial credit: more anomalies = more risk, capped at 0.3
            anomaly_score = round(min(anomaly_count / ANOMALY_COUNT_DANGER, 1.0) * 0.3, 3)
    except Exception:
        # Anomaly detector needs >=10 readings to train — if it's not ready
        # yet, this factor simply contributes 0 rather than breaking prediction
        anomaly_score = 0.0
    probability += anomaly_score
    factors["anomaly_count"] = anomaly_score

    # ── Factor 3: trend ──────────────────────────────────────────────────────
    trend_score  = 0.0
    trend        = features["trend"]
    trend_danger = rules["trend_danger"]

    if inverted:
        # For inverted sensors (fan speed), a NEGATIVE trend beyond the
        # danger threshold is what's risky — falling fast
        if trend <= trend_danger:
            trend_score = 0.2
    else:
        if trend >= trend_danger:
            trend_score = 0.2
    probability += trend_score
    factors["trend"] = trend_score

    probability = round(min(probability, 1.0), 3)

    return {
        "sensor"              : sensor,
        "failure_probability" : probability,
        "risk"                : categorize_risk(probability),
        "contributing_factors": factors,
        "features"            : features,
    }


def predict_all(sensors: list[str], limit: int = 200) -> dict:
    """Run predict_failure() across multiple sensors in one call — used by health_score.py."""
    return {sensor: predict_failure(sensor, limit=limit) for sensor in sensors}


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Demo: categorize_risk() boundaries")
    print("=" * 50)
    for p in [0.0, 0.15, 0.29, 0.30, 0.45, 0.59, 0.60, 0.78, 1.0]:
        print(f"  probability={p:<5} -> risk={categorize_risk(p)}")

    print()
    print("=" * 50)
    print("Demo: predict_failure() against live telemetry.db (if available)")
    print("=" * 50)

    try:
        for sensor in ["CPU_TEMP", "DIMM_TEMP", "FAN_SPEED", "PSU_VOLTAGE"]:
            result = predict_failure(sensor, limit=200)
            print(f"\n{sensor}:")
            if "message" in result:
                print(f"  {result['message']}")
                continue
            print(f"  Failure probability : {result['failure_probability']}")
            print(f"  Risk                : {result['risk']}")
            print(f"  Contributing factors: {result['contributing_factors']}")
            print(f"  Features            : {result['features']}")
    except Exception as e:
        print(f"  (Skipping live demo — {e})")
        print("  Run telemetry/collector.py first to generate real data.")