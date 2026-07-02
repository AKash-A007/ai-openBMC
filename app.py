"""
app.py — Streamlit Dashboard
AI OpsBMC Autonomous Operations Platform

Run with:
    streamlit run app.py
"""

import os

from dotenv import load_dotenv
import urllib3

load_dotenv()  # reads .env automatically, no terminal setup needed
import requests
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
# All values are overridable via .env / environment — see .env.example.

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# QEMU sandbox BMC — distinct from the generic BMC_* vars (reserved for a real
# BMC target), since the QEMU dev image ships with its own fixed credentials.
QEMU_BMC_HOST = os.getenv("QEMU_BMC_HOST", "localhost")
QEMU_BMC_PORT = os.getenv("QEMU_BMC_PORT", "2443")
QEMU_BMC_USERNAME = os.getenv("QEMU_BMC_USERNAME", "root")
QEMU_BMC_PASSWORD = os.getenv("QEMU_BMC_PASSWORD", "0penBmc")
QEMU_BMC_VERIFY_SSL = os.getenv("QEMU_BMC_VERIFY_SSL", "false").lower() == "true"
QEMU_BMC_URL = f"https://{QEMU_BMC_HOST}:{QEMU_BMC_PORT}"

# How long cached backend reads stay fresh before a rerun refetches them.
CACHE_TTL_SECONDS = int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "5"))

# fg (text/border) + bg pairs — keys are matched case-insensitively
STATUS_STYLES = {
    "CRITICAL": ("#B91C1C", "#FEF2F2"),
    "HIGH": ("#C2410C", "#FFF7ED"),
    "MEDIUM": ("#B45309", "#FFFBEB"),
    "LOW": ("#15803D", "#F0FDF4"),
    "UNKNOWN": ("#475569", "#F1F5F9"),
    "SUCCESS": ("#15803D", "#F0FDF4"),
    "HEALTHY": ("#15803D", "#F0FDF4"),
    "ONLINE": ("#15803D", "#F0FDF4"),
    "RESOLVED": ("#15803D", "#F0FDF4"),
    "FAILED": ("#B91C1C", "#FEF2F2"),
    "OFFLINE": ("#B91C1C", "#FEF2F2"),
    "OPEN": ("#B91C1C", "#FEF2F2"),
    "ROLLBACK_FAILED": ("#B91C1C", "#FEF2F2"),
    "PENDING": ("#B45309", "#FFFBEB"),
    "NO_ROLLBACK": ("#B45309", "#FFFBEB"),
    "REJECTED": ("#475569", "#F1F5F9"),
    "MANUAL": ("#475569", "#F1F5F9"),
    "ROLLED_BACK": ("#1D4ED8", "#EFF6FF"),
    "AUTO": ("#1D4ED8", "#EFF6FF"),
}

SCENARIO_LABELS = {
    "dimm_failure": "DIMM Failure — Memory ECC Error",
    "cpu_overheat": "CPU Overheat",
    "psu_failure": "Power Supply Failure",
    "fan_fault": "Fan Fault",
    "voltage_fault": "Voltage Fault",
}

SCENARIO_EVENTS = {
    "dimm_failure": {
        "sensor": "DIMM_B2",
        "event": "Memory ECC Error",
        "severity": "WARNING",
    },
    "cpu_overheat": {
        "sensor": "CPU0",
        "event": "CPU Over Temperature",
        "severity": "CRITICAL",
    },
    "psu_failure": {
        "sensor": "PSU1",
        "event": "Power Supply Failure",
        "severity": "CRITICAL",
    },
    "fan_fault": {"sensor": "FAN_3", "event": "Fan Fault", "severity": "WARNING"},
    "voltage_fault": {
        "sensor": "VR_CPU0",
        "event": "Voltage Fault",
        "severity": "CRITICAL",
    },
}


# ── UI helpers ────────────────────────────────────────────────────────────────


def pill(text: str, fg: str, bg: str) -> str:
    return (
        f'<span class="badge" style="color:{fg};background:{bg};'
        f'border:1px solid {fg}33;">{text}</span>'
    )


