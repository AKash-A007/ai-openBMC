"""
monitoring/alerts.py

Phase B Week 4 — Alert Engine

This is the layer that turns "the system computed some numbers" into
"someone should look at this." Every prior layer (Week 1 telemetry,
Week 2 anomaly detection, Week 3 prediction/health scoring) produces
data. This file is the first one that produces an *opinion* about
whether that data warrants a human's attention right now.

Design principle: alerts.py reads from health_score.py and
anomaly_detector.py — it does not recompute risk itself. An alert is a
THRESHOLD APPLIED TO existing analytics output, not a new analytics
method. This keeps the actual risk logic in one place (predictor.py /
health_score.py) and keeps this file focused purely on "given this
score, should we surface a notification, and how loud should it be."
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "analytics"))

from query import get_all_sensor_names  # noqa: E402
from health_score import calculate_health_score  # noqa: E402
from anomaly_detector import detect_anomalies  # noqa: E402

# ── Config — alert thresholds ─────────────────────────────────────────────────

# These thresholds are deliberately separate from predictor.py's risk
# bands (LOW/MEDIUM/HIGH at 30%/60%) — an alert threshold answers a
# different question ("should this interrupt a human") than a risk
# category does ("how should this be classified analytically"). They
# happen to align loosely here, but keeping them as distinct constants
# means tuning alert sensitivity later doesn't require touching the
# underlying risk model.
HEALTH_WARNING_THRESHOLD = 80  # below this: WARNING
HEALTH_CRITICAL_THRESHOLD = 60  # below this: CRITICAL

FAILURE_PROB_ALERT_THRESHOLD = 0.75  # spec's explicit rule


# ── Severity classification ───────────────────────────────────────────────────


def _severity_from_health(health_score: int) -> str:
    """
    INFO     — health_score > 80   (healthy, no action needed)
    WARNING  — 60 < health_score <= 80  (degrading, worth watching)
    CRITICAL — health_score <= 60  (action likely needed soon)
    """
    if health_score > HEALTH_WARNING_THRESHOLD:
        return "INFO"
    elif health_score > HEALTH_CRITICAL_THRESHOLD:
        return "WARNING"
    return "CRITICAL"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Individual alert rules ────────────────────────────────────────────────────


def _check_health_score(sensor: str, result: dict) -> dict | None:
    """
    Rule: if health_score < 70 (per spec) → ALERT.
    Implemented here as: any score that isn't comfortably healthy
    (i.e. anything WARNING or worse) generates an alert — INFO-level
    health scores don't produce alerts at all, since "everything is
    fine" shouldn't generate a notification.
    """
    score = result.get("health_score")
    if score is None:
        return None

    severity = _severity_from_health(score)
    if severity == "INFO":
        return None  # healthy — no alert

    return {
        "timestamp": _now(),
        "sensor": sensor,
        "severity": severity,
        "rule": "HEALTH_SCORE",
        "message": f"{sensor} health score is {score}/100 — {severity.lower()} condition.",
        "value": score,
    }


def _check_failure_probability(sensor: str, result: dict) -> dict | None:
    """Rule: if failure_probability > 0.75 → ALERT (per spec, explicit threshold)."""
    probability = result.get("failure_probability")
    if probability is None or probability <= FAILURE_PROB_ALERT_THRESHOLD:
        return None

    return {
        "timestamp": _now(),
        "sensor": sensor,
        "severity": "CRITICAL",
        "rule": "FAILURE_PROBABILITY",
        "message": f"{sensor} failure probability is {probability*100:.0f}% — "
        f"failure risk high.",
        "value": probability,
    }


def _check_anomaly_detected(sensor: str, limit: int = 200) -> dict | None:
    """
    Rule: if the most recent reading itself is anomalous → ALERT.

    Distinct from the health-score and probability checks above —
    those look at the AGGREGATE risk picture; this one flags "the
    single most recent reading was itself flagged as an outlier,"
    which can fire even when the rolling health score hasn't yet
    caught up to reflect one fresh bad reading.
    """
    try:
        result = detect_anomalies(sensor, limit=limit)
    except Exception:
        return None  # not enough history yet to run anomaly detection

    anomalies = result.get("anomalies", [])
    if not anomalies:
        return None

    # Only alert if the MOST RECENT reading (highest index) was anomalous —
    # an anomaly from 150 readings ago shouldn't fire a fresh alert every
    # time this check runs.
    latest_index = result["total_readings"] - 1
    latest_anomaly = next((a for a in anomalies if a["index"] == latest_index), None)
    if latest_anomaly is None:
        return None

    return {
        "timestamp": _now(),
        "sensor": sensor,
        "severity": "WARNING",
        "rule": "ANOMALY_DETECTED",
        "message": f"{sensor} latest reading ({latest_anomaly['value']}) "
        f"flagged as anomalous (score={latest_anomaly['score']}).",
        "value": latest_anomaly["value"],
    }


# ── Orchestration ──────────────────────────────────────────────────────────────


def check_sensor_alerts(sensor: str, limit: int = 200) -> list[dict]:
    """
    Run every alert rule against one sensor and return whichever fired.
    A single sensor can produce zero, one, or multiple simultaneous
    alerts (e.g. both a low health score AND a fresh anomaly).
    """
    health_result = calculate_health_score(sensor, limit=limit)

    alerts = []
    for check in (
        lambda: _check_health_score(sensor, health_result),
        lambda: _check_failure_probability(sensor, health_result),
        lambda: _check_anomaly_detected(sensor, limit),
    ):
        alert = check()
        if alert:
            alerts.append(alert)

    return alerts


def check_all_alerts(limit: int = 200) -> list[dict]:
    """
    Run alert checks across every sensor currently tracked.
    This is the function a dashboard's "Recent Alerts" panel or a
    background polling job would call on each cycle.

    Returns alerts sorted CRITICAL → WARNING → INFO, most severe first,
    so a dashboard rendering the list top-to-bottom shows what matters
    most without needing its own sorting logic.
    """
    sensors = get_all_sensor_names()
    all_alerts = []
    for sensor in sensors:
        all_alerts.extend(check_sensor_alerts(sensor, limit=limit))

    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    all_alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))
    return all_alerts


def get_alert_summary(limit: int = 200) -> dict:
    """
    Counts by severity — the small numeric badges a dashboard header
    would show (e.g. "2 critical, 1 warning").
    """
    alerts = check_all_alerts(limit=limit)
    summary = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for a in alerts:
        summary[a["severity"]] = summary.get(a["severity"], 0) + 1

    return {
        "total": len(alerts),
        "by_severity": summary,
        "alerts": alerts,
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 50)
    print("Demo: check_all_alerts() against live telemetry.db")
    print("=" * 50)

    summary = get_alert_summary()
    print(f"\nTotal alerts: {summary['total']}")
    print(f"By severity : {summary['by_severity']}")

    if summary["alerts"]:
        print("\nAlerts (most severe first):")
        for a in summary["alerts"]:
            icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}[a["severity"]]
            print(f"  {icon} [{a['severity']}] {a['sensor']}: {a['message']}")
    else:
        print(
            "\nNo alerts — all sensors healthy, or insufficient data. "
            "Run telemetry/collector.py first."
        )
