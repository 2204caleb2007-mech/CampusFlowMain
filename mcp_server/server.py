# ============================================================
# mcp_server/server.py — CampusFlow MCP Server
# ============================================================
# Exposes the 5 core campus tools as MCP endpoints using
# FastMCP over HTTP (default port 8765).
#
# Run standalone:
#   python mcp_server/server.py
#
# The Streamlit app connects to this server via MCPClient
# in campus/mcp_client.py.  All underlying logic lives in the
# existing modules — this file only wraps them as MCP tools.
# ============================================================

import sys
import os
import json
import logging

# Ensure the project root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# FastMCP MUST use sys.stderr for logging — never stdout in stdio mode.
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s [MCP] %(levelname)s %(message)s")
logger = logging.getLogger("campusflow.mcp")

from fastmcp import FastMCP

mcp = FastMCP(
    name="CampusFlow",
    instructions=(
        "You are the CampusFlow campus assistant. "
        "Use the available tools to handle student requests: "
        "lab bookings, leave requests, room bookings, complaints, and web searches."
    ),
)


# ──────────────────────────────────────────────────────────────
# TOOL 1: classify_request
# Wraps campus/classifier.py — determines workflow type + schema
# ──────────────────────────────────────────────────────────────
@mcp.tool
def classify_request(
    query_text: str,
    role: str = "student",
    groq_api_key: str = "",
    model: str = "llama-3.3-70b-versatile",
) -> dict:
    """
    Classify a student's free-text query into a structured workflow schema.

    Returns a dict with:
      - type: lab_booking | leave_request | room_booking | complaint | web_search
      - All extracted fields (date, lab_id, etc.)
    """
    try:
        from groq import Groq
        from campus import classifier
        client = Groq(api_key=groq_api_key) if groq_api_key else None
        if client is None:
            return classifier._keyword_fallback(query_text)
        schema = classifier.classify(query_text, client, model, role)
        logger.info(f"classify_request → {schema.get('type')}")
        return schema
    except Exception as e:
        logger.error(f"classify_request error: {e}")
        return {"type": "web_search", "query": query_text, "error": str(e)}


# ──────────────────────────────────────────────────────────────
# TOOL 2: check_availability
# Wraps agent/tools/availability_checker.py
# ──────────────────────────────────────────────────────────────
@mcp.tool
def check_availability(
    resource: str,
    date: str,
    start_time: str = "09:00",
    end_time: str = "11:00",
) -> dict:
    """
    Check whether a lab or room is available for a given date and time range.

    Returns:
      - available: bool
      - conflicts: list of conflicting bookings
      - free_slots_same_day: list of free slots
      - timetable_conflict: bool (True if blocked by regular class schedule)
    """
    try:
        from campus import csv_loader
        from agent.tools.availability_checker import check_availability as _check

        schedule = csv_loader.get_lab_schedule()
        result = _check(resource, date, start_time, end_time, schedule)
        logger.info(f"check_availability({resource}, {date}) → available={result['available']}")
        return result
    except Exception as e:
        logger.error(f"check_availability error: {e}")
        return {"available": False, "conflicts": [], "free_slots_same_day": [],
                "error": str(e)}


# ──────────────────────────────────────────────────────────────
# TOOL 3: evaluate_policy
# Wraps campus/policy_engine.py — applies campus rules
# ──────────────────────────────────────────────────────────────
@mcp.tool
def evaluate_policy(
    workflow_type: str,
    schema: dict,
) -> dict:
    """
    Evaluate a campus request against policy rules.

    Returns:
      - result: APPROVED | REJECTED | ESCALATED
      - reason: str
      - alternatives: list[str]
    """
    try:
        from campus import policy_engine
        result = policy_engine.evaluate(workflow_type, schema)
        logger.info(f"evaluate_policy({workflow_type}) → {result.get('result')}")
        return result
    except Exception as e:
        logger.error(f"evaluate_policy error: {e}")
        return {
            "result": "ESCALATED",
            "reason": f"Policy engine error: {e}",
            "alternatives": [],
        }


