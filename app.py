"""
app.py  —  Week 4 Streamlit Dashboard
AI OpsBMC Diagnostics UI

Run with:
    streamlit run app.py
"""
from dotenv import load_dotenv
load_dotenv()          # reads .env automatically, no terminal setup needed
import requests
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH"    : "🟠",
    "MEDIUM"  : "🟡",
    "LOW"     : "🟢",
    "UNKNOWN" : "⚪",
}

SCENARIO_LABELS = {
    "dimm_failure"  : "💾 DIMM Failure (Memory ECC Error)",
    "cpu_overheat"  : "🔥 CPU Overheat",
    "psu_failure"   : "⚡ Power Supply Failure",
    "fan_fault"     : "🌀 Fan Fault",
    "voltage_fault" : "⚠️ Voltage Fault",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def run_diagnosis(scenario_name: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/diagnose/scenario",
            json={"name": scenario_name},
            timeout=60,         # LLM call can take a moment
        )
        return r.json() if r.status_code == 200 else {"error": r.json().get("detail", "API error")}
    except Exception as e:
        return {"error": str(e)}


def get_history() -> list:
    try:
        r = requests.get(f"{API_BASE}/results?limit=10", timeout=5)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception:
        return []


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI OpsBMC",
    page_icon="🖥️",
    layout="wide",
)

st.title("🖥️ AI OpsBMC — Hardware Diagnostics Dashboard")
st.caption("RAG + LLM powered OpenBMC fault analysis engine")

# ── Sidebar — health + info ───────────────────────────────────────────────────

with st.sidebar:
    st.header("System Status")

    health = check_health()
    if health:
        status_icon = "✅" if health["status"] == "healthy" else "⚠️"
        st.success(f"{status_icon} Backend: **{health['status'].upper()}**")
        st.info(f"📦 RAG Index: **{health['chunks']} chunks**")
    else:
        st.error("❌ Backend offline — start with `uvicorn main:app --reload`")

    st.divider()
    st.header("How It Works")
    st.markdown("""
1. Select a fault scenario
2. Click **Run Diagnosis**
3. FastAPI → RAG Engine → Qwen3-8B
4. View Root Cause Analysis
""")
    st.divider()
    st.caption("Week 4 · ai-openBMC · Amritapuri")


# ── Main layout — two columns ─────────────────────────────────────────────────

left, right = st.columns([1, 2])

# ── Left: scenario selection ──────────────────────────────────────────────────

with left:
    st.subheader("📋 Select Fault Scenario")

    selected_key = st.selectbox(
        "Scenario",
        options=list(SCENARIO_LABELS.keys()),
        format_func=lambda k: SCENARIO_LABELS[k],
        label_visibility="collapsed",
    )

    # Show the raw event that will be sent
    scenario_events = {
        "dimm_failure"  : {"sensor": "DIMM_B2",  "event": "Memory ECC Error",       "severity": "WARNING"},
        "cpu_overheat"  : {"sensor": "CPU0",      "event": "CPU Over Temperature",    "severity": "CRITICAL"},
        "psu_failure"   : {"sensor": "PSU1",      "event": "Power Supply Failure",    "severity": "CRITICAL"},
        "fan_fault"     : {"sensor": "FAN_3",     "event": "Fan Fault",              "severity": "WARNING"},
        "voltage_fault" : {"sensor": "VR_CPU0",   "event": "Voltage Fault",          "severity": "CRITICAL"},
    }

    ev = scenario_events[selected_key]
    st.markdown("**Event Details:**")
    st.code(
        f"Sensor  : {ev['sensor']}\n"
        f"Event   : {ev['event']}\n"
        f"Severity: {ev['severity']}",
        language="yaml"
    )

    run_btn = st.button("🔍 Run Diagnosis", type="primary", use_container_width=True)

# ── Right: diagnosis result ───────────────────────────────────────────────────

with right:
    st.subheader("🧠 Root Cause Analysis")

    if run_btn:
        if not health:
            st.error("Backend is offline. Cannot run diagnosis.")
        else:
            with st.spinner("Running RAG retrieval + LLM diagnosis..."):
                result = run_diagnosis(selected_key)

            if result and "error" not in result:
                sev   = result.get("severity", "UNKNOWN")
                icon  = SEVERITY_COLORS.get(sev, "⚪")
                imm   = result.get("requires_immediate_action", False)

                # ── Metric cards ──
                m1, m2, m3 = st.columns(3)
                m1.metric("Severity",   f"{icon} {sev}")
                m2.metric("Confidence", result.get("confidence", "—"))
                m3.metric("Immediate?", "YES ⚠️" if imm else "No")

                st.divider()

                # ── Root cause ──
                st.markdown("#### 🔍 Root Cause")
                st.info(result.get("root_cause", "—"))

                # ── Recommendation ──
                st.markdown("#### 🛠️ Recommendation")
                st.success(result.get("recommendation", "—"))

                # ── RAG context used ──
                with st.expander("📚 Knowledge Base Context Used"):
                    st.caption(result.get("rag_context", "—"))

                # ── Full JSON ──
                with st.expander("🗂️ Full Diagnosis JSON"):
                    st.json(result)

                st.caption(
                    f"⏱️ {result.get('duration_ms', 0)} ms  ·  "
                    f"🕐 {result.get('timestamp', '')}"
                )

            elif result and "error" in result:
                st.error(f"Diagnosis failed: {result['error']}")
    else:
        st.markdown("""
        <div style='text-align:center; padding: 60px 20px; color: #666;'>
            <h3>👈 Select a scenario and click Run Diagnosis</h3>
            <p>The AI engine will retrieve relevant knowledge and generate a root cause report.</p>
        </div>
        """, unsafe_allow_html=True)

# ── History section ───────────────────────────────────────────────────────────

st.divider()
st.subheader("📜 Recent Diagnosis History")

history = get_history()
if history:
    for item in history[:5]:
        ev   = item.get("event", {})
        sev  = item.get("severity", "UNKNOWN")
        icon = SEVERITY_COLORS.get(sev, "⚪")
        ts   = item.get("timestamp", "")[:19].replace("T", " ")

        with st.expander(
            f"{icon} `{ev.get('sensor','?')}` — {ev.get('event','?')}  ·  {ts}"
        ):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Root Cause:** {item.get('root_cause','—')}")
            c2.markdown(f"**Recommendation:** {item.get('recommendation','—')}")
else:
    st.caption("No diagnosis history yet — run your first scenario above.")