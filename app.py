"""
app.py  —  Phase C Week 4 Streamlit Dashboard
AI OpsBMC Autonomous Operations Platform

Run with:
    streamlit run app.py
"""

from dotenv import load_dotenv
import urllib3

load_dotenv()  # reads .env automatically, no terminal setup needed
import requests
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
    "UNKNOWN": "⚪",
}

SCENARIO_LABELS = {
    "dimm_failure": "💾 DIMM Failure (Memory ECC Error)",
    "cpu_overheat": "🔥 CPU Overheat",
    "psu_failure": "⚡ Power Supply Failure",
    "fan_fault": "🌀 Fan Fault",
    "voltage_fault": "⚠️ Voltage Fault",
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
            timeout=60,  # LLM call can take a moment
        )
        return (
            r.json()
            if r.status_code == 200
            else {"error": r.json().get("detail", "API error")}
        )
    except Exception as e:
        return {"error": str(e)}


def get_history() -> list:
    try:
        r = requests.get(f"{API_BASE}/results?limit=10", timeout=5)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception:
        return []


# ── Phase C Week 4: New API helper functions ─────────────────────────────────


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


def get_incidents() -> dict:
    try:
        r = requests.get(f"{API_BASE}/incidents?limit=10", timeout=5)
        return r.json() if r.status_code == 200 else {"total": 0, "incidents": []}
    except Exception:
        return {"total": 0, "incidents": []}


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI OpsBMC — Autonomous Operations",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AI OpsBMC — Autonomous Enterprise AIOps Platform")
st.caption(
    "Phase C Week 4 · Detect → Diagnose → Predict → Recommend → **Approve → Execute → Audit**"
)

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
    st.header("Pipeline")
    st.markdown("""
1. 🔍 **Detect** — Telemetry anomaly
2. 🧠 **Diagnose** — RAG + LLM root cause
3. 📈 **Predict** — Failure probability
4. 🛠️ **Recommend** — Action suggestion
5. ✅ **Approve** — Policy gate
6. ⚡ **Execute** — Autonomous action
7. 📓 **Audit** — Full trail
""")
    st.divider()
    st.caption("Phase C Week 4 · ai-openBMC · Amritapuri")

    st.divider()
    st.subheader("🔴 Live QEMU Mode")

    # ── BMC connection check (fast, separate from fetch) ──────────────────
    def check_bmc() -> dict:
        """Quick probe — just hits /redfish/v1, doesn't save anything."""
        try:
            import requests as _r

            resp = _r.get(
                "https://localhost:2443/redfish/v1",
                auth=("root", "0penBmc"),
                verify=False,
                timeout=3,
            )
            if resp.status_code == 200:
                return {"status": "online"}
            return {"status": "error", "code": resp.status_code}
        except Exception:
            return {"status": "offline"}

    bmc = check_bmc()

    # Show BMC status badge
    if bmc["status"] == "online":
        st.success("🟢 BMC Online — QEMU is running")
        bmc_ready = True
    elif bmc["status"] == "error":
        st.warning(f"🟡 BMC responded with error {bmc.get('code')} — still booting?")
        bmc_ready = False
    else:
        st.error("🔴 No BMC Found — QEMU is not running")
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

    st.divider()

    # ── Step 1: Fetch button (disabled if BMC offline) ─────────────────────
    if st.button(
        "📡 Fetch from QEMU",
        use_container_width=True,
        disabled=not bmc_ready,
    ):
        with st.spinner("Fetching live data from OpenBMC..."):
            try:
                r = requests.post(f"{API_BASE}/fetch", timeout=15)
                if r.status_code == 200:
                    st.success("✅ Live data fetched!")
                    st.session_state["live_fetched"] = True
                else:
                    # Parse structured error from FastAPI
                    detail = r.json().get("detail", {})
                    err = detail.get("error", "Fetch failed")
                    msg = detail.get("message", str(detail))
                    hint = detail.get("hint", "")

                    if err == "BMC_NOT_FOUND":
                        st.error("🔴 No BMC Found — QEMU is not running")
                    elif err == "BMC_TIMEOUT":
                        st.warning(
                            "🟡 BMC Timeout — QEMU still booting, wait and retry"
                        )
                    else:
                        st.error(f"❌ {msg}")

                    if hint:
                        st.caption(f"💡 {hint}")
                    st.session_state["live_fetched"] = False

            except Exception as e:
                st.error(f"❌ Cannot reach FastAPI backend: {e}")
                st.session_state["live_fetched"] = False

    if not bmc_ready:
        st.caption("⬆️ Start QEMU to enable live fetch")

    # ── Step 2: Diagnose live (only enabled after successful fetch) ─────────
    live_ready = st.session_state.get("live_fetched", False)

    if st.button(
        "🧠 Diagnose Live Events",
        use_container_width=True,
        disabled=not live_ready,
        type="primary" if live_ready else "secondary",
    ):
        with st.spinner("Diagnosing real QEMU events..."):
            try:
                r = requests.get(f"{API_BASE}/diagnose/live", timeout=120)
                if r.status_code == 200:
                    st.session_state["live_results"] = r.json()
                else:
                    st.error(f"❌ {r.json().get('detail', 'Diagnosis failed')}")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    if not live_ready:
        st.caption("⬆️ Fetch from QEMU first to enable live diagnosis")


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

    ev = scenario_events[selected_key]
    st.markdown("**Event Details:**")
    st.code(
        f"Sensor  : {ev['sensor']}\n"
        f"Event   : {ev['event']}\n"
        f"Severity: {ev['severity']}",
        language="yaml",
    )

    b1, b2 = st.columns(2)
    run_btn = b1.button("🔍 Run Diagnosis", type="primary", use_container_width=True)
    remediate_btn = b2.button(
        "🔧 Auto-Remediate",
        type="secondary",
        use_container_width=True,
        disabled=not health,
        help="Run diagnosis then auto-execute via Policy Engine",
    )

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
                sev = result.get("severity", "UNKNOWN")
                icon = SEVERITY_COLORS.get(sev, "⚪")
                imm = result.get("requires_immediate_action", False)

                # ── Metric cards ──
                m1, m2, m3 = st.columns(3)
                m1.metric("Severity", f"{icon} {sev}")
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
    elif remediate_btn:
        if not health:
            st.error("Backend is offline.")
        else:
            with st.spinner("🧠 Running diagnosis..."):
                result = run_diagnosis(selected_key)
            if result and "error" not in result:
                # Store last diagnosis for display
                rec = result.get("recommendation", "")
                sensor = result.get("event", {}).get("sensor", ev["sensor"])
                sev = result.get("severity", "UNKNOWN")

                st.markdown(f"**🧠 Diagnosis:** {result.get('root_cause', '—')}")
                st.markdown(f"**🛠️ Recommendation:** `{rec}`")

                with st.spinner(f"⚡ Routing '{rec}' through Policy Engine..."):
                    rem_result = remediate(
                        issue=selected_key.upper(),
                        action=rec,
                        sensor=sensor,
                        severity=sev,
                    )

                if "error" in rem_result:
                    st.error(f"❌ Remediation error: {rem_result['error']}")
                elif rem_result.get("mode") == "AUTO":
                    status = rem_result.get("status", "")
                    if rem_result.get("success"):
                        st.success(
                            f"✅ **AUTO-EXECUTED** — `{rec}` | Status: **{status}**"
                        )
                        st.caption(rem_result.get("details", ""))
                    else:
                        st.warning(
                            f"⚠️ **EXECUTED with issues** | Status: **{status}**"
                        )
                        if rem_result.get("rollback"):
                            st.info(
                                f"↩️ Rollback: {rem_result['rollback'].get('status')}"
                            )
                else:
                    st.warning(
                        f"🔒 **MANUAL APPROVAL REQUIRED** — `{rec}`\n\n"
                        f"Approval ID: `{rem_result.get('approval_id', '?')}`\n"
                        "Go to **Pending Approvals** panel below to approve or reject."
                    )
            else:
                st.error(
                    f"Diagnosis failed: {result.get('error') if result else 'No response'}"
                )
    else:
        st.markdown(
            """
        <div style='text-align:center; padding: 60px 20px; color: #666;'>
            <h3>👈 Select a scenario and click Run Diagnosis</h3>
            <p>The AI engine will retrieve relevant knowledge and generate a root cause report.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

# ── History section ───────────────────────────────────────────────────────────

st.divider()
st.subheader("📜 Recent Diagnosis History")

history = get_history()
if history:
    for item in history[:5]:
        ev = item.get("event", {})
        sev = item.get("severity", "UNKNOWN")
        icon = SEVERITY_COLORS.get(sev, "⚪")
        ts = item.get("timestamp", "")[:19].replace("T", " ")

        with st.expander(
            f"{icon} `{ev.get('sensor','?')}` — {ev.get('event','?')}  ·  {ts}"
        ):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Root Cause:** {item.get('root_cause','—')}")
            c2.markdown(f"**Recommendation:** {item.get('recommendation','—')}")
else:
    st.caption("No diagnosis history yet — run your first scenario above.")
# ── Live QEMU Results ─────────────────────────────────────────────────────────

if "live_results" in st.session_state:
    data = st.session_state["live_results"]
    st.divider()
    st.subheader("🔴 Live QEMU Diagnosis Results")

    results = data.get("results", [])

    if not results:
        st.success("✅ No faults detected — QEMU system is healthy")
    else:
        st.warning(f"⚠️ {len(results)} fault(s) detected in live QEMU data")

        for i, item in enumerate(results, 1):
            if "error" in item:
                st.error(f"Event {i}: {item['error']}")
                continue

            ev = item.get("event", {})
            sev = item.get("severity", "UNKNOWN")
            icon = SEVERITY_COLORS.get(sev, "⚪")

            with st.expander(
                f"{icon} [{i}] `{ev.get('sensor','?')}` — " f"{ev.get('event','?')}",
                expanded=True,
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("Severity", f"{icon} {sev}")
                c2.metric("Confidence", item.get("confidence", "—"))
                c3.metric(
                    "Immediate?",
                    "YES ⚠️" if item.get("requires_immediate_action") else "No",
                )

                st.markdown(f"**🔍 Root Cause:** {item.get('root_cause','—')}")
                st.markdown(f"**🛠️ Recommendation:** {item.get('recommendation','—')}")

                with st.expander("📚 RAG Context"):
                    st.caption(item.get("rag_context", "—"))


# ─────────────────────────────────────────────────────────────
# Phase C Week 4 — NEW ENTERPRISE AIOPS PANELS
# ─────────────────────────────────────────────────────────────

st.divider()
st.markdown("## 🏭 Autonomous Operations Hub")
st.caption("Policy Engine → Execution Engine → Rollback Manager → Audit Logger")

panel1, panel2, panel3 = st.columns(3)

# ── Panel 1: Quick stats ──────────────────────────────────────────────────────
with panel1:
    st.markdown("### 📅 Active Incidents")
    incidents_data = get_incidents()
    incidents = incidents_data.get("incidents", [])
    if not incidents:
        st.caption("✓ No active incidents")
    else:
        for inc in incidents[:4]:
            sev = inc.get("severity", "UNKNOWN")
            icon = SEVERITY_COLORS.get(sev, "⚪")
            resolved = "✅" if inc.get("resolved") else "🔴"
            st.markdown(
                f"{resolved} {icon} **{inc.get('issue','?')}**\n\n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;`{inc.get('sensor','?')}` — {sev}\n\n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;💻 `{inc.get('action','?')}`"
            )
            st.caption(
                f"Detected: {str(inc.get('detected_at',''))[:19].replace('T',' ')}"
            )
            st.markdown("---")

with panel2:
    st.markdown("### ⚡ Executed Actions")
    audit_data = get_audit_log()
    entries = [e for e in audit_data.get("entries", []) if e.get("status") == "SUCCESS"]
    if not entries:
        st.caption("No executed actions yet")
    else:
        for entry in entries[:4]:
            ts = str(entry.get("timestamp", ""))[:19].replace("T", " ")
            st.markdown(
                f"✅ **{entry.get('action','?')}**\n\n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;📌 `{entry.get('sensor','?')}` | {entry.get('issue','?')}"
            )
            st.caption(
                f"{ts} · {entry.get('policy','?')} · {entry.get('executed_by','?')}"
            )
            st.markdown("---")

with panel3:
    st.markdown("### 🔒 Pending Approvals")
    approvals_data = get_approvals()
    pending = [
        r for r in approvals_data.get("requests", []) if r.get("status") == "PENDING"
    ]
    if not pending:
        st.success("✓ No actions awaiting approval")
    else:
        st.warning(f"⏳ {len(pending)} action(s) waiting for approval")
        for req in pending:
            st.markdown(
                f"🔒 **{req.get('action','?')}**\n\n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;📌 `{req.get('sensor','?')}` | {req.get('issue','?')} | {req.get('severity','?')}"
            )
            ts = str(req.get("requested_at", ""))[:19].replace("T", " ")
            st.caption(f"Requested: {ts}")
            req_id = req.get("id", "")
            col_a, col_r = st.columns(2)
            if col_a.button(
                "✅ Approve", key=f"approve_{req_id}", use_container_width=True
            ):
                with st.spinner("Approving and executing..."):
                    res = approve_action(req_id)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.success(f"Executed! Status: {res.get('status','?')}")
                    st.rerun()
            if col_r.button(
                "❌ Reject", key=f"reject_{req_id}", use_container_width=True
            ):
                res = reject_action(req_id)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.info("Action rejected.")
                    st.rerun()
            st.markdown("---")


# ── Audit Log panel ────────────────────────────────────────────────────────────

st.divider()
st.subheader("📓 Audit Log")
st.caption("Every autonomous action — who, what, when, why, outcome")

audit_data = get_audit_log()
entries = audit_data.get("entries", [])
stats = audit_data.get("stats", {})

if stats:
    sa, sb, sc, sd = st.columns(4)
    sa.metric("✅ Success", stats.get("SUCCESS", 0))
    sb.metric("❌ Failed", stats.get("FAILED", 0))
    sc.metric("⏳ Pending", stats.get("PENDING", 0))
    sd.metric("❌ Rejected", stats.get("REJECTED", 0))

if not entries:
    st.caption("Audit log is empty. Run Auto-Remediate to create entries.")
else:
    STATUS_ICON = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "ROLLED_BACK": "↩️",
        "ROLLBACK_FAILED": "🚨",
        "NO_ROLLBACK": "⚠️",
        "PENDING": "⏳",
        "REJECTED": "🚫",
    }
    import pandas as pd

    df_rows = []
    for e in entries:
        ts = str(e.get("timestamp", ""))[:19].replace("T", " ")
        df_rows.append(
            {
                "Time": ts,
                "Status": STATUS_ICON.get(e.get("status", ""), "")
                + " "
                + e.get("status", ""),
                "Action": e.get("action", ""),
                "Issue": e.get("issue", ""),
                "Sensor": e.get("sensor", ""),
                "Policy": e.get("policy", ""),
                "By": e.get("executed_by", ""),
                "ms": round(e.get("duration_ms", 0), 1),
            }
        )
    st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True)


# ── Incident Timeline panel ─────────────────────────────────────────────────────

st.divider()
st.subheader("📅 Incident Timeline")
st.caption("Full lifecycle: Detected → Diagnosed → Executed → Resolved")

inc_data = get_incidents()
incidents = inc_data.get("incidents", [])

if not incidents:
    st.caption("No incidents recorded yet. Run Auto-Remediate to create incidents.")
else:
    for inc in incidents[:5]:
        sev = inc.get("severity", "UNKNOWN")
        icon = SEVERITY_COLORS.get(sev, "⚪")
        resolved = inc.get("resolved", False)
        status_badge = "🟢 RESOLVED" if resolved else "🔴 OPEN"
        policy = inc.get("policy", "")
        policy_badge = "🤖 AUTO" if policy == "AUTO" else "🔒 MANUAL"

        with st.expander(
            f"{icon} **{inc.get('issue','?')}** — `{inc.get('action','?')}` · {status_badge} · {policy_badge}",
            expanded=False,
        ):
            # Timeline steps
            steps = []
            if inc.get("detected_at"):
                steps.append(("🔍 Detected", inc["detected_at"]))
            if inc.get("approved_at"):
                steps.append(("✅ Approved", inc["approved_at"]))
            if inc.get("executed_at"):
                steps.append(("⚡ Executed", inc["executed_at"]))
            if inc.get("resolved_at"):
                steps.append(("🟢 Resolved", inc["resolved_at"]))

            for step_label, step_ts in steps:
                ts_str = str(step_ts)[:19].replace("T", " ")
                st.markdown(f"**{step_label}** &nbsp; `{ts_str}`")

            if inc.get("execution"):
                ex = inc["execution"]
                st.markdown(
                    f"📓 **Result:** {ex.get('status','?')} — {ex.get('details','')[:120]}"
                )
                if ex.get("rollback"):
                    rb = ex["rollback"]
                    st.info(
                        f"↩️ Rollback: {rb.get('status','?')} — {rb.get('details','')[:100]}"
                    )