def status_badge(status: str) -> str:
    fg, bg = STATUS_STYLES.get((status or "").upper(), ("#475569", "#F1F5F9"))
    return pill((status or "UNKNOWN").upper(), fg, bg)


def stat_block(label: str, value_html: str) -> None:
    st.markdown(
        f"""
        <div class="stat-block">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── API helpers ───────────────────────────────────────────────────────────────


@st.cache_data(ttl=CACHE_TTL_SECONDS)
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
            timeout=60,  # LLM call can take a moment
        )
        return (
            r.json()
            if r.status_code == 200
            else {"error": r.json().get("detail", "API error")}
        )
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_history() -> list:
    try:
        r = requests.get(f"{API_BASE}/results?limit=10", timeout=5)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception:
        return []


def remediate(issue: str, action: str, sensor: str, severity: str) -> dict:
    try:
        r = requests.post(
            f"{API_BASE}/remediate",
            json={
                "issue": issue,
                "action": action,
                "sensor": sensor,
                "severity": severity,
            },
            timeout=30,
        )
        return (
            r.json()
            if r.status_code == 200
            else {"error": r.json().get("detail", "Remediation error")}
        )
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_approvals() -> dict:
    try:
        r = requests.get(f"{API_BASE}/approvals", timeout=5)
        return (
            r.json()
            if r.status_code == 200
            else {"total": 0, "requests": [], "stats": {}}
        )
    except Exception:
        return {"total": 0, "requests": [], "stats": {}}


def approve_action(request_id: str) -> dict:
    try:
        r = requests.post(
            f"{API_BASE}/approvals/{request_id}/approve",
            json={"resolved_by": "ops-dashboard"},
            timeout=30,
        )
        return (
            r.json()
            if r.status_code == 200
            else {"error": r.json().get("detail", "Approve failed")}
        )
    except Exception as e:
        return {"error": str(e)}


def reject_action(request_id: str) -> dict:
    try:
        r = requests.post(
            f"{API_BASE}/approvals/{request_id}/reject",
            json={"resolved_by": "ops-dashboard", "notes": "Rejected from dashboard"},
            timeout=10,
        )
        return (
            r.json()
            if r.status_code == 200
            else {"error": r.json().get("detail", "Reject failed")}
        )
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_audit_log() -> dict:
    try:
        r = requests.get(f"{API_BASE}/audit?limit=30", timeout=5)
        return (
            r.json()
            if r.status_code == 200
            else {"total": 0, "entries": [], "stats": {}}
        )
    except Exception:
        return {"total": 0, "entries": [], "stats": {}}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_incidents() -> dict:
    try:
        r = requests.get(f"{API_BASE}/incidents?limit=10", timeout=5)
        return r.json() if r.status_code == 200 else {"total": 0, "incidents": []}
    except Exception:
        return {"total": 0, "incidents": []}


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def check_bmc() -> dict:
    """Quick probe — just hits /redfish/v1, doesn't save anything."""
    try:
        resp = requests.get(
            f"{QEMU_BMC_URL}/redfish/v1",
            auth=(QEMU_BMC_USERNAME, QEMU_BMC_PASSWORD),
            verify=QEMU_BMC_VERIFY_SSL,
            timeout=3,
        )
        if resp.status_code == 200:
            return {"status": "online"}
        return {"status": "error", "code": resp.status_code}
    except Exception:
        return {"status": "offline"}


def clear_dashboard_cache() -> None:
    """Invalidate all cached backend reads — call after any mutating action."""
    check_health.clear()
    get_history.clear()
    get_approvals.clear()
    get_audit_log.clear()
    get_incidents.clear()


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI OpsBMC — Autonomous Operations",
    page_icon=":material/dns:",
    layout="wide",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 4rem; padding-bottom: 3rem; max-width: 1200px; }

        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.03em;
        }

        .stat-block { padding: 2px 0 10px 0; }
        .stat-label {
            font-size: 0.72rem; font-weight: 600; color: #64748B;
            text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 5px;
        }
        .stat-value { font-size: 1rem; color: #0F172A; }

        .app-header { display: flex; align-items: center; gap: 14px; margin-bottom: 4px; }
        .app-logo {
            width: 40px; height: 40px; border-radius: 9px;
            background: linear-gradient(135deg, #2563EB, #1D4ED8);
            color: #fff; display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 1.05rem; letter-spacing: -0.02em;
        }
        .app-title { font-size: 1.55rem; font-weight: 700; color: #0F172A; margin: 0; line-height: 1.2; }
        .app-subtitle { color: #64748B; font-size: 0.9rem; margin-top: 1px; }

        .empty-state {
            text-align: center; padding: 56px 20px; color: #64748B;
            border: 1px dashed #E2E8F0; border-radius: 10px; background: #FAFAFA;
        }
        .empty-state h4 { color: #0F172A; margin-bottom: 6px; }

        .entry-row { padding: 10px 0; border-bottom: 1px solid #F1F5F9; }
        .entry-row:last-child { border-bottom: none; }
        .entry-title { font-weight: 600; color: #0F172A; font-size: 0.92rem; }
        .entry-meta { color: #64748B; font-size: 0.8rem; margin-top: 2px; }

        section[data-testid="stSidebar"] h3 {
            font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        """
        <div class="app-header">
            <div class="app-logo">AI</div>
            <div>
                <p class="app-title">AI OpsBMC</p>
                <p class="app-subtitle">Autonomous AIOps Platform · Detect → Diagnose → Predict → Recommend → Approve → Execute → Audit</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_right:
    st.write("")
    if st.button(
        "Refresh data",
        icon=":material/refresh:",
        width="stretch",
        help=f"Cached reads auto-refresh every {CACHE_TTL_SECONDS}s — click to force now",
    ):
        clear_dashboard_cache()
        check_bmc.clear()
        st.rerun()
st.divider()

# ── Sidebar — health + info ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### System Status")

    health = check_health()
    if health:
        st.markdown(
            status_badge(health["status"]) + "  Backend",
            unsafe_allow_html=True,
        )
        st.caption(f"RAG index — {health['chunks']} chunks loaded")
    else:
        st.markdown(status_badge("OFFLINE") + "  Backend", unsafe_allow_html=True)
        st.caption("Start the API with `uvicorn main:app --reload`")

    st.divider()
    st.markdown("### Pipeline")
    st.markdown(
        """
1. **Detect** — Telemetry anomaly
2. **Diagnose** — RAG + LLM root cause
3. **Predict** — Failure probability
4. **Recommend** — Action suggestion
5. **Approve** — Policy gate
6. **Execute** — Autonomous action
7. **Audit** — Full trail
"""
    )
    st.divider()
    st.caption("ai-openBMC · Amritapuri")

    st.divider()
    st.markdown("### Live QEMU Mode")

    bmc = check_bmc()

    if bmc["status"] == "online":
        st.markdown(status_badge("ONLINE") + "  QEMU BMC", unsafe_allow_html=True)
        bmc_ready = True
    elif bmc["status"] == "error":
        st.markdown(status_badge("PENDING") + "  Still booting?", unsafe_allow_html=True)
        st.caption(f"BMC responded with HTTP {bmc.get('code')}")
        bmc_ready = False
    else:
        st.markdown(status_badge("OFFLINE") + "  QEMU BMC", unsafe_allow_html=True)
        with st.expander("Show launch command"):
            st.code(
                "qemu-system-arm \\\n"
                "  -machine romulus-bmc \\\n"
                "  -m 512 \\\n"
                "  -drive file=tmp/deploy/images/romulus/\n"
                "    obmc-phosphor-image-romulus.static.mtd,\n"
                "    if=mtd,format=raw \\\n"
                "  -serial mon:stdio -serial null \\\n"
                "  -netdev user,id=net0,hostfwd=tcp::2443-:443 \\\n"
                "  -net nic,netdev=net0",
                language="bash",
            )
        bmc_ready = False

    st.write("")

    if st.button(
        "Fetch from QEMU",
        icon=":material/cloud_download:",
        width="stretch",
        disabled=not bmc_ready,
    ):
        with st.spinner("Fetching live data from OpenBMC..."):
            try:
                r = requests.post(f"{API_BASE}/fetch", timeout=15)
                if r.status_code == 200:
                    st.success("Live data fetched", icon=":material/check_circle:")
                    st.session_state["live_fetched"] = True
                else:
                    detail = r.json().get("detail", {})
                    err = detail.get("error", "Fetch failed")
                    msg = detail.get("message", str(detail))
                    hint = detail.get("hint", "")

                    if err == "BMC_NOT_FOUND":
                        st.error("No BMC found — QEMU is not running", icon=":material/error:")
                    elif err == "BMC_TIMEOUT":
                        st.warning("BMC timeout — QEMU still booting, retry shortly", icon=":material/hourglass_top:")
                    else:
                        st.error(msg, icon=":material/error:")

                    if hint:
                        st.caption(hint)
                    st.session_state["live_fetched"] = False

            except Exception as e:
                st.error(f"Cannot reach FastAPI backend: {e}", icon=":material/error:")
                st.session_state["live_fetched"] = False

    if not bmc_ready:
        st.caption("Start QEMU to enable live fetch")

    live_ready = st.session_state.get("live_fetched", False)

    if st.button(
        "Diagnose Live Events",
        icon=":material/psychology:",
        width="stretch",
        disabled=not live_ready,
        type="primary" if live_ready else "secondary",
    ):
        with st.spinner("Diagnosing real QEMU events..."):
            try:
                r = requests.get(f"{API_BASE}/diagnose/live", timeout=120)
                if r.status_code == 200:
                    st.session_state["live_results"] = r.json()
                else:
                    st.error(r.json().get("detail", "Diagnosis failed"), icon=":material/error:")
            except Exception as e:
                st.error(f"Error: {e}", icon=":material/error:")

    if not live_ready:
        st.caption("Fetch from QEMU first to enable live diagnosis")


# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_diagnosis, tab_ops, tab_audit = st.tabs(
    ["Diagnosis", "Operations Hub", "Audit & Timeline"]
)

# ── Tab 1: Diagnosis ─────────────────────────────────────────────────────────

with tab_diagnosis:
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.markdown("#### Select Fault Scenario")

        selected_key = st.selectbox(
            "Scenario",
            options=list(SCENARIO_LABELS.keys()),
            format_func=lambda k: SCENARIO_LABELS[k],
            label_visibility="collapsed",
        )

        ev = SCENARIO_EVENTS[selected_key]
        st.markdown("**Event details**")
        st.code(
            f"Sensor  : {ev['sensor']}\n"
            f"Event   : {ev['event']}\n"
            f"Severity: {ev['severity']}",
            language="yaml",
        )

        b1, b2 = st.columns(2)
        run_btn = b1.button(
            "Run Diagnosis",
            icon=":material/troubleshoot:",
            type="primary",
            width="stretch",
        )
        remediate_btn = b2.button(
            "Auto-Remediate",
            icon=":material/bolt:",
            type="secondary",
            width="stretch",
            disabled=not health,
            help="Run diagnosis then auto-execute via Policy Engine",
        )

    with right:
        st.markdown("#### Root Cause Analysis")

        if run_btn:
            if not health:
                st.error("Backend is offline. Cannot run diagnosis.", icon=":material/error:")
            else:
                with st.spinner("Running RAG retrieval + LLM diagnosis..."):
                    result = run_diagnosis(selected_key)

                if result and "error" not in result:
                    get_history.clear()
                    sev = result.get("severity", "UNKNOWN")
                    imm = result.get("requires_immediate_action", False)

                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            stat_block("Severity", status_badge(sev))
                        with c2:
                            stat_block("Confidence", result.get("confidence", "—"))
                        with c3:
                            imm_badge = (
                                pill("REQUIRED", "#B91C1C", "#FEF2F2")
                                if imm
                                else pill("NOT REQUIRED", "#15803D", "#F0FDF4")
                            )
                            stat_block("Immediate action", imm_badge)

                    st.write("")
                    st.markdown("**Root cause**")
                    st.info(result.get("root_cause", "—"), icon=":material/search:")

                    st.markdown("**Recommendation**")
                    st.success(result.get("recommendation", "—"), icon=":material/build:")

                    with st.expander("Knowledge base context used"):
                        st.caption(result.get("rag_context", "—"))

                    with st.expander("Full diagnosis JSON"):
                        st.json(result)

                    st.caption(
                        f"{result.get('duration_ms', 0)} ms · {result.get('timestamp', '')}"
                    )

                elif result and "error" in result:
                    st.error(f"Diagnosis failed: {result['error']}", icon=":material/error:")
        elif remediate_btn:
            if not health:
                st.error("Backend is offline.", icon=":material/error:")
            else:
                with st.spinner("Running diagnosis..."):
                    result = run_diagnosis(selected_key)
                if result and "error" not in result:
                    rec = result.get("recommendation", "")
                    sensor = result.get("event", {}).get("sensor", ev["sensor"])
                    sev = result.get("severity", "UNKNOWN")

                    st.markdown(f"**Diagnosis:** {result.get('root_cause', '—')}")
                    st.markdown(f"**Recommendation:** `{rec}`")

                    with st.spinner(f"Routing '{rec}' through Policy Engine..."):
                        rem_result = remediate(
                            issue=selected_key.upper(),
                            action=rec,
                            sensor=sensor,
                            severity=sev,
                        )

                    clear_dashboard_cache()

                    if "error" in rem_result:
                        st.error(f"Remediation error: {rem_result['error']}", icon=":material/error:")
                    elif rem_result.get("mode") == "AUTO":
                        status = rem_result.get("status", "")
                        if rem_result.get("success"):
                            st.success(
                                f"**Auto-executed** — `{rec}` · status: {status_badge(status)}",
                                icon=":material/check_circle:",
                            )
                            st.markdown(status_badge(status), unsafe_allow_html=True)
                            st.caption(rem_result.get("details", ""))
                        else:
                            st.warning(f"Executed with issues · status: {status}", icon=":material/warning:")
                            st.markdown(status_badge(status), unsafe_allow_html=True)
                            if rem_result.get("rollback"):
                                st.info(
                                    f"Rollback: {rem_result['rollback'].get('status')}",
                                    icon=":material/undo:",
                                )
                    else:
                        st.warning(
                            f"**Manual approval required** — `{rec}`",
                            icon=":material/lock:",
                        )
                        st.caption(
                            f"Approval ID: `{rem_result.get('approval_id', '?')}` · "
                            "review it in the Operations Hub tab."
                        )
                else:
                    st.error(
                        f"Diagnosis failed: {result.get('error') if result else 'No response'}",
                        icon=":material/error:",
                    )
        else:
            st.markdown(
                """
                <div class="empty-state">
                    <h4>Select a scenario and click Run Diagnosis</h4>
                    <p>The AI engine will retrieve relevant knowledge and generate a root cause report.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── History ──────────────────────────────────────────────────────────────

    st.divider()
    st.markdown("#### Recent Diagnosis History")

    history = get_history()
    if history:
        for item in history[:5]:
            hev = item.get("event", {})
            sev = item.get("severity", "UNKNOWN")
            ts = item.get("timestamp", "")[:19].replace("T", " ")

            with st.expander(
                f"{hev.get('sensor','?')} — {hev.get('event','?')} · {sev} · {ts}"
            ):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Root cause:** {item.get('root_cause','—')}")
                c2.markdown(f"**Recommendation:** {item.get('recommendation','—')}")
    else:
        st.caption("No diagnosis history yet — run your first scenario above.")

    # ── Live QEMU results ────────────────────────────────────────────────────

    if "live_results" in st.session_state:
        data = st.session_state["live_results"]
        st.divider()
        st.markdown("#### Live QEMU Diagnosis Results")

        results = data.get("results", [])

        if not results:
            st.success("No faults detected — QEMU system is healthy", icon=":material/check_circle:")
        else:
            st.warning(f"{len(results)} fault(s) detected in live QEMU data", icon=":material/warning:")

            for i, item in enumerate(results, 1):
                if "error" in item:
                    st.error(f"Event {i}: {item['error']}", icon=":material/error:")
                    continue

                lev = item.get("event", {})
                sev = item.get("severity", "UNKNOWN")

                with st.expander(
                    f"[{i}] {lev.get('sensor','?')} — {lev.get('event','?')} · {sev}",
                    expanded=True,
                ):
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            stat_block("Severity", status_badge(sev))
                        with c2:
                            stat_block("Confidence", item.get("confidence", "—"))
                        with c3:
                            imm_badge = (
                                pill("REQUIRED", "#B91C1C", "#FEF2F2")
                                if item.get("requires_immediate_action")
                                else pill("NOT REQUIRED", "#15803D", "#F0FDF4")
                            )
                            stat_block("Immediate action", imm_badge)

                    st.markdown(f"**Root cause:** {item.get('root_cause','—')}")
                    st.markdown(f"**Recommendation:** {item.get('recommendation','—')}")

                    with st.expander("RAG context"):
                        st.caption(item.get("rag_context", "—"))


# ── Tab 2: Operations Hub ────────────────────────────────────────────────────

with tab_ops:
    st.caption("Policy Engine → Execution Engine → Rollback Manager → Audit Logger")

    panel1, panel2, panel3 = st.columns(3, gap="medium")

    with panel1:
        with st.container(border=True):
            st.markdown("**Active Incidents**")
            incidents_data = get_incidents()
            incidents = incidents_data.get("incidents", [])
            if not incidents:
                st.caption("No active incidents")
            else:
                for inc in incidents[:4]:
                    sev = inc.get("severity", "UNKNOWN")
                    resolved_badge = (
                        pill("RESOLVED", "#15803D", "#F0FDF4")
                        if inc.get("resolved")
                        else pill("OPEN", "#B91C1C", "#FEF2F2")
                    )
                    st.markdown(
                        f"""
                        <div class="entry-row">
                            <div class="entry-title">{inc.get('issue','?')}</div>
                            <div class="entry-meta"><code>{inc.get('sensor','?')}</code> · {status_badge(sev)} · {resolved_badge}</div>
                            <div class="entry-meta">Action: <code>{inc.get('action','?')}</code></div>
                            <div class="entry-meta">Detected {str(inc.get('detected_at',''))[:19].replace('T',' ')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with panel2:
        with st.container(border=True):
            st.markdown("**Executed Actions**")
            audit_data = get_audit_log()
            entries = [
                e for e in audit_data.get("entries", []) if e.get("status") == "SUCCESS"
            ]
            if not entries:
                st.caption("No executed actions yet")
            else:
                for entry in entries[:4]:
                    ts = str(entry.get("timestamp", ""))[:19].replace("T", " ")
                    st.markdown(
                        f"""
                        <div class="entry-row">
                            <div class="entry-title">{entry.get('action','?')}</div>
                            <div class="entry-meta"><code>{entry.get('sensor','?')}</code> · {entry.get('issue','?')}</div>
                            <div class="entry-meta">{ts} · {entry.get('policy','?')} · {entry.get('executed_by','?')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with panel3:
        with st.container(border=True):
            st.markdown("**Pending Approvals**")
            approvals_data = get_approvals()
            pending = [
                r
                for r in approvals_data.get("requests", [])
                if r.get("status") == "PENDING"
            ]
            if not pending:
                st.caption("No actions awaiting approval")
            else:
                st.warning(f"{len(pending)} action(s) waiting for approval", icon=":material/hourglass_top:")
                for req in pending:
                    st.markdown(
                        f"""
                        <div class="entry-row">
                            <div class="entry-title">{req.get('action','?')}</div>
                            <div class="entry-meta"><code>{req.get('sensor','?')}</code> · {req.get('issue','?')} · {status_badge(req.get('severity','UNKNOWN'))}</div>
                            <div class="entry-meta">Requested {str(req.get('requested_at',''))[:19].replace('T',' ')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    req_id = req.get("id", "")
                    col_a, col_r = st.columns(2)
                    if col_a.button(
                        "Approve",
                        icon=":material/check:",
                        key=f"approve_{req_id}",
                        width="stretch",
                    ):
                        with st.spinner("Approving and executing..."):
                            res = approve_action(req_id)
                        if "error" in res:
                            st.error(res["error"], icon=":material/error:")
                        else:
                            clear_dashboard_cache()
                            st.success(f"Executed — status {res.get('status','?')}", icon=":material/check_circle:")
                            st.rerun()
                    if col_r.button(
                        "Reject",
                        icon=":material/close:",
                        key=f"reject_{req_id}",
                        width="stretch",
                    ):
                        res = reject_action(req_id)
                        if "error" in res:
                            st.error(res["error"], icon=":material/error:")
                        else:
                            clear_dashboard_cache()
                            st.info("Action rejected.", icon=":material/info:")
                            st.rerun()


# ── Tab 3: Audit & Timeline ──────────────────────────────────────────────────

with tab_audit:
    st.markdown("#### Audit Log")
    st.caption("Every autonomous action — who, what, when, why, outcome")

    audit_data = get_audit_log()
    entries = audit_data.get("entries", [])
    stats = audit_data.get("stats", {})

    if stats:
        sa, sb, sc, sd = st.columns(4)
        sa.metric("Success", stats.get("SUCCESS", 0))
        sb.metric("Failed", stats.get("FAILED", 0))
        sc.metric("Pending", stats.get("PENDING", 0))
        sd.metric("Rejected", stats.get("REJECTED", 0))

    if not entries:
        st.caption("Audit log is empty. Run Auto-Remediate to create entries.")
    else:
        import pandas as pd

        df_rows = []
        for e in entries:
            ts = str(e.get("timestamp", ""))[:19].replace("T", " ")
            df_rows.append(
                {
                    "Time": ts,
                    "Status": e.get("status", ""),
                    "Action": e.get("action", ""),
                    "Issue": e.get("issue", ""),
                    "Sensor": e.get("sensor", ""),
                    "Policy": e.get("policy", ""),
                    "By": e.get("executed_by", ""),
                    "ms": round(e.get("duration_ms", 0), 1),
                }
            )
        st.dataframe(pd.DataFrame(df_rows), width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### Incident Timeline")
    st.caption("Full lifecycle: Detected → Diagnosed → Executed → Resolved")

    inc_data = get_incidents()
    incidents = inc_data.get("incidents", [])

    if not incidents:
        st.caption("No incidents recorded yet. Run Auto-Remediate to create incidents.")
    else:
        for inc in incidents[:5]:
            sev = inc.get("severity", "UNKNOWN")
            resolved = inc.get("resolved", False)
            status_label = "RESOLVED" if resolved else "OPEN"
            policy = inc.get("policy", "")
            policy_label = "AUTO" if policy == "AUTO" else "MANUAL"

            with st.expander(
                f"{inc.get('issue','?')} — {inc.get('action','?')} · {status_label} · {policy_label}",
                expanded=False,
            ):
                top1, top2, top3 = st.columns(3)
                with top1:
                    stat_block("Severity", status_badge(sev))
                with top2:
                    stat_block("Status", status_badge(status_label))
                with top3:
                    stat_block("Policy", status_badge(policy_label))

                steps = []
                if inc.get("detected_at"):
                    steps.append(("Detected", inc["detected_at"]))
                if inc.get("approved_at"):
                    steps.append(("Approved", inc["approved_at"]))
                if inc.get("executed_at"):
                    steps.append(("Executed", inc["executed_at"]))
                if inc.get("resolved_at"):
                    steps.append(("Resolved", inc["resolved_at"]))

                for step_label, step_ts in steps:
                    ts_str = str(step_ts)[:19].replace("T", " ")
                    st.markdown(f"**{step_label}** &nbsp; `{ts_str}`")

                if inc.get("execution"):
                    ex = inc["execution"]
                    st.markdown(
                        f"**Result:** {ex.get('status','?')} — {ex.get('details','')[:120]}"
                    )
                    if ex.get("rollback"):
                        rb = ex["rollback"]
                        st.info(
                            f"Rollback: {rb.get('status','?')} — {rb.get('details','')[:100]}",
                            icon=":material/undo:",
                        )
