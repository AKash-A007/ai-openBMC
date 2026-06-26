"""
monitoring/reports.py

Phase B Week 4 — Report Generator

Metrics and alerts answer "what is the state right now." Reports
answer a different question: "what happened over a period of time,
and what should I pay attention to going forward." This is the
summarisation layer — it doesn't introduce any new analysis, it
aggregates what metrics.py and alerts.py already compute, plus the
diagnosis history table, into a single digestible snapshot.

This is also where the `diagnoses` table (added to database.py this
week) gets its first real consumer — "top issue" and "most frequent
failures" are only answerable once diagnosis results are persisted
rather than printed once and discarded.
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "analytics"))
sys.path.append(str(Path(__file__).resolve().parent))

from query import get_all_sensor_names  # noqa: E402
from database import fetch_recent_diagnoses, count_diagnoses  # noqa: E402
from metrics import get_system_metrics  # noqa: E402
from alerts import get_alert_summary  # noqa: E402

# ── RCA history helpers ────────────────────────────────────────────────────────


def get_recent_diagnoses(limit: int = 10) -> list[dict]:
    """
    The 'Last 10 Diagnoses' panel — newest first, shaped for direct
    JSON/dashboard consumption rather than raw sqlite3.Row objects.
    """
    rows = fetch_recent_diagnoses(limit=limit)
    return [
        {
            "timestamp": row["timestamp"],
            "sensor": row["sensor"],
            "root_cause": row["root_cause"],
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def get_most_frequent_issue(limit: int = 100) -> dict | None:
    """
    'Top Issue' for the weekly report — the most commonly recorded
    root_cause across recent diagnoses.

    Why count root_cause text rather than sensor name: two diagnoses on
    the same sensor can have entirely different root causes (e.g.
    CPU_TEMP overheating once due to a fan fault, once due to thermal
    paste degradation) — counting by sensor would conflate genuinely
    different problems. Counting by root_cause text is the more honest
    signal of "what specific problem keeps recurring," at the cost of
    being sensitive to exact wording — a known limitation worth noting
    rather than silently accepting.
    """
    diagnoses = get_recent_diagnoses(limit=limit)
    if not diagnoses:
        return None

    counts = Counter(d["root_cause"] for d in diagnoses)
    top_cause, top_count = counts.most_common(1)[0]

    return {
        "root_cause": top_cause,
        "occurrences": top_count,
        "out_of": len(diagnoses),
    }


def get_recurring_problems(limit: int = 100, min_occurrences: int = 2) -> list[dict]:
    """
    Every root_cause that has occurred more than once recently —
    the basis for "recurring problems" rather than just the single
    top issue. A problem appearing exactly once might be a one-off;
    appearing 2+ times is the operational signal worth surfacing.
    """
    diagnoses = get_recent_diagnoses(limit=limit)
    if not diagnoses:
        return []

    counts = Counter(d["root_cause"] for d in diagnoses)
    recurring = [
        {"root_cause": cause, "occurrences": count}
        for cause, count in counts.items()
        if count >= min_occurrences
    ]
    recurring.sort(key=lambda x: x["occurrences"], reverse=True)
    return recurring


# ── Weekly report ──────────────────────────────────────────────────────────────


def generate_weekly_report(
    diagnosis_limit: int = 100, telemetry_limit: int = 200
) -> dict:
    """
    Combine system metrics, alert counts, and diagnosis history into
    a single summary report — the function a scheduled job (cron, or
    a FastAPI endpoint hit once a week) would call to produce a
    digest for operators.

    Returns:
        {
            "avg_health": 84,
            "overall_risk": "MEDIUM",
            "total_alerts": 3,
            "critical_alerts": 1,
            "warning_alerts": 2,
            "top_issue": {"root_cause": "...", "occurrences": 4, "out_of": 12},
            "recurring_problems": [...],
            "total_diagnoses_recorded": 47,
            "sensors_tracked": ["CPU_TEMP", "FAN_SPEED", ...]
        }
    """
    metrics_summary = get_system_metrics(limit=telemetry_limit)
    alert_summary = get_alert_summary(limit=telemetry_limit)
    top_issue = get_most_frequent_issue(limit=diagnosis_limit)
    recurring = get_recurring_problems(limit=diagnosis_limit)

    return {
        "avg_health": metrics_summary["overall_health"],
        "overall_risk": metrics_summary["overall_risk"],
        "failure_rate": metrics_summary["failure_rate"],
        "total_alerts": alert_summary["total"],
        "critical_alerts": alert_summary["by_severity"]["CRITICAL"],
        "warning_alerts": alert_summary["by_severity"]["WARNING"],
        "top_issue": top_issue,
        "recurring_problems": recurring,
        "total_diagnoses_recorded": count_diagnoses(),
        "sensors_tracked": get_all_sensor_names(),
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 50)
    print("Demo: generate_weekly_report() against live telemetry.db")
    print("=" * 50)
    report = generate_weekly_report()
    print(json.dumps(report, indent=2))

    print()
    print("=" * 50)
    print("Demo: get_recent_diagnoses()")
    print("=" * 50)
    diagnoses = get_recent_diagnoses(limit=5)
    if diagnoses:
        for d in diagnoses:
            print(
                f"  [{d['timestamp']}] {d['sensor']}: {d['root_cause']} "
                f"(confidence={d['confidence']})"
            )
    else:
        print(
            "  No diagnoses recorded yet — call database.insert_diagnosis() "
            "from agent.py whenever a diagnosis completes."
        )
