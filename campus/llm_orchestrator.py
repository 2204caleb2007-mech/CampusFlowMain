import json
import re
from groq import Groq
from campus import executor
from campus.policy_engine import get_attendance
from campus import data_editor as _data_editor

# ─────────────────────────────────────────────────────────────────
# Patterns for detecting raw/leaked tool call text from the model
# ─────────────────────────────────────────────────────────────────
_RAW_TOOL_CALL_RE = re.compile(
    r"<function[/\s]+run_campusflow_agent[^>]*>\s*(\{.*?\})\s*</function>",
    re.DOTALL | re.IGNORECASE,
)
_BARE_JSON_RE = re.compile(r'\{"clarified_query"\s*:\s*"([^"]+)"\}')

# Pattern to detect attendance lookup queries so we can answer directly from CSV
_ATTENDANCE_RE = re.compile(
    r"\b(STU\d{3})\b",  # matches STU001 … STU999
    re.IGNORECASE,
)
_ATTENDANCE_KEYWORDS = ("attendance", "present", "classes attended", "absence", "how much", "percentage")

# Keywords that indicate a WRITE intent (not just a read)
_WRITE_KEYWORDS = (
    "add attendance", "mark attendance", "mark present", "mark absent",
    "update attendance", "set attendance", "record attendance",
    "schedule ", "add ", "remove ", "delete ", "book timetable",
    "add to timetable", "remove from timetable", "cancel timetable",
)


def _is_data_write_intent(text: str) -> bool:
    """Quick pre-check: does the query LOOK like a data modification intent?"""
    lower = text.lower()
    return any(kw in lower for kw in _WRITE_KEYWORDS)


def _is_pdf_export_query(text: str) -> bool:
    """Return True if the text asks to generate or download a PDF of the chat."""
    lower = text.lower()
    return "pdf" in lower and any(w in lower for w in ["export", "download", "save", "generate", "create"])


def _is_attendance_query(text: str, role: str = "") -> bool:
    """Return True if the text looks like an attendance lookup request."""
    lower = text.lower()
    has_kw = any(kw in lower for kw in _ATTENDANCE_KEYWORDS)
    if not has_kw:
        return False
        
    has_id = bool(_ATTENDANCE_RE.search(text))
    # If a student uses personal pronouns + attendance keyword, assume it's their own
    is_personal_query = role == "student" and any(w in lower for w in ["my", "mine", "i "])
    return has_id or is_personal_query


def _answer_attendance(query_text: str, username: str = "") -> str:
    """
    Directly answer an attendance query using the CSV data source.
    No LLM call needed — reads from existing get_attendance() function.
    """
    match = _ATTENDANCE_RE.search(query_text)
    
    if match:
        student_id = match.group(1).upper()
    elif username and username.upper().startswith("STU"):
        student_id = username.upper()
    else:
        return "I couldn't identify a valid student ID for your query. Please provide one (e.g., STU001)."

    pct = get_attendance(student_id)

    status = "✅ sufficient" if pct >= 75 else "⚠️ below the required 75% threshold"
    return (
        f"📊 **Attendance Report for {student_id}**\n\n"
        f"- **Attendance:** `{pct:.1f}%`\n"
        f"- **Status:** {status}\n\n"
        f"{'The student is eligible to apply for leave.' if pct >= 75 else 'The student must attend more classes before applying for leave.'}"
    )


def _extract_raw_tool_call(text: str):
    """
    Fallback parser: if the model outputs the tool call as plain text
    (e.g. <function/run_campusflow_agent>{"clarified_query":"..."})</function>),
    extract and return the clarified_query string. Returns None if not found.
    """
    if not text:
        return None
    m = _RAW_TOOL_CALL_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1)).get("clarified_query")
        except json.JSONDecodeError:
            pass
    m2 = _BARE_JSON_RE.search(text)
    if m2:
        return m2.group(1)
    return None


