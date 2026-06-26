"""
analytics/anomaly_detector.py

Phase B Week 2 — Anomaly Detection Layer

Pipeline:
    SQLite (telemetry.db)
        ↓
    get_sensor_history(sensor)   ← Week 1 query layer
        ↓
    IsolationForest
        ↓
    Anomaly labels + scores

Why Isolation Forest?
    Telemetry has no labels — nobody manually tags each reading as
    "normal" or "anomalous" ahead of time. Isolation Forest is an
    unsupervised algorithm: it learns what "normal" looks like purely
    from the distribution of the data itself, with no labelled examples.

    The core idea: anomalies are easier to isolate than normal points.
    A random partitioning of the feature space separates an outlier
    (e.g. 150°C in a stream of 70-75°C readings) into its own region
    in very few splits, while a normal point sits deep inside a dense
    cluster and takes many splits to isolate. Average split-depth
    across many random trees becomes the anomaly score.

    This is the same algorithmic family used by Datadog, New Relic,
    and Splunk for infrastructure anomaly detection — it requires no
    labelled training data, which matches real telemetry exactly.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest

# Allow importing from ../telemetry/ when run standalone
sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
from query import get_sensor_history, get_sensor_history_full  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

# contamination = the assumed proportion of anomalies in the data.
# 0.05 means "assume ~5% of readings are anomalous" — this is a prior,
# not a hard rule; IsolationForest uses it to calibrate the decision
# boundary between normal and anomalous scores.
DEFAULT_CONTAMINATION = 0.05
RANDOM_STATE = 42  # fixed seed → reproducible results across runs

# Model cache — avoid retraining on every single call within a session
_model_cache: dict[str, IsolationForest] = {}


# ── Step 1: Reshape data for sklearn ──────────────────────────────────────────


def _prepare_data(values: list[float]) -> np.ndarray:
    """
    sklearn estimators expect a 2D array: (n_samples, n_features).
    Our telemetry is a single feature (the sensor value), so each
    reading becomes its own row: [[70], [72], [73], [150]].

    Without this reshape, IsolationForest raises:
        ValueError: Expected 2D array, got 1D array instead
    """
    return np.array(values).reshape(-1, 1)


# ── Step 2: Train ──────────────────────────────────────────────────────────────


def train_model(
    sensor: str,
    limit: int = 200,
    contamination: float = DEFAULT_CONTAMINATION,
) -> IsolationForest:
    """
    Train (fit) an Isolation Forest on a sensor's historical readings.

    Args:
        sensor       : sensor name, e.g. "CPU_TEMP"
        limit        : how many historical readings to train on
        contamination: assumed fraction of anomalies in the training data

    Returns:
        The fitted IsolationForest model (also cached in-memory for reuse).

    Raises:
        ValueError if there isn't enough history to train meaningfully.
    """
    values = get_sensor_history(sensor, limit=limit)

    if len(values) < 10:
        raise ValueError(
            f"Not enough data to train on '{sensor}' — "
            f"got {len(values)} readings, need at least 10. "
            f"Let the collector run longer."
        )

    data = _prepare_data(values)

    model = IsolationForest(
        contamination=contamination,
        random_state=RANDOM_STATE,
    )
    model.fit(data)

    _model_cache[sensor] = model
    return model


def _get_or_train_model(sensor: str, limit: int = 200) -> IsolationForest:
    """Reuse a cached model if available, otherwise train fresh."""
    if sensor not in _model_cache:
        train_model(sensor, limit=limit)
    return _model_cache[sensor]


# ── Step 3: Predict ────────────────────────────────────────────────────────────


def detect_anomalies(sensor: str, limit: int = 200) -> dict:
    """
    Run anomaly detection on a sensor's recent history.

    Returns:
        {
            "sensor": "CPU_TEMP",
            "total_readings": 200,
            "anomaly_count": 1,
            "anomalies": [
                {"value": 150.0, "score": -0.44, "index": 197}
            ]
        }
    """
    values = get_sensor_history(sensor, limit=limit)

    if len(values) < 10:
        return {
            "sensor": sensor,
            "total_readings": len(values),
            "anomaly_count": 0,
            "anomalies": [],
            "message": "Not enough history yet — need at least 10 readings.",
        }

    data = _prepare_data(values)
    model = _get_or_train_model(sensor, limit=limit)

    # predict() → 1 for normal (inlier), -1 for anomaly (outlier)
    predictions = model.predict(data)

    # decision_function() → continuous anomaly score.
    # Negative = more anomalous, positive = more normal.
    # This is what lets us report severity, not just a binary flag.
    scores = model.decision_function(data)

    anomalies = []
    for i, (value, pred, score) in enumerate(zip(values, predictions, scores)):
        if pred == -1:
            anomalies.append(
                {
                    "value": float(value),
                    "score": round(float(score), 4),
                    "index": i,
                }
            )

    return {
        "sensor": sensor,
        "total_readings": len(values),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


# ── Step 4: Score a single new reading against the trained model ─────────────


def get_anomaly_score(sensor: str, value: float, limit: int = 200) -> dict:
    """
    Score ONE new incoming reading against the sensor's trained baseline —
    this is the function you'd call in real-time as each new telemetry
    point arrives, rather than re-scanning the whole history every time.

    Returns:
        {
            "sensor": "CPU_TEMP",
            "value": 150.0,
            "status": "ANOMALY",     # or "NORMAL"
            "score": -0.44,
            "severity": "HIGH"        # derived from score + distance from baseline
        }

    Note on score saturation:
        IsolationForest.decision_function() does NOT decrease without
        bound as a value gets more extreme — it saturates once a value
        is isolated in very few splits (typically within 1-2 levels of
        the tree). A reading of 160 and a reading of 500 can produce the
        *same* score, even though 500 is far more severe in real terms.
        Score alone is therefore a weak signal for severity at the
        extreme end — we combine it with simple distance-from-baseline
        (z-score-like) to differentiate "mildly weird" from "wildly
        abnormal" readings.
    """
    model = _get_or_train_model(sensor, limit=limit)

    data = _prepare_data([value])
    prediction = model.predict(data)[0]
    score = float(model.decision_function(data)[0])

    status = "ANOMALY" if prediction == -1 else "NORMAL"

    # Distance-from-baseline as a secondary severity signal, since the
    # isolation score saturates and can't distinguish "150" from "500".
    baseline_values = get_sensor_history(sensor, limit=limit)
    mean = float(np.mean(baseline_values))
    std = float(np.std(baseline_values)) or 1.0  # avoid divide-by-zero
    z_distance = abs(value - mean) / std

    if status == "NORMAL":
        severity = "NONE"
    elif z_distance < 5:
        severity = "LOW"
    elif z_distance < 15:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    return {
        "sensor": sensor,
        "value": value,
        "status": status,
        "score": round(score, 4),
        "severity": severity,
    }


# ── Step 5: Full health snapshot (for dashboard integration) ─────────────────


def get_sensor_health(sensor: str, limit: int = 200) -> dict:
    """
    Combine the latest reading + anomaly detection into a single
    dashboard-friendly health summary.

    Returns:
        {
            "sensor": "CPU_TEMP",
            "latest_value": 82.0,
            "status": "NORMAL",
            "score": 0.12,
            "severity": "NONE",
            "recent_anomaly_count": 1
        }
    """
    history = get_sensor_history_full(sensor, limit=limit)

    if not history:
        return {"sensor": sensor, "status": "NO_DATA"}

    latest = history[-1]
    result = get_anomaly_score(sensor, latest["value"], limit=limit)

    full_scan = detect_anomalies(sensor, limit=limit)

    return {
        "sensor": sensor,
        "latest_value": latest["value"],
        "latest_timestamp": latest["timestamp"],
        "status": result["status"],
        "score": result["score"],
        "severity": result["severity"],
        "recent_anomaly_count": full_scan["anomaly_count"],
    }


def retrain_all(sensors: list[str], limit: int = 200) -> dict:
    """
    Retrain models for multiple sensors at once — call this periodically
    (e.g. on a schedule) so the model's notion of "normal" stays current
    as more telemetry accumulates.
    """
    results = {}
    for sensor in sensors:
        try:
            train_model(sensor, limit=limit)
            results[sensor] = "retrained"
        except ValueError as e:
            results[sensor] = f"skipped: {e}"
    return results


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo using the exact example from the spec
    print("=" * 50)
    print("Demo: Isolation Forest on synthetic data")
    print("=" * 50)

    demo_values = [70.0, 72.0, 71.0, 73.0, 74.0, 75.0, 150.0]
    print(f"Input values: {demo_values}")

    data = _prepare_data(demo_values)
    model = IsolationForest(contamination=0.15, random_state=RANDOM_STATE)
    model.fit(data)

    predictions = model.predict(data)
    scores = model.decision_function(data)

    print(f"\nPredictions: {list(predictions)}   (1=normal, -1=anomaly)")
    print(f"Scores     : {[round(s, 3) for s in scores]}")

    for value, pred, score in zip(demo_values, predictions, scores):
        status = "ANOMALY" if pred == -1 else "normal"
        print(f"  {value:>5}  →  {status:<8}  score={score:.4f}")

    print("\n" + "=" * 50)
    print("Demo: Live data from telemetry.db (if available)")
    print("=" * 50)

    try:
        for sensor in ["CPU_TEMP", "DIMM_TEMP", "FAN_SPEED", "PSU_VOLTAGE"]:
            result = detect_anomalies(sensor, limit=200)
            print(f"\n{sensor}:")
            print(f"  Total readings : {result['total_readings']}")
            print(f"  Anomalies found: {result['anomaly_count']}")
            for a in result["anomalies"]:
                print(f"    value={a['value']}  score={a['score']}")
    except Exception as e:
        print(f"  (Skipping live data demo — {e})")
        print("  Run telemetry/collector.py first to generate real data.")
