"""
parser.py
Reads saved Redfish JSON files and extracts structured events for diagnosis.
"""

import json
from pathlib import Path

# ── Where redfish_client.py saves its files ────────────────────────────────────
DATA_DIR = Path("./redfish_data")

# ── Event pattern matching ─────────────────────────────────────────────────────

EVENT_PATTERNS = {
    "ECC"                  : ("MEMORY", "ECC_ERROR"),
    "CPU Over Temperature" : ("CPU",    "OVERHEAT"),
    "Power Supply Failure" : ("PSU",    "FAILURE"),
    "Fan Fault"            : ("COOLING","FAN_FAULT"),
    "Voltage Fault"        : ("POWER",  "VOLTAGE_FAULT"),
}

def parse_event(event_str: str) -> dict | None:
    """Map a raw event string to category + event_type."""
    for keyword, (category, event_type) in EVENT_PATTERNS.items():
        if keyword in event_str:
            return {"category": category, "event_type": event_type}
    return None


def parse_log(log: dict) -> dict | None:
    """
    Parse a single raw log dict into a structured event.
    Input : {"sensor": "DIMM_B2", "event": "Memory ECC Error", "severity": "WARNING"}
    Output: {"sensor": ..., "category": ..., "event_type": ..., "severity": ...}
    """
    sensor   = log.get("sensor",   "UNKNOWN")
    event    = log.get("event",    "")
    severity = log.get("severity", "UNKNOWN")

    parsed = parse_event(event)
    if parsed:
        return {
            "sensor"    : sensor,
            "category"  : parsed["category"],
            "event_type": parsed["event_type"],
            "severity"  : severity,
        }
    return None


# ── JSON file readers ──────────────────────────────────────────────────────────

def load_json(filename: str) -> dict:
    """Load a saved Redfish JSON file from DATA_DIR."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"[Parser] File not found: {path}")
    with open(path) as f:
        return json.load(f)


def extract_events_from_system(system_data: dict) -> list[dict]:
    """
    Extract log entries from system.json (Redfish System resource).
    Returns a list of raw log dicts ready for parse_log().
    """
    events = []

    # Pull from MemorySummary health status
    memory_health = (
        system_data
        .get("MemorySummary", {})
        .get("Status", {})
        .get("Health", "OK")
    )
    if memory_health != "OK":
        events.append({
            "sensor"  : "MemorySummary",
            "event"   : "Memory ECC Error",
            "severity": "WARNING" if memory_health == "Warning" else "CRITICAL",
        })

    # Pull from ProcessorSummary health status
    cpu_health = (
        system_data
        .get("ProcessorSummary", {})
        .get("Status", {})
        .get("Health", "OK")
    )
    if cpu_health != "OK":
        events.append({
            "sensor"  : "ProcessorSummary",
            "event"   : "CPU Over Temperature",
            "severity": "WARNING" if cpu_health == "Warning" else "CRITICAL",
        })

    return events


def extract_events_from_thermal(thermal_data: dict) -> list[dict]:
    """
    Extract overheat events from thermal.json.
    Flags any temperature sensor reading above its UpperThresholdCritical.
    """
    events = []
    for temp in thermal_data.get("Temperatures", []):
        name    = temp.get("Name", "UNKNOWN")
        reading = temp.get("ReadingCelsius")
        upper   = temp.get("UpperThresholdCritical")
        health  = temp.get("Status", {}).get("Health", "OK")

        if health != "OK" or (reading and upper and reading >= upper):
            events.append({
                "sensor"  : name,
                "event"   : "CPU Over Temperature",
                "severity": "CRITICAL" if health == "Critical" else "WARNING",
            })
    return events


def extract_events_from_power(power_data: dict) -> list[dict]:
    """
    Extract PSU failure events from power.json.
    """
    events = []
    for psu in power_data.get("PowerSupplies", []):
        name   = psu.get("Name", "UNKNOWN")
        health = psu.get("Status", {}).get("Health", "OK")
        if health != "OK":
            events.append({
                "sensor"  : name,
                "event"   : "Power Supply Failure",
                "severity": "CRITICAL",
            })
    return events


def extract_all_events() -> list[dict]:
    """
    Master function: load all saved JSON files and extract every event.
    Returns a flat list of raw log dicts for the agent to diagnose.
    """
    all_events = []

    loaders = [
        ("system.json",  extract_events_from_system),
        ("thermal.json", extract_events_from_thermal),
        ("power.json",   extract_events_from_power),
    ]

    for filename, extractor in loaders:
        try:
            data   = load_json(filename)
            events = extractor(data)
            all_events.extend(events)
            print(f"[Parser] {filename} → {len(events)} event(s) found")
        except FileNotFoundError as e:
            print(f"[Parser] Skipping: {e}")

    if not all_events:
        print("[Parser] No events found — system appears healthy.")

    return all_events