class LLMOrchestrator:
    """
    Wrapper-Based Architecture (Non-Intrusive).
    Sits between UI and existing system functions.
    Handles three routing paths:
      1. Attendance query  → answer directly from CSV (no LLM round-trip needed)
      2. Campus workflow   → route to existing executor.run() via tool_calls
      3. Conversational    → answer directly from LLM content

    Bug fix: models sometimes emit the function call as raw text instead of
    using the structured tool_calls mechanism. Both forms are detected.
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", tavily_key: str = ""):
        self.api_key = api_key
        self.model = model
        self.tavily_key = tavily_key

    def _run_backend(self, session_id, query, role, client, on_log):
        """Thin wrapper — calls existing executor without modification."""
        return executor.run(
            session_id=session_id,
            query_text=query,
            role=role,
            client=client,
            model=self.model,
            tavily_api_key=self.tavily_key,
            on_log=on_log,
        )

    def process_request(
        self,
        session_id: str,
        query_text: str,
        role: str,
        on_log=None,
        chat_history: list | None = None,
    ) -> dict:
        """
        Process a request with full conversation context.
        chat_history: list of {role, content} dicts. If None, loaded from DB.
        """
        client = Groq(api_key=self.api_key) if self.api_key else None

        # Load conversation history from DB if not provided
        if chat_history is None:
            try:
                from campus import db as _db
                raw_msgs = _db.get_messages(session_id)
                # Only keep last 10 turns to stay within context limits
                chat_history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in raw_msgs[-10:]
                ]
            except Exception:
                chat_history = []

        try:
            if not client:
                raise ValueError("Missing Groq API Key")

            # ── Path -1: PDF Export Request ──
            if _is_pdf_export_query(query_text):
                if on_log:
                    on_log("ORCHESTRATOR: Detected PDF export intent — triggering PDF generation pipeline.")
                return {
                    "workflow_type": "pdf_export",
                    "chat_reply": "I have collected the chat history and generated a PDF document. You can download it below.",
                }

            # ── Path 0.5: Data modification (attendance/timetable write) ─
            if _is_data_write_intent(query_text):
                if on_log:
                    on_log("ORCHESTRATOR: Detected potential data modification intent — parsing command...")
                parsed_action = _data_editor.parse_data_command(
                    query_text, role, client, self.model
                )
                if parsed_action is not None:
                    # Get the authenticated username from session state if available
                    try:
                        import streamlit as _st
                        username = _st.session_state.get("username", role)
                    except Exception:
                        username = role

                    if on_log:
                        on_log(f"ORCHESTRATOR: Data action detected — {parsed_action.get('action')} — validating role '{role}'...")

                    result = _data_editor.execute_data_command(parsed_action, username, role)

                    if on_log:
                        status = "✅ success" if result.get("success") else "❌ denied/error"
                        on_log(f"ORCHESTRATOR: Data modification {status}")

                    return {
                        "workflow_type": "data_modification",
                        "chat_reply": result["message"],
                        "data_action": parsed_action,
                        "data_result": result,
                    }

            # ── Path 0: Attendance lookup (answered directly from CSV) ──
            if _is_attendance_query(query_text, role):
                # Try getting the username from Streamlit session context for implicit checking
                auth_user = role # fallback
                try:
                    import streamlit as _st
                    auth_user = _st.session_state.get("username", role)
                except Exception:
                    pass
                
                if on_log:
                    on_log(f"ORCHESTRATOR: Detected attendance query for user '{auth_user}' — reading directly from CSV data...")
                return {
                    "workflow_type": "general_chat",
                    "chat_reply": _answer_attendance(query_text, auth_user),
                }

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "run_campusflow_agent",
                        "description": (
                            "Trigger the CampusFlow autonomous agent for ONLY these tasks: "
                            "Lab Booking, Leave Requests, Room Booking, IT Complaints, or Academic Web Search. "
                            "DO NOT call this tool for anything else."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "clarified_query": {
                                    "type": "string",
                                    "description": "The cleaned up user query to pass to the backend agent.",
                                }
                            },
                            "required": ["clarified_query"],
                        },
                    },
                }
            ]

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are the CampusFlow LLM Orchestrator. "
                        f"The user has the role: {role}. "
                        "Interpret the user's natural language input, including follow-up messages that reference the conversation history below. "
                        "If the request is about: booking a lab, applying for leave, booking a room, "
                        "filing a complaint, or performing a web/academic search — "
                        "call the 'run_campusflow_agent' tool with a fully clarified, self-contained version of the query. "
                        "For small talk, greetings, or anything outside CampusFlow scope, "
                        "respond directly without calling any tool. "
                        "IMPORTANT: Never output the tool call as raw text or XML. "
                        "Always use the structured tool_calls mechanism."
                    ),
                },
                # Inject conversation history for follow-up context
                *chat_history,
                {"role": "user", "content": query_text},
            ]

            res = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=500,
            )

            msg = res.choices[0].message

            # ── Path 1: Proper structured tool_calls (normal case) ────────
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                if tool_call.function.name == "run_campusflow_agent":
                    args = json.loads(tool_call.function.arguments)
                    clean_query = args.get("clarified_query", query_text)
                    if on_log:
                        on_log("ORCHESTRATOR: Routing via structured tool_calls.")
                    return self._run_backend(session_id, clean_query, role, client, on_log)

            # ── Path 2: Model leaked raw text tool call (bug fix) ─────────
            raw_query = _extract_raw_tool_call(msg.content or "")
            if raw_query:
                if on_log:
                    on_log("ORCHESTRATOR: Detected raw text tool call — parsing and re-routing.")
                return self._run_backend(session_id, raw_query, role, client, on_log)

            # ── Path 3: Pure conversational reply ─────────────────────────
            if on_log:
                on_log("ORCHESTRATOR: Processed as conversational query.")

            reply = (msg.content or "").strip()
            if not reply:
                reply = "I'm not sure how to help with that. Please try a CampusFlow request (leave, lab, room, complaint, or search)."

            return {
                "workflow_type": "general_chat",
                "chat_reply": reply,
            }

        except Exception as e:
            # Safe fallback: bypass orchestrator, call executor directly
            if on_log:
                on_log(f"ORCHESTRATOR FAILED ({e}). Falling back to direct executor...")
            client = Groq(api_key=self.api_key) if self.api_key else None
            return self._run_backend(session_id, query_text, role, client, on_log)
