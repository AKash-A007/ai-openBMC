"""
monitoring/dashboard.py

Phase B Week 4 — Observability Dashboard

Run with:
    streamlit run dashboard.py

Layout (per spec):
    +-----------------------------------+
    | System Health: 84/100             |
    +-----------------------------------+
    | Failure Probability: 23%          |
    +-----------------------------------+
    | CPU Temperature Trend              |
    |      Graph                          |
    +-----------------------------------+
    | Recent Alerts                       |
    +-----------------------------------+
    | Recent Diagnoses                    |
    +-----------------------------------+

This is intentionally a SEPARATE Streamlit app from Phase A's app.py
(the diagnosis-trigger dashboard). That one answers "let me run a
diagnosis on this scenario." This one answers "show me how the system
has been behaving" — observability is a read-only, always-on view of
history, not an action-triggering interface. Keeping them separate
apps mirrors how real platforms split "operate" tools from "observe"
tools (e.g. a remediation console vs. a Grafana dashboard).
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "telemetry"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "analytics"))
sys.path.append(str(Path(__file__).resolve().parent))

from query import get_sensor_history_full, get_all_sensor_names   # noqa: E402
from metrics import get_system_metrics                              # noqa: E402
from alerts import get_alert_summary                                # noqa: E402
from reports import get_recent_diagnoses, generate_weekly_report    # noqa: E402


SEVERITY_COLORS = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}
RISK_COLORS     = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "UNKNOWN": "⚪"}


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="AI OpsBMC — Observability", page_icon="📊", layout="wide")
st.title("📊 AI OpsBMC — Observability Dashboard")
st.caption("Phase B · Telemetry → Analytics → Visualization → Alerts")

sensors = get_all_sensor_names()

if not sensors:
    st.warning("No telemetry data found yet. Run `telemetry/collector.py` first.")
    st.stop()

system = get_system_metrics()


# ── Row 1: System Health + Failure Risk headline cards ────────────────────────

c1, c2, c3 = st.columns(3)

with c1:
    health = system["overall_health"]
    st.metric("System Health", f"{health}/100" if health is not None else "—")

with c2:
    risk = system["overall_risk"]
    icon = RISK_COLORS.get(risk, "⚪")
    st.metric("Overall Risk", f"{icon} {risk}")

with c3:
    rate = system["failure_rate"]
    st.metric("Failure Rate", f"{rate*100:.0f}%" if rate is not None else "—")

if system["at_risk_sensors"]:
    st.info(f"⚠️ Sensors at elevated risk: {', '.join(system['at_risk_sensors'])}")


# ── Row 2: Per-sensor trend graphs ─────────────────────────────────────────────

st.divider()
st.subheader("📈 Sensor Trends")

selected_sensor = st.selectbox("Select sensor", sensors)

history = get_sensor_history_full(selected_sensor, limit=100)

if history:
    import pandas as pd

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    st.line_chart(df["value"], height=300)

    m = system["sensors"].get(selected_sensor, {})
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Latest", m.get("latest", "—"))
    sc2.metric("Average", m.get("avg", "—"))
    sc3.metric("Max", m.get("max", "—"))
    sc4.metric("Min", m.get("min", "—"))
else:
    st.caption("No history for this sensor yet.")


# ── Row 3: Recent Alerts ──────────────────────────────────────────────────────

st.divider()
st.subheader("🚨 Recent Alerts")

alert_summary = get_alert_summary()

ac1, ac2, ac3 = st.columns(3)
ac1.metric("🔴 Critical", alert_summary["by_severity"]["CRITICAL"])
ac2.metric("🟡 Warning", alert_summary["by_severity"]["WARNING"])
ac3.metric("🟢 Info", alert_summary["by_severity"]["INFO"])

if alert_summary["alerts"]:
    for a in alert_summary["alerts"]:
        icon = SEVERITY_COLORS.get(a["severity"], "⚪")
        st.write(f"{icon} **[{a['severity']}]** {a['sensor']} — {a['message']}")
else:
    st.success("✅ No active alerts — all sensors within normal parameters.")


# ── Row 4: Recent Diagnoses (RCA history) ──────────────────────────────────────

st.divider()
st.subheader("🧠 Recent Diagnoses")

diagnoses = get_recent_diagnoses(limit=10)

if diagnoses:
    for d in diagnoses:
        with st.expander(f"{d['sensor']} — {d['root_cause'][:60]}  ·  {d['timestamp'][:19]}"):
            st.write(f"**Root Cause:** {d['root_cause']}")
            st.write(f"**Confidence:** {d['confidence']}")
else:
    st.caption("No diagnoses recorded yet. Diagnoses are logged whenever "
               "Phase A's diagnosis agent calls `database.insert_diagnosis()`.")


# ── Row 5: Weekly Report snapshot ──────────────────────────────────────────────

st.divider()
st.subheader("📋 Weekly Report Snapshot")

with st.expander("View full report"):
    report = generate_weekly_report()
    st.json(report)