# ──────────────────────────────────────────────────────────────
# TOOL 4: handle_complaint
# Wraps complaint workflow through policy engine
# ──────────────────────────────────────────────────────────────
@mcp.tool
def handle_complaint(
    issue_type: str,
    location: str = "",
    priority: str = "normal",
    description: str = "",
    student_id: str = "",
) -> dict:
    """
    File and route a campus complaint (maintenance, facility, IT, etc.).

    Returns:
      - result: ESCALATED | APPROVED | REJECTED
      - reason: str
      - sla_hours: int (target resolution time)
      - ticket_id: str
    """
    try:
        import uuid
        from campus import policy_engine
        schema = {
            "type": "complaint",
            "issue_type": issue_type,
            "location": location,
            "priority": priority,
            "description": description,
            "student_id": student_id,
        }
        policy = policy_engine.evaluate("complaint", schema)
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        sla_map = {"urgent": 4, "high": 8, "normal": 24, "low": 48}
        result = {**policy, "ticket_id": ticket_id,
                  "sla_hours": sla_map.get(priority, 24)}
        logger.info(f"handle_complaint({issue_type}) → ticket={ticket_id}")
        return result
    except Exception as e:
        logger.error(f"handle_complaint error: {e}")
        return {"result": "ESCALATED", "reason": str(e), "alternatives": [],
                "ticket_id": "ERROR", "sla_hours": 24}


# ──────────────────────────────────────────────────────────────
# TOOL 5: web_search
# Wraps campus/web_researcher.py — Tavily-powered academic search
# ──────────────────────────────────────────────────────────────
@mcp.tool
def web_search(
    query: str,
    tavily_api_key: str = "",
    groq_api_key: str = "",
    model: str = "llama-3.3-70b-versatile",
    role: str = "student",
) -> dict:
    """
    Perform a web search for academic/campus queries using Tavily.

    Returns:
      - answer: str (synthesized LLM response)
      - sources: list of {title, url}
      - success: bool
    """
    try:
        from groq import Groq
        from campus import web_researcher
        client = Groq(api_key=groq_api_key) if groq_api_key else None
        search_data = web_researcher.search(query, tavily_api_key)
        if client:
            answer = web_researcher.synthesize_answer(query, search_data, client, model, role)
        else:
            answer = search_data.get("answer", "No answer available.")
        sources = [
            {"title": r.get("title", ""), "url": r.get("url", "")}
            for r in search_data.get("results", [])[:3]
        ]
        logger.info(f"web_search({query[:40]}) → success={search_data.get('success')}")
        return {"answer": answer, "sources": sources, "success": search_data.get("success", False)}
    except Exception as e:
        logger.error(f"web_search error: {e}")
        return {"answer": str(e), "sources": [], "success": False}


# ──────────────────────────────────────────────────────────────
# TOOL 6: send_notification
# Wraps campus/notifier.py — dual Formspree (admin + student)
# ──────────────────────────────────────────────────────────────
@mcp.tool
def send_notification(
    workflow_type: str,
    schema: dict,
    policy_result: str,
    policy_reason: str,
    alternatives: list = None,
    role: str = "student",
) -> dict:
    """
    Send dual email notifications (admin HOD + student) for a campus request.

    Returns:
      - status: sent | simulated | error
      - responses: dict (admin/student send results)
    """
    try:
        from campus import notifier
        policy = {
            "result": policy_result,
            "reason": policy_reason,
            "alternatives": alternatives or [],
        }
        result = notifier.notify(workflow_type, schema, policy, role)
        logger.info(f"send_notification({workflow_type}) → {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"send_notification error: {e}")
        return {"status": "error", "error": str(e)}


# ──────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CampusFlow MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--transport", default="http",
                        choices=["http", "stdio"], help="Transport mode")
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("Starting MCP server (stdio transport)...")
        mcp.run()  # stdio mode — for Claude Desktop / CLI
    else:
        logger.info(f"Starting MCP server (HTTP) on http://{args.host}:{args.port}")
        mcp.run(transport="http", host=args.host, port=args.port)
