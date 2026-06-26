import os
import requests
import streamlit as st
import pandas as pd
import base64
import json

AGENT_BASE = os.getenv("AGENT_SERVICE_URL", "http://localhost:8000")
ANALYTICS_BASE = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8001")

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH": "&nbsp;🟠",
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

# ── Streamlit Config ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI OpsBMC — Autonomous Operations",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AI OpsBMC — Autonomous Enterprise AIOps Platform")
st.caption("Phase D · Production Microservice Architecture · Approve → Execute → Audit")

# ── API Authenticated Requests Wrapper ──────────────────────────────────────


def api_request(method, url, json_data=None, data=None, params=None):
    headers = {}
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state['token']}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == "POST":
            if json_data is not None:
                r = requests.post(url, headers=headers, json=json_data, timeout=30)
            else:
                r = requests.post(url, headers=headers, data=data, timeout=30)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=10)

        if r.status_code == 401:
            st.session_state["token"] = None
            st.session_state["user_role"] = None
            st.session_state["username"] = None
            st.rerun()

        return r
    except Exception as e:
        st.error(f"Error reaching endpoint {url}: {e}")
        return None


# ── Sidebar — Authentication + Health Status ──────────────────────────────────

with st.sidebar:
    st.header("🔑 Authentication")
    if not st.session_state.get("token"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            try:
                # Retrieve token
                r = requests.post(
                    f"{AGENT_BASE}/token",
                    data={"username": username, "password": password},
                    timeout=5,
                )
                if r.status_code == 200:
                    res_data = r.json()
                    st.session_state["token"] = res_data["access_token"]

                    # Decode role
                    payload_part = res_data["access_token"].split(".")[1]
                    padding = "=" * (4 - len(payload_part) % 4)
                    payload = json.loads(
                        base64.urlsafe_b64decode(payload_part + padding).decode()
                    )
                    st.session_state["user_role"] = payload.get("role", "viewer")
                    st.session_state["username"] = username
                    st.success(f"Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            except Exception as e:
                st.error(f"Auth server unreachable: {e}")
    else:
        st.success(f"Logged in: **{st.session_state.get('username')}**")
        st.caption(f"Role: **{st.session_state.get('user_role').upper()}**")
        if st.button("Logout", use_container_width=True):
            st.session_state["token"] = None
            st.session_state["user_role"] = None
            st.session_state["username"] = None
            st.rerun()

    st.divider()
    st.header("System Status")

    agent_healthy = False
    analytics_healthy = False

    try:
        r_agent = requests.get(f"{AGENT_BASE}/health", timeout=3)
        agent_healthy = r_agent.status_code == 200
    except Exception:
        pass

    try:
        r_anal = requests.get(f"{ANALYTICS_BASE}/health", timeout=3)
        analytics_healthy = r_anal.status_code == 200
    except Exception:
        pass

    if agent_healthy:
        st.success("✅ Agent Orchestrator: **ONLINE**")
    else:
        st.error("❌ Agent Orchestrator: **OFFLINE**")

    if analytics_healthy:
        st.success("✅ Analytics Service: **ONLINE**")
    else:
        st.error("❌ Analytics Service: **OFFLINE**")

    st.divider()
    st.header("Pipeline Stages")
    st.markdown("""
1. 🔍 **Detect** — Telemetry anomaly
2. 🧠 **Diagnose** — RAG + LLM root cause
3. 📈 **Predict** — Failure probability
4. 🛠️ **Recommend** — Action suggestion
5. ✅ **Approve** — Policy gate
6. ⚡ **Execute** — Autonomous action
7. 📓 **Audit** — Full trail
""")
    st.caption("Phase D · ai-openBMC · Amritapuri")

# ── Main Panel Control ────────────────────────────────────────────────────────

if not st.session_state.get("token"):
    st.warning("🔒 Access Denied. Please log in from the sidebar using credentials.")
    st.info("""
    **Demo Users:**
    * **Admin:** `admin` / `admin123`
    * **Operator:** `operator` / `op123`
    * **Viewer:** `viewer` / `view123`
    """)
else:
    # ── Executive KPI Banner ──
    st.markdown("### 📊 Fleet Executive Dashboard")

    fleet_health_score = 100
    fleet_risk = "LOW"

    r_health = api_request("GET", f"{ANALYTICS_BASE}/health-score")
    if r_health and r_health.status_code == 200:
        h_data = r_health.json()
        fleet_health_score = h_data.get("overall_health_score") or 100
        fleet_risk = h_data.get("overall_risk") or "LOW"

    r_incidents = api_request("GET", f"{AGENT_BASE}/incidents")
    active_incidents = 0
    incidents_list = []
    if r_incidents and r_incidents.status_code == 200:
        incidents_list = r_incidents.json().get("incidents", [])
        active_incidents = sum(1 for i in incidents_list if not i.get("resolved"))

    col_h1, col_h2, col_h3 = st.columns(3)

    health_icon = (
        "🟢" if fleet_health_score >= 80 else "🟡" if fleet_health_score >= 60 else "🔴"
    )
    col_h1.metric("Overall Fleet Health", f"{health_icon} {fleet_health_score}/100")

    risk_icon = (
        "🟢" if fleet_risk == "LOW" else "🟡" if fleet_risk == "MEDIUM" else "🔴"
    )
    col_h2.metric("Fleet System Risk", f"{risk_icon} {fleet_risk}")

    incident_icon = "✓" if active_incidents == 0 else "⚠️"
    col_h3.metric("Active Incidents", f"{incident_icon} {active_incidents} Open")

    st.divider()

    # ── Left / Right Split for Action vs Results ──
    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.subheader("📋 Select Fault Scenario")
        selected_key = st.selectbox(
            "Scenario Selection",
            options=list(SCENARIO_LABELS.keys()),
            format_func=lambda k: SCENARIO_LABELS[k],
            label_visibility="collapsed",
        )

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
            "fan_fault": {
                "sensor": "FAN_3",
                "event": "Fan Fault",
                "severity": "WARNING",
            },
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
        run_btn = b1.button(
            "🔍 Run Diagnosis", type="primary", use_container_width=True
        )
        remediate_btn = b2.button(
            "🔧 Auto-Remediate", type="secondary", use_container_width=True
        )

    with right_col:
        st.subheader("🧠 Diagnostic Analysis & Action Broker")

        if run_btn:
            with st.spinner("Retrieving RAG context + LLM reasoning..."):
                r = api_request(
                    "POST",
                    f"{AGENT_BASE}/diagnose/scenario",
                    json_data={"name": selected_key},
                )
                if r and r.status_code == 200:
                    result = r.json()
                    sev = result.get("severity", "UNKNOWN")
                    icon = SEVERITY_COLORS.get(sev, "⚪")
                    imm = result.get("requires_immediate_action", False)

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Severity", f"{icon} {sev}")
                    m2.metric("Confidence", result.get("confidence", "—"))
                    m3.metric("Immediate?", "YES ⚠️" if imm else "No")

                    st.divider()
                    st.markdown("#### 🔍 Root Cause Report")
                    st.info(result.get("root_cause", "—"))

                    st.markdown("#### 🛠️ Recommended Action")
                    st.success(result.get("recommendation", "—"))

                    with st.expander("📚 Knowledge Base Context Used"):
                        st.caption(result.get("rag_context", "—"))
                else:
                    st.error("Failed to run diagnosis. Check role permissions.")

        elif remediate_btn:
            with st.spinner("Analysing and evaluating against Policy Engine..."):
                # First run diagnosis to get the recommended action
                r_diag = api_request(
                    "POST",
                    f"{AGENT_BASE}/diagnose/scenario",
                    json_data={"name": selected_key},
                )
                if r_diag and r_diag.status_code == 200:
                    diag = r_diag.json()
                    rec = diag.get("recommendation", "")
                    sensor = diag.get("event", {}).get("sensor", ev["sensor"])
                    sev = diag.get("severity", "UNKNOWN")

                    st.markdown(f"**🧠 Diagnosis:** {diag.get('root_cause', '—')}")
                    st.markdown(f"**🛠️ Recommendation:** `{rec}`")

                    with st.spinner("Routing action through Policy Engine..."):
                        r_rem = api_request(
                            "POST",
                            f"{AGENT_BASE}/remediate",
                            json_data={
                                "issue": selected_key.upper(),
                                "action": rec,
                                "sensor": sensor,
                                "severity": sev,
                                "executed_by": st.session_state.get("username"),
                            },
                        )
                        if r_rem and r_rem.status_code == 200:
                            rem_res = r_rem.json()
                            if rem_res.get("mode") == "AUTO":
                                status_msg = rem_res.get("status", "")
                                if rem_res.get("success"):
                                    st.success(
                                        f"✅ **AUTO-EXECUTED** — `{rec}` | Status: **{status_msg}**"
                                    )
                                    st.caption(rem_res.get("details", ""))
                                else:
                                    st.warning(
                                        f"⚠️ **AUTO-EXECUTION FAILED** | Status: **{status_msg}**"
                                    )
                                    st.caption(rem_res.get("details", ""))
                                    if rem_res.get("rollback"):
                                        st.info(
                                            f"↩️ Rollback attempted: {rem_res['rollback'].get('status')}"
                                        )
                            else:
                                st.warning(
                                    f"🔒 **MANUAL POLICY GATE TRIGGERED** — Approval ID: `{rem_res.get('approval_id')}`\n\n"
                                    f"Recommended action `{rec}` requires review. Go to the approvals hub below."
                                )
                        else:
                            st.error(
                                "Remediation execution denied or failed. Check permissions."
                            )
                else:
                    st.error("Diagnosis failed prior to remediation.")
        else:
            st.markdown(
                """
            <div style='text-align:center; padding: 60px 20px; color: #666;'>
                <h3>👈 Select a fault scenario and run an operations action</h3>
                <p>Ensure your account role has appropriate permissions (Operator or Admin for actions).</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

    # ── Hub section ──
    st.divider()
    st.markdown("## 🏭 Autonomous Operations Hub")

    panel1, panel2, panel3 = st.columns(3)

    # Panel 1: Active Incidents
    with panel1:
        st.markdown("### 📅 Active Open Incidents")
        open_incs = [i for i in incidents_list if not i.get("resolved")]
        if not open_incs:
            st.caption("✓ No active incidents")
        else:
            for inc in open_incs[:4]:
                sev = inc.get("severity", "UNKNOWN")
                icon = SEVERITY_COLORS.get(sev, "⚪")
                st.markdown(
                    f"🔴 {icon} **{inc.get('issue','?')}**\n\n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;`{inc.get('sensor','?')}` — `{inc.get('action','?')}`"
                )
                st.caption(
                    f"Detected: {str(inc.get('detected_at',''))[:19].replace('T',' ')}"
                )
                st.markdown("---")

    # Panel 2: Executed Actions
    with panel2:
        st.markdown("### ⚡ Executed Remediation Actions")
        r_audit = api_request("GET", f"{AGENT_BASE}/audit?limit=20")
        audit_entries = []
        if r_audit and r_audit.status_code == 200:
            audit_entries = r_audit.json().get("entries", [])

        success_actions = [e for e in audit_entries if e.get("status") == "SUCCESS"]
        if not success_actions:
            st.caption("No executed actions yet")
        else:
            for entry in success_actions[:4]:
                ts = str(entry.get("timestamp", ""))[:19].replace("T", " ")
                st.markdown(
                    f"✅ **{entry.get('action','?')}**\n\n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;📌 `{entry.get('sensor','?')}` | {entry.get('issue','?')}"
                )
                st.caption(
                    f"{ts} · {entry.get('policy','?')} · {entry.get('executed_by','?')}"
                )
                st.markdown("---")

    # Panel 3: Pending Approvals
    with panel3:
        st.markdown("### 🔒 Pending Approvals")
        r_approvals = api_request("GET", f"{AGENT_BASE}/approvals?pending_only=true")
        pending_list = []
        if r_approvals and r_approvals.status_code == 200:
            pending_list = r_approvals.json().get("requests", [])

        if not pending_list:
            st.success("✓ No actions awaiting approval")
        else:
            st.warning(f"⏳ {len(pending_list)} action(s) waiting for approval")
            for req in pending_list[:3]:
                req_id = req.get("id", "")
                st.markdown(
                    f"🔒 **{req.get('action','?')}**\n\n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;📌 `{req.get('sensor','?')}` | {req.get('issue','?')} | {req.get('severity','?')}"
                )
                ts = str(req.get("requested_at", ""))[:19].replace("T", " ")
                st.caption(f"Requested: {ts}")

                col_a, col_r = st.columns(2)
                if col_a.button(
                    "✅ Approve", key=f"approve_{req_id}", use_container_width=True
                ):
                    with st.spinner("Approving and executing..."):
                        res = api_request(
                            "POST",
                            f"{AGENT_BASE}/approvals/{req_id}/approve",
                            json_data={"resolved_by": st.session_state.get("username")},
                        )
                        if res and res.status_code == 200:
                            st.success("Approved!")
                            st.rerun()
                        else:
                            st.error("Failed to approve. Check role permissions.")
                if col_r.button(
                    "❌ Reject", key=f"reject_{req_id}", use_container_width=True
                ):
                    with st.spinner("Rejecting..."):
                        res = api_request(
                            "POST",
                            f"{AGENT_BASE}/approvals/{req_id}/reject",
                            json_data={
                                "resolved_by": st.session_state.get("username"),
                                "notes": "Rejected by dashboard user",
                            },
                        )
                        if res and res.status_code == 200:
                            st.info("Rejected.")
                            st.rerun()
                        else:
                            st.error("Failed to reject.")
                st.markdown("---")

    # ── Audit Log panel ──
    st.divider()
    st.subheader("📓 System Audit Log")

    if not audit_entries:
        st.caption("Audit log is empty.")
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
        df_rows = []
        for e in audit_entries:
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
                    "Duration(ms)": round(e.get("duration_ms", 0) or 0, 1),
                }
            )
        st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True)

    # ── Incident Timeline panel ──
    st.divider()
    st.subheader("📅 Incident Timeline")

    if not incidents_list:
        st.caption("No incidents recorded yet.")
    else:
        for inc in incidents_list[:5]:
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
