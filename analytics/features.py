"""
analytics/features.py

Phase B Week 3 — Feature Engineering Layer

Why this file exists:
    Raw telemetry is just a list of numbers:
        [70, 72, 73, 75, 76, 77]

    Neither a rule-based predictor nor an ML model learns well from a
    raw list — they need that list condensed into a handful of summary
    statistics that actually correlate with risk:

        mean   → typical operating level
        max    → worst point reached recently
        min    → best point (useful as a baseline reference)
        std    → volatility — a noisy, jumpy sensor is itself a signal
        trend  → direction and speed of change — "rising fast" matters
                 even if the current value looks fine in isolation

    This file is intentionally the ONLY place that turns raw values
    into model-ready features — predictor.py and health_score.py both
    import from here rather than recomputing statistics inline. Same
    separation-of-concerns principle as database.py owning all SQL.
"""

import numpy as np

# ── Core feature extraction ───────────────────────────────────────────────────


def extract_features(values: list[float]) -> dict:
    """
    Convert a list of raw sensor readings into summary statistics.

    Args:
        values: list of numeric readings, oldest → newest
                e.g. [70, 72, 74, 76, 80]

    Returns:
        {
            "mean": 74.4,
            "max": 80.0,
            "min": 70.0,
            "std": 3.6,
            "trend": 2.5,
            "count": 5
        }

    Returns all-zero features with count=0 if values is empty, rather
    than raising — callers (predictor.py) can then handle "not enough
    data" as a normal case instead of catching exceptions everywhere.
    """
    if not values:
        return {
            "mean": 0.0,
            "max": 0.0,
            "min": 0.0,
            "std": 0.0,
            "trend": 0.0,
            "count": 0,
        }

    arr = np.array(values, dtype=float)

    return {
        "mean": round(float(np.mean(arr)), 3),
        "max": round(float(np.max(arr)), 3),
        "min": round(float(np.min(arr)), 3),
        "std": round(float(np.std(arr)), 3),
        "trend": round(calculate_trend(values), 3),
        "count": len(values),
    }


# ── Trend calculation ──────────────────────────────────────────────────────────


def calculate_trend(values: list[float]) -> float:
    """
    Simple trend estimate: average change per reading.

        trend = (last_value - first_value) / len(values)

    A positive trend means the sensor is climbing over the observed
    window; negative means it's falling. Magnitude indicates how fast.

    This is deliberately simple (not a full linear regression slope)
    because Week 3 is the rule-based baseline — see predictor.py's
    docstring for why we start simple before reaching for ML.

    Returns 0.0 for fewer than 2 readings (no trend is computable from
    a single point).
    """
    if len(values) < 2:
        return 0.0
    return (values[-1] - values[0]) / len(values)


def calculate_rate_of_change(values: list[float], window: int = 5) -> float:
    """
    Trend over just the most recent `window` readings, rather than the
    entire history. This catches a sensor that was stable for a long
    time but has started climbing sharply in just the last few polls —
    calculate_trend() over the full history would dilute that signal
    by averaging it against a long stable period.
    """
    if len(values) < 2:
        return 0.0
    recent = values[-window:] if len(values) >= window else values
    return calculate_trend(recent)


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Feature extraction — spec example")
    print("=" * 50)

    demo = [70, 72, 74, 76, 80]
    print(f"Input : {demo}")
    print(f"Output: {extract_features(demo)}")

    print()
    print("=" * 50)
    print("Trend comparison — stable vs rising")
    print("=" * 50)

    stable = [74, 75, 74, 75, 74, 75]
    rising = [70, 74, 79, 84, 90, 95]

    for label, vals in [("Stable", stable), ("Rising", rising)]:
        f = extract_features(vals)
        print(f"\n{label}: {vals}")
        print(f"  mean={f['mean']}  std={f['std']}  trend={f['trend']}")

    print()
    print("=" * 50)
    print("Rate of change — recent window vs full history")
    print("=" * 50)

    # Long stable period, then a sharp recent climb
    mixed = [74, 75, 74, 75, 74, 75, 74, 80, 88, 96]
    print(f"Input: {mixed}")
    print(f"Full-history trend : {calculate_trend(mixed):.3f}")
    print(f"Recent (last 5) ROC: {calculate_rate_of_change(mixed, window=5):.3f}")
