# ============================================================
# main.py — CampusFlow Multi-Domain Autonomous Agent UI
# ============================================================
# Two-page Streamlit app:
#   Dashboard   → Clean chat interface (messages only)
#   Automation  → Logs, pipeline, policy, KPIs per session
#
# Persistence: SQLite via campus/db.py
# Execution:   campus/executor.py (classify → policy → notify)
# ============================================================

import os
import json
import uuid
import random
import datetime
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from campus import db, executor, role_system

load_dotenv()

# ── PAGE CONFIG ──────────────────────────────────────────────────
st.set_page_config(
    page_title="CampusFlow — Autonomous Campus Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── SESSION STATE ────────────────────────────────────────────────
if "active_session_id"  not in st.session_state: st.session_state["active_session_id"]  = None
if "active_page"        not in st.session_state: st.session_state["active_page"]        = "Dashboard"
if "rename_session_id"  not in st.session_state: st.session_state["rename_session_id"]  = None
if "user_role"          not in st.session_state: st.session_state["user_role"]          = "student"

# ── STEP ICONS AND LABELS ─────────────────────────────────────────
STEP_ICONS = {
    "pending": "○",
    "active": "⚙",
    "done": "✔",
    "failed": "✖",
    "skipped": "↩",
}

STEP_LABELS = ["THINK", "PLAN", "EXECUTE", "REVIEW", "UPDATE"]
STEP_KEYS = ["think", "plan", "execute", "review", "update"]

STEP_DESCRIPTIONS = {
    "think": "Parse query",
    "plan": "Create plan",
    "execute": "Run tools",
    "review": "Score output",
    "update": "Self-correct",
}


def render_steps(statuses, container):
    """Render the 5 step cards with current statuses."""
    with container:
        container.empty()
        cols = st.columns(5)
        for i, col in enumerate(cols):
            key = STEP_KEYS[i]
            status = statuses.get(key, "pending")
            icon = STEP_ICONS.get(status, "○")
            label = STEP_LABELS[i]
            desc = STEP_DESCRIPTIONS.get(key, "")
            # Colourful CSS Logic matching states
            if status == "active":
                bg = "linear-gradient(135deg, rgba(255,193,7,0.2) 0%, rgba(255,193,7,0.05) 100%)"
                border = "1px solid rgba(255,193,7, 0.8)"
                shadow = "0 0 15px rgba(255,193,7,0.4)"
                text_color = "#ffc107"
            elif status == "done":
                bg = "linear-gradient(135deg, rgba(0,230,118,0.2) 0%, rgba(0,230,118,0.05) 100%)"
                border = "1px solid rgba(0,230,118, 0.5)"
                shadow = "0 0 10px rgba(0,230,118,0.2)"
                text_color = "#00e676"
            elif status == "failed":
                bg = "linear-gradient(135deg, rgba(255,23,68,0.2) 0%, rgba(255,23,68,0.05) 100%)"
                border = "1px solid rgba(255,23,68, 0.8)"
                shadow = "0 0 15px rgba(255,23,68,0.4)"
                text_color = "#ff1744"
            else: # pending / default
                bg = "rgba(255,255,255,0.03)"
                border = "1px solid rgba(255,255,255,0.1)"
                shadow = "none"
                text_color = "#888"

            col.markdown(
                f"""<div style="background:{bg}; border:{border}; box-shadow:{shadow}; padding:14px 10px; border-radius:12px; text-align:center; transition: all 0.3s ease;">
                    <div style="font-size: 28px; color:{text_color}; text-shadow: {shadow};">{icon}</div>
                    <div style="font-weight: 800; margin-top: 6px; color:{text_color}; letter-spacing: 1px;">{label}</div>
                    <div style="font-size: 11px; margin-top: 4px; opacity: 0.9; color: #ddd;">{desc}</div>
                    <div style="font-size: 10px; margin-top: 10px; font-weight:bold; color:{text_color}; background:rgba(0,0,0,0.3); display:inline-block; padding:3px 10px; border-radius:12px;">{status.upper()}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def format_log(message):
    """Add timestamp and color-code log lines for readability."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    time_span = f'<span style="color:gray;">[{ts}]</span>'

    if message.startswith("═══"):
        return f'{time_span} <span style="color:cyan;">{message}</span>'
    elif "Running tool:" in message:
        return f'{time_span} <span style="color:orange;">{message}</span>'
    elif "PASSED" in message or ("passed" in message.lower() and "success" in message.lower()):
        return f'{time_span} <span style="color:green;">{message}</span>'
    elif "FAILED" in message or "failed" in message.lower():
        return f'{time_span} <span style="color:red;">{message}</span>'
    else:
        return f"{time_span} {message}"


# ── INFO DIALOG ───────────────────────────────────────────────────
@st.dialog("About CampusFlow", width="large")
def show_info_dialog():
    st.markdown("### CampusFlow — Multi-Domain Autonomous Campus Agent")
    st.write("Handles 4 campus workflows autonomously: Lab Booking, Leave Requests, Room Booking, and Complaints.")

    with st.expander("Supported Workflows", expanded=True):
        st.markdown("""
| Workflow | What it handles |
|----------|----------------|
| **Lab Booking** | Book CS, Electronics, Physics, CAD, Software labs |
| **Leave Request** | Medical, emergency, personal leave + HOD routing |
| **Room Booking** | Seminar halls, conference rooms, event spaces |
| **Complaint** | Maintenance, facility issues with SLA-based routing |
        """)

    with st.expander("Policy Engine", expanded=False):
        st.markdown("""
**Every request goes through the policy engine:**
- ✅ **APPROVED** — Auto-executed immediately
- ❌ **REJECTED** — Clear reason given, alternatives suggested
- ⚠️ **ESCALATED** — Forwarded to HOD/Admin with notification

**Examples:**
- Lab booked? → Suggest 3 free slots
- Leave during exam week? → Auto-rejected
- High-priority complaint? → Escalated within 4 hours
        """)

    with st.expander("CampusBot Architecture", expanded=False):
        st.markdown("""
**CampusBot Architecture**  
The 5-step loop (`agent/loop.py`):

```text
THINK → PLAN → EXECUTE → REVIEW → UPDATE
  ↑                                  |
  └──────── (if score < 7) ──────────┘
```

**What each file does:**
- `loop.py` — Runs the 5-step cycle (NEVER changes)
- `planner.py` — LLM → JSON action plan
- `executor.py` — Routes plan → tool functions
- `reviewer.py` — Scores 6 workflow metrics
- `tools/` — The 4 domain-specific tools

**The 4 CampusBot tools:**
- `request_classifier` — Intent + entity extraction
- `form_parser` — Text & PDF Form Parser
- `availability_checker` — Google Sheets slot lookup
- `email_router` — Notification & escalation

**Why this is autonomous:** The reviewer scores classification accuracy, escalation logic, and response quality. If score < 7, it self-corrects.
        """)

    with st.expander("What makes CampusBot AUTONOMOUS (not just a chatbot)?", expanded=False):
        st.markdown("""
A chatbot takes your question → calls an LLM once → gives whatever it generates → done. One shot. No quality check.

**CampusBot (an autonomous agent)** receives a student query and then:

| Step | What the Agent Does | Why It Matters |
|------|--------------------|----------------|
| **THINK** | Reads the student message + any feedback from previous attempts | Understands the full context before acting |
| **PLAN** | LLM creates a JSON action plan — decides which tools to run | Self-directed — the agent decides the workflow |
| **EXECUTE** | Runs 4 tools in sequence (classify → retrieve → escalate → respond) | Information chaining — each tool feeds the next |
| **REVIEW** | Scores the output on 6 workflow quality metrics | Self-evaluation — **THIS is what makes it autonomous** |
| **UPDATE** | If score < 7, self-corrects with feedback and retries | Directed self-correction, not blind retry |

**4-Tool Pipeline:**
- **Request Classifier** → Identifies intent (leave/lab/event), extracts dates & details
- **Form Parser** → Parses PDF and text rules into structured properties
- **Availability Checker** → Confirms the resource in Google Sheets
- **Email Router** → Drafts HOD escalation and sends Telegram reply

**The one rule:** THE LOOP NEVER CHANGES. THE TOOLS DO.
        """)

# ── SIDEBAR ──────────────────────────────────────────────────────
with st.sidebar:
    colA, colB = st.columns(2)
    with colA:
        if st.button("About CampusFlow", use_container_width=True):
            show_info_dialog()

    st.markdown(
        """
        <style>
        /* Center configuration button text and elements */
        div[data-testid="stPopover"] > button p {
            font-weight: 600;
            text-align: center;
            flex-grow: 1;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with colB:
        with st.popover("Config", icon=":material/settings:", use_container_width=True):
            api_key = st.text_input(
                "Groq API Key", type="password",
                value=os.getenv("GROQ_API_KEY", ""),
                help="Get your free key at console.groq.com",
            )

            tavily_key = st.text_input(
                "Tavily API Key", type="password",
                value=os.getenv("TAVILY_API_KEY", ""),
                help="Required for web search queries. Get at app.tavily.com",
            )

            model = st.selectbox(
                "Model Selection",
                ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"],
                help="llama-3.3-70b recommended",
            )

            role_choices = role_system.get_role_choices()
            role_keys = [r[0] for r in role_choices]
            role_labels = [r[1] for r in role_choices]
            
            current_index = role_keys.index(st.session_state["user_role"]) if st.session_state["user_role"] in role_keys else 0
            
            role = st.selectbox(
                "Your Role",
                options=role_keys,
                index=current_index,
                format_func=lambda x: role_system.ROLES[x]['display_name'],
                help="Role controls AI behavior, tone, and data visibility",
            )
            
            # Show role description
            role_desc = role_system.ROLES[role]["description"]
            st.caption(f"_{role_desc}_")
            
            if role != st.session_state["user_role"]:
                st.session_state["user_role"] = role
                st.rerun()

    st.divider()

    # ── CHAT HISTORY ─────────────────────────────────────────────
    col_h, col_new = st.columns([3, 1])
    with col_h:
        st.subheader("Chat History", anchor=False)
    with col_new:
        if st.button("New", use_container_width=True, help="Start a new query"):
            st.session_state["active_session_id"] = None
            st.session_state.pop("idea_input", None)
            st.rerun()

    sessions = db.list_sessions()

    if not sessions:
        st.caption("No chats yet. Submit a query to start.")
    else:
        for session in sessions:
            sid        = session["id"]
            is_active  = (st.session_state["active_session_id"] == sid)
            is_renaming = (st.session_state["rename_session_id"] == sid)
            wt         = session.get("workflow_type", "")
            wt_badge   = {"lab_booking": ":material/science:", "leave_request": ":material/assignment:",
                          "room_booking": ":material/domain:", "complaint": ":material/warning:", "web_search": ":material/search:"}.get(wt, ":material/chat:")

            with st.container(border=True):
                if is_renaming:
                    new_name = st.text_input(
                        "Rename", value=session.get("title", ""),
                        key=f"rename_input_{sid}", label_visibility="collapsed",
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Save", key=f"save_{sid}", use_container_width=True, type="primary"):
                            db.rename_session(sid, new_name)
                            st.session_state["rename_session_id"] = None
                            st.rerun()
                    with c2:
                        if st.button("Cancel", key=f"cancel_{sid}", use_container_width=True):
                            st.session_state["rename_session_id"] = None
                            st.rerun()
                else:
                    ts = session.get("created_at", "")
                    try:
                        dt = datetime.datetime.fromisoformat(ts)
                        date_str = dt.strftime("%d %b, %I:%M %p")
                    except Exception:
                        date_str = ""
                    label      = f"{wt_badge} {session.get('title', 'Untitled')}  \n*{date_str}*"
                    btn_label  = f"▶ {label}" if is_active else label

                    col_c, col_e, col_d = st.columns([5, 1, 1])
                    with col_c:
                        if st.button(btn_label, key=f"chat_{sid}", use_container_width=True, type="tertiary"):
                            st.session_state["active_session_id"] = sid
                            st.rerun()
                    with col_e:
                        if st.button("", key=f"edit_{sid}", use_container_width=True,
                                     type="tertiary", icon=":material/edit:", help="Rename"):
                            st.session_state["rename_session_id"] = sid
                            st.rerun()
                    with col_d:
                        if st.button("✕", key=f"del_{sid}", use_container_width=True,
                                     type="tertiary", help="Delete"):
                            db.delete_session(sid)
                            if st.session_state["active_session_id"] == sid:
                                st.session_state["active_session_id"] = None
                            st.rerun()

# ── TOP NAV ───────────────────────────────────────────────────────
col_sp, col_dash, col_auto = st.columns([7, 1.5, 1.5])
with col_dash:
    if st.button("Dashboard", use_container_width=True,
                 type="secondary" if st.session_state["active_page"] == "Dashboard" else "tertiary"):
        st.session_state["active_page"] = "Dashboard"
        st.rerun()
with col_auto:
    if st.button("Automation", use_container_width=True,
                 type="secondary" if st.session_state["active_page"] == "Automation" else "tertiary"):
        st.session_state["active_page"] = "Automation"
        st.rerun()

# ── BRANDING ─────────────────────────────────────────────────────
st.title("CampusFlow", anchor=False)
st.subheader("AUTONOMOUS CAMPUS AGENT", anchor=False)

# ════════════════════════════════════════════════════════════════
# AUTOMATION PAGE
# ════════════════════════════════════════════════════════════════
if st.session_state["active_page"] == "Automation":
    active_id = st.session_state.get("active_session_id")

    # ── KPI SUMMARY (ROLE-BASED ACCESS) ────────────────────────────
    user_role = st.session_state["user_role"]
    
    # Check if role has KPI access
    if not role_system.can_access(user_role, "kpi", "read"):
        st.header("System KPIs", anchor=False)
        st.warning(role_system.get_access_denied_message(user_role, 'kpi', 'read'))
    else:
        st.header("System KPIs", anchor=False)
        kpis = db.get_kpi_summary()
        if kpis:
            visible_kpis = role_system.get_visible_fields(user_role, "kpi")
            
            # Admin sees full KPI set, TA sees subset
            if user_role == "admin":
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Requests",       kpis.get("total_requests", 0))
                k2.metric("Resolution Rate",      f"{kpis.get('resolution_rate_pct', 0)}%")
                k3.metric("Avg Resolution Time",  f"{kpis.get('avg_resolution_mins', 0)} min")
                k4.metric("Resolved",             kpis.get("resolved", 0))

                by_wf = kpis.get("by_workflow", {})
                if by_wf:
                    st.markdown("**By Workflow:**")
                    wf_cols = st.columns(len(by_wf))
                    for i, (wt, stats) in enumerate(by_wf.items()):
                        wf_cols[i].metric(
                            wt.replace("_"," ").title(),
                            f"{stats['resolved']}/{stats['total']} resolved"
                        )
            elif user_role == "teaching_assistant":
                k1, k2 = st.columns(2)
                k1.metric("Total Requests",       kpis.get("total_requests", 0))
                k2.metric("Resolution Rate",      f"{kpis.get('resolution_rate_pct', 0)}%")
        else:
            st.info("No requests yet. Submit a query via the Dashboard page.")

    st.divider()

    if not active_id:
        st.info("Select a session from the sidebar to view its detailed logs.")
        st.stop()

    session = db.get_session(active_id)
    if not session:
        st.warning("Session not found.")
        st.stop()

    # Role-based session info display
    session_role = session.get('role', 'student')
    session_info = f"Session: **{session.get('title','')}**"
    
    # Only show role in session info for TA and Admin
    if role_system.can_access(user_role, "session", "admin"):
        session_info += f" · Actor Role: {session_role}"
    else:
        session_info += f" · Role: {session_role}"
    
    session_info += f" · {session.get('created_at','')[:19].replace('T',' at ')}"
    st.caption(session_info)
    st.divider()
    # ── AUTONOMOUS LOOP ──────────────────────────────────────────
    st.subheader("Autonomous Loop", anchor=False)

    # ── STEP DISPLAY CONTAINERS ───────────────────────────────────────
    step_container = st.container()
    loop_label = st.empty()
    log_header = st.empty()
    log_container = st.empty()

    # Render done steps for history
    statuses = {"think": "done", "plan": "done", "execute": "done", "review": "done", "update": "done"}
    render_steps(statuses, step_container)
    st.divider()

    # ── WORKFLOW PIPELINE ────────────────────────────────────────
    st.subheader("Workflow Pipeline", anchor=False)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.success("**1. Request Classifier**  \nIntent extracted")
    with c2: st.success("**2. Form Parser**  \nSchema structured")
    with c3: st.success("**3. Policy Engine**  \nRules evaluated")
    with c4: st.success("**4. Notification Router**  \nPayload dispatched")
    st.divider()

    # ── SESSION REQUESTS & TOOL OUTPUTS ──────────────────────────
    requests = db.get_session_requests(active_id)
    
    # ── CAMPUSBOT HANDLED YOUR QUERY ───────────────────────────────
    # Get the results from the executor
    results = {}
    if requests:
        # Get the most recent request data
        req = requests[-1]
        try:
            results["schema"] = json.loads(req.get("schema_json", "{}"))
        except:
            results["schema"] = {}
        results["policy"] = {
            "result": req.get("policy_result", "UNKNOWN"),
            "reason": req.get("policy_reason", ""),
            "alternatives": json.loads(req.get("alternatives", "[]")) if req.get("alternatives") else []
        }
        results["workflow_type"] = req.get("workflow_type", "unknown")
        results["status"] = req.get("status", "unknown")
    
    st.divider()
    st.markdown("## CampusBot Handled Your Query")
    
    # Parse all outputs
    classifier_data = results.get("schema", {})
    form_data = results.get("schema", {})
    avail_data = {}  # Availability is part of policy evaluation
    email_data = results.get("policy", {})
    
    # Get the assistant message for the reply
    messages = db.get_messages(active_id)
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    telegram_reply = assistant_msgs[-1]["content"] if assistant_msgs else "No reply generated."

    tab_reply, tab_pipeline, tab_tools, tab_raw = st.tabs(
        ["Student Reply", "Workflow Pipeline", "Tool Outputs", "Raw JSON"]
    )

    # ── TAB 1: STUDENT TELEGRAM REPLY ────────────────────────────
    with tab_reply:
        if telegram_reply:
            st.markdown("**Telegram Message Sent to Student:**")
            st.markdown(
                f'''<div style="background: #3a3a4a;
                            color: #eee;
                            padding: 20px;
                            border-radius: 12px;
                            border-left: 4px solid #8b7ecf;
                            font-size: 15px;
                            line-height: 1.6;">
                        {telegram_reply}
                     </div>''',
                unsafe_allow_html=True,
            )
        else:
            st.warning("No reply was generated. Check the activity log.")

        st.markdown("---")

        # Workflow summary
        summary = results.get("policy", {}).get("reason", "Processed successfully via CampusFlow pipeline.")
        if summary:
            st.markdown(f"**Workflow Summary:** {summary}")

    # ── TAB 2: PIPELINE VISUALIZATION ────────────────────────────
    with tab_pipeline:
        st.markdown("**4-Tool CampusBot Pipeline:**")
        p_cols = st.columns(4)
        
        workflow_type = results.get("workflow_type", "unknown")
        policy_result = results.get("policy", {}).get("result", "UNKNOWN")
        escalated = policy_result == "ESCALATED"

        pipeline_tools = [
            ("1.", "Request\nClassifier", f"Intent: {workflow_type.replace('_', ' ').title()}", "#4a4a5a"),
            ("2.", "Form\nParser", f"Type: {workflow_type.replace('_', ' ').title()}", "#4a5568"),
            ("3.", "Policy\nEngine", "Available" if policy_result == "APPROVED" else "Review Needed", "#4a5a4a"),
            ("4.", "Notification\nRouter", "Escalated" if escalated else "Replied", "#5a4a4a"),
        ]
        for i, col in enumerate(p_cols):
            icon, name, output, bg_color = pipeline_tools[i]
            col.markdown(
                f"""<div style="background:{bg_color};padding:15px;border-radius:12px;text-align:center;border:1px solid #666;">
                    <div style="font-size:22px;font-weight:bold;color:#fff;">{icon}</div>
                    <div style="font-weight:bold;margin-top:6px;color:#eee;font-size:14px;">{name}</div>
                    <div style="font-size:11px;color:#ccc;margin-top:8px;background:rgba(255,255,255,0.1);padding:4px 8px;border-radius:6px;">{output}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("### Workflow Quality Score")
        # Since we're using executor.run() directly, we show single-pass results
        st.success("Query handled successfully in a single pass!")

        st.markdown(f"**Workflow Type:** {workflow_type.replace('_', ' ').title()}")

        # Show classification details
        if classifier_data:
            st.markdown("### Classification Details")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Intent", workflow_type.replace('_', ' ').title().upper())
            col_b.metric("Status", policy_result.upper())
            col_c.metric("Policy", policy_result)

            # Show extracted details
            if classifier_data:
                st.info(f"**Extracted Details:** {json.dumps(classifier_data, indent=2)[:200]}")

    # ── TAB 3: TOOL OUTPUTS ───────────────────────────────────────
    with tab_tools:
        st.markdown("**Understanding how tools chain together in CampusBot:**")
        st.markdown("---")

        st.markdown("### Tool 1: Request Classifier")
        st.json(classifier_data)

        st.markdown("---")
        st.markdown("### Tool 2: Form Parser")
        st.json(form_data)

        st.markdown("---")
        st.markdown("### Tool 3: Policy Engine")
        st.json(results.get("policy", {}))

        st.markdown("---")
        st.markdown("### Tool 4: Notification Router")
        st.json({"status": "sent" if escalated else "replied", "message": "Notification dispatched"})

    # ── TAB 4: RAW JSON ────────────────────────────────────────────
    with tab_raw:
        st.markdown("**Raw outputs from each tool (for debugging / learning):**")
        
        st.markdown("**Request Data**")
        if requests:
            st.json(dict(requests[-1]))
        else:
            st.code("*No request data*")
        
        st.markdown("**Schema**")
        st.json(classifier_data)
        
        st.markdown("**Policy Result**")
        st.json(results.get("policy", {}))
    st.divider()

    # ── STUDENT REPLY ────────────────────────────────────────────
    st.header("Student Reply", anchor=False)
    messages = db.get_messages(active_id)
    user_msgs = [m for m in messages if m["role"] == "user"]
    if user_msgs:
        st.info(user_msgs[-1]["content"])
    else:
        st.info("No query entered yet.")
    st.divider()

    # ── ACTIVITY LOG ─────────────────────────────────────────────
    logs = db.get_logs(active_id)
    if logs:
        st.header("Activity Log", anchor=False)
        formatted_logs = [format_log(l) for l in logs]
        st.markdown(
            f'<div style="background-color:#0e1117; padding:15px; border-radius:8px; font-family:monospace; font-size:14px; line-height:1.5;">{"<br>".join(formatted_logs)}</div>',
            unsafe_allow_html=True
        )

    st.stop()


# ════════════════════════════════════════════════════════════════
# DASHBOARD PAGE — Chat Interface
# ════════════════════════════════════════════════════════════════

# ── EXAMPLE QUERIES ───────────────────────────────────────────────
LEAVE_EXAMPLES = [
    "Hi, I need to apply for 3 days medical leave from March 22-24. I have a doctor's certificate. Please forward this to the HOD for approval.",
    "I'm requesting a 2-day emergency leave on April 5-6 due to a family function. Kindly inform the HOD and update my attendance record.",
    "I need to take leave from May 10 to May 12 for my sister's wedding. Please get HOD approval.",
    "Requesting sick leave for tomorrow, March 30th. I have a high fever and cannot attend college.",
    "I need a half-day leave this Friday afternoon (after 1 PM) to attend a government document verification appointment.",
    "I want to request leave for next whole week (April 12 to 16) due to severe chicken pox check. Send to HOD.",
]
LAB_EXAMPLES = [
    "I need to book the computer lab (Lab 204) on Friday 3–5 PM for a project demo with my team. Is it available?",
    "Can I reserve the Electronics Lab (Room 301) on Tuesday from 10 AM to 12 PM for a circuit testing session?",
    "Our group needs the CAD Lab on Wednesday 2–4 PM to complete design drawings before submission.",
    "I'd like to book Lab 102 (Physics Lab) on Thursday morning 9–11 AM for a practical revision session.",
    "We need the Software Lab (Lab 205) on Saturday 10 AM to 1 PM for a hackathon preparation session.",
    "Book the main computer lab for me and my partner tomorrow at 11am for AI training models.",
]
ROOM_EXAMPLES = [
    "We'd like to book Seminar Hall A on April 10 from 10 AM to 12 PM for a guest lecture. Around 60 students expected.",
    "I need Conference Room 1 on March 31 at 2 PM for a 1-hour project presentation. About 15 people.",
    "Requesting Seminar Hall B on April 15 from 9 AM to 5 PM for a departmental workshop.",
    "Can you book the large seminar hall A for our cultural club meeting this Friday at 4 PM? 80 students will come.",
]
COMPLAINT_EXAMPLES = [
    "The AC in Lab 204 is not working. It's very hot and students can't focus. This needs urgent attention.",
    "The projector in Seminar Hall A is broken and we have a presentation tomorrow. Please fix it.",
    "There's a water leak on the 2nd floor corridor near Lab 301. Needs urgent maintenance.",
    "The WiFi in the library has been down for 2 days. Please fix it as soon as possible.",
    "The power outlets in row 3 of the hardware lab are sparking, this is extremely dangerous and needs high priority fixing.",
]
SEARCH_EXAMPLES = [
    "What is the difference between supervised and unsupervised learning in machine learning?",
    "Can you explain how quantum computing fundamentally differs from classical computing?",
    "What are the latest AI trends in completely autonomous agents as of 2025?",
    "How does Transformer architecture work in NLP models?",
]

def load_random_example():
    all_examples = LEAVE_EXAMPLES + LAB_EXAMPLES + ROOM_EXAMPLES + COMPLAINT_EXAMPLES + SEARCH_EXAMPLES
    st.session_state["idea_input"] = random.choice(all_examples)

# ── LOAD CHAT MESSAGES ────────────────────────────────────────────
active_id = st.session_state.get("active_session_id")
display_messages = db.get_messages(active_id) if active_id else []

# ── RENDER CHAT ───────────────────────────────────────────────────
if display_messages:
    for msg in display_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    st.caption("View full system details in the **Automation** tab above.")

# ── INPUT ─────────────────────────────────────────────────────────
if not display_messages:
    # Fresh — show full form + example buttons
    with st.container():
        idea = st.text_area(
            "Enter your query (leave/lab/room/complaint/doubt)",
            key="idea_input",
            placeholder="Examples: Book a lab, apply for leave, report a complaint, or ask an academic doubt...",
            height=120,
        )
        col_run, col_sample = st.columns([2, 1])
        with col_run:
            run_button = st.button("Submit Request", use_container_width=True, type="primary")
        with col_sample:
            st.button("Give a sample prompt", use_container_width=True, on_click=load_random_example)
else:
    idea = st.chat_input("Submit another request...")
    run_button = bool(idea)

# ── EXECUTE ───────────────────────────────────────────────────────
if run_button:
    query_text = idea if isinstance(idea, str) else st.session_state.get("idea_input", "")

    if not api_key or "your_groq" in api_key:
        st.error("**Groq API key missing.** Please fill it in the **Config** part in the sidebar.")
        st.stop()
    if not query_text.strip():
        st.error("**No query entered.**")
        st.stop()

    user_role = st.session_state["user_role"]

    # Show user message immediately
    with st.chat_message("user"):
        st.write(query_text)

    with st.chat_message("assistant"):
        resp_placeholder = st.empty()
        resp_placeholder.write("Processing your request...")

        # Live step tracker inside the assistant bubble
        step_container = st.container()
        
        # Real-time state tracking
        loop_statuses = {"think": "pending", "plan": "pending", "execute": "pending", "review": "pending", "update": "pending"}
        render_steps(loop_statuses, step_container)

        def on_log(msg: str):
            u_msg = msg.upper()
            if "THINK" in u_msg:
                loop_statuses["think"] = "active"
            elif "PLAN" in u_msg:
                loop_statuses["think"] = "done"
                loop_statuses["plan"] = "active"
            elif "EXECUTE" in u_msg:
                loop_statuses["plan"] = "done"
                loop_statuses["execute"] = "active"
            elif "REVIEW" in u_msg:
                loop_statuses["execute"] = "done"
                loop_statuses["review"] = "active"
            elif "UPDATE" in u_msg:
                loop_statuses["review"] = "done"
                loop_statuses["update"] = "active"
            elif "DONE" in u_msg:
                loop_statuses["update"] = "done"
            
            # Re-render the 5 cards in real time
            render_steps(loop_statuses, step_container)

    # Ensure session exists
    session_id = active_id
    if not session_id:
        session_id = str(uuid.uuid4())
        title = query_text.strip()[:20] + ("..." if len(query_text.strip()) > 20 else "")
        db.create_session(session_id, title, user_role)
        st.session_state["active_session_id"] = session_id

    client = Groq(api_key=api_key)

    with st.spinner("CampusFlow is handling your request autonomously..."):
        try:
            result = executor.run(
                session_id=session_id,
                query_text=query_text,
                role=user_role,
                client=client,
                model=model,
                tavily_api_key=tavily_key,
                on_log=on_log,
            )
        except Exception as e:
            st.error(f"**Agent error:** `{str(e)}`")
            st.stop()

    # Update session workflow type
    wt = result.get("workflow_type", "")
    conn = db.get_conn()
    with conn:
        conn.execute("UPDATE sessions SET workflow_type=? WHERE id=?", (wt, session_id))
    conn.close()

    # Save messages
    db.add_message(session_id, "user", query_text)
    db.add_message(session_id, "assistant", result["chat_reply"])

    # Show reply
    resp_placeholder.write(result["chat_reply"])

    st.rerun()
