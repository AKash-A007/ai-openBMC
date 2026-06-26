"""
telemetry/query.py

Query Layer — Phase B Week 1
Friendly, purpose-built functions for reading telemetry history.
These wrap database.py's raw SQL functions and shape the output
for downstream consumers — Phase B Week 2's anomaly detection,
dashboards, or the FastAPI layer.
"""

from datetime import datetime, timedelta, timezone

from database import fetch_by_sensor, fetch_all, count_rows

# ── Core history functions ────────────────────────────────────────────────────

import time

_query_cache = {}
CACHE_TTL_SECONDS = 2.0


def get_sensor_history(sensor: str, limit: int = 100) -> list[float]:
    """
    Return just the numeric values for a sensor, oldest → newest.
    This is the exact shape Phase B Week 2 (anomaly detection) needs —
    a plain list of floats to feed into a trend/anomaly model.

    Example:
        >>> get_sensor_history("CPU_TEMP")
        [71.0, 73.0, 74.0, 77.0, 80.0]
    """
    current_time = time.time()
    cache_key = (sensor, limit, "raw")
    if cache_key in _query_cache:
        val, ts = _query_cache[cache_key]
        if current_time - ts < CACHE_TTL_SECONDS:
            return val

    rows = fetch_by_sensor(sensor, limit=limit)
    res = [row["value"] for row in rows]
    _query_cache[cache_key] = (res, current_time)
    return res


def get_sensor_history_full(sensor: str, limit: int = 100) -> list[dict]:
    """
    Return full reading records (timestamp + value + status) for a sensor.
    Use this when you need context, not just raw numbers —
    e.g. for plotting a time-series chart with status colour coding.

    Example:
        >>> get_sensor_history_full("CPU_TEMP", limit=3)
        [
          {"timestamp": "2026-06-17T15:30:00+00:00", "sensor": "CPU_TEMP", "value": 74.0, "status": "OK"},
          {"timestamp": "2026-06-17T15:30:05+00:00", "sensor": "CPU_TEMP", "value": 75.0, "status": "OK"},
          {"timestamp": "2026-06-17T15:30:10+00:00", "sensor": "CPU_TEMP", "value": 77.0, "status": "WARNING"},
        ]
    """
    current_time = time.time()
    cache_key = (sensor, limit, "full")
    if cache_key in _query_cache:
        val, ts = _query_cache[cache_key]
        if current_time - ts < CACHE_TTL_SECONDS:
            return val

    rows = fetch_by_sensor(sensor, limit=limit)
    res = [
        {
            "timestamp": row["timestamp"],
            "sensor": row["sensor"],
            "value": row["value"],
            "status": row["status"],
        }
        for row in rows
    ]
    _query_cache[cache_key] = (res, current_time)
    return res


def get_latest_reading(sensor: str) -> dict | None:
    """
    Return the single most recent reading for a sensor, or None if
    no data exists yet.
    """
    rows = fetch_by_sensor(sensor, limit=1)
    if not rows:
        return None
    row = rows[-1]  # fetch_by_sensor returns oldest→newest, so last = most recent
    return {
        "timestamp": row["timestamp"],
        "sensor": row["sensor"],
        "value": row["value"],
        "status": row["status"],
    }


def get_all_sensor_names() -> list[str]:
    """Return the distinct list of sensor names currently in the database."""
    rows = fetch_all()
    return sorted(set(row["sensor"] for row in rows))


# ── Aggregate / summary functions ─────────────────────────────────────────────


def get_sensor_stats(sensor: str, limit: int = 100) -> dict:
    """
    Return basic statistics for a sensor's recent history —
    useful for a quick health summary without building a full model yet.
    """
    values = get_sensor_history(sensor, limit=limit)

    if not values:
        return {"sensor": sensor, "count": 0}

    return {
        "sensor": sensor,
        "count": len(values),
        "latest": values[-1],
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2),
        "trend": (
            "rising"
            if values[-1] > values[0]
            else "falling" if values[-1] < values[0] else "stable"
        ),
    }


def get_database_summary() -> dict:
    """High-level overview — total rows, sensors tracked, per-sensor counts."""
    sensors = get_all_sensor_names()
    return {
        "total_rows": count_rows(),
        "sensor_count": len(sensors),
        "sensors": sensors,
        "per_sensor": {s: len(get_sensor_history(s, limit=100_000)) for s in sensors},
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Database Summary")
    print("=" * 50)
    summary = get_database_summary()
    print(f"Total rows   : {summary['total_rows']}")
    print(f"Sensors      : {summary['sensors']}")

    for sensor in summary["sensors"]:
        print(f"\n--- {sensor} ---")
        stats = get_sensor_stats(sensor)
        print(f"  Count : {stats['count']}")
        print(f"  Latest: {stats.get('latest')}")
        print(f"  Min   : {stats.get('min')}")
        print(f"  Max   : {stats.get('max')}")
        print(f"  Avg   : {stats.get('avg')}")
        print(f"  Trend : {stats.get('trend')}")

        history = get_sensor_history(sensor, limit=5)
        print(f"  Last 5 values: {history}")
