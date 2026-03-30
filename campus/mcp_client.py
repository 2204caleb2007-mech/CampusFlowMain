# ============================================================
# campus/mcp_client.py — CampusFlow MCP Client
# ============================================================
# Connects to the FastMCP server running at MCP_SERVER_URL.
# Provides a thin, synchronous interface for calling MCP tools
# from the Streamlit app / orchestrator.
#
# Falls back to direct function calls if the MCP server is
# unreachable — so the app works even without the MCP server.
# ============================================================

import os
import json
import time
import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger("campusflow.mcp_client")

# ── SERVER CONFIG ─────────────────────────────────────────────────
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765")
MCP_TIMEOUT    = int(os.getenv("MCP_TIMEOUT", "10"))   # seconds per request
MCP_MAX_RETRY  = int(os.getenv("MCP_MAX_RETRY", "2"))  # retries on transient errors


# ── HEALTH CHECK ─────────────────────────────────────────────────

def is_server_available() -> bool:
    """Return True if the MCP server is reachable."""
    try:
        r = requests.get(f"{MCP_SERVER_URL}/health", timeout=3)
        return r.status_code < 500
    except Exception:
        return False


# ── CORE CALL ─────────────────────────────────────────────────────

def call_tool(tool_name: str, arguments: Dict[str, Any],
              on_log=None) -> Dict[str, Any]:
    """
    Call a tool on the MCP server.

    Protocol: FastMCP HTTP endpoint is /tools/<tool_name>/call
    Payload:  {"arguments": {...}}
    Response: {"content": [{"type": "text", "text": "<json>"}]}
              or {"result": {...}} depending on FastMCP version.

    Falls back to direct function call if server unreachable.
    """
    url = f"{MCP_SERVER_URL}/tools/{tool_name}/call"
    payload = {"arguments": arguments}

    if on_log:
        on_log(f"MCP → calling tool '{tool_name}'")

    last_err = None
    for attempt in range(1, MCP_MAX_RETRY + 2):
        try:
            t0 = time.time()
            resp = requests.post(url, json=payload, timeout=MCP_TIMEOUT)
            elapsed = round((time.time() - t0) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                # FastMCP wraps result in content[0].text as JSON string
                if "content" in data and data["content"]:
                    raw = data["content"][0].get("text", "{}")
                    try:
                        result = json.loads(raw)
                    except Exception:
                        result = {"raw": raw}
                elif "result" in data:
                    result = data["result"]
                else:
                    result = data

                if on_log:
                    on_log(f"MCP ← '{tool_name}' OK ({elapsed}ms)")
                logger.info(f"MCP tool '{tool_name}' OK in {elapsed}ms")
                return result

            # Non-200 — log and retry
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning(f"MCP '{tool_name}' attempt {attempt}: {last_err}")

        except requests.exceptions.ConnectionError as e:
            last_err = f"Connection refused — is the MCP server running? ({e})"
            logger.warning(f"MCP '{tool_name}' attempt {attempt}: {last_err}")
            break  # Don't retry a connection error — go to fallback immediately

        except Exception as e:
            last_err = str(e)
            logger.warning(f"MCP '{tool_name}' attempt {attempt}: {e}")

        if attempt <= MCP_MAX_RETRY:
            time.sleep(1.0 * attempt)

    # ── FALLBACK: direct function call ───────────────────────────
    if on_log:
        on_log(f"MCP server unavailable — falling back to direct call for '{tool_name}'")
    logger.warning(f"MCP fallback for '{tool_name}': {last_err}")
    return _direct_fallback(tool_name, arguments, on_log)


# ── DIRECT FALLBACKS ──────────────────────────────────────────────
# These mirror the MCP tools but call the underlying functions directly.
# Activated automatically when the MCP server is not running.

def _direct_fallback(tool_name: str, args: Dict[str, Any],
                     on_log=None) -> Dict[str, Any]:
    """Call the underlying function directly (no MCP server needed)."""
    try:
        if tool_name == "classify_request":
            from groq import Groq
            from campus import classifier
            client = Groq(api_key=args.get("groq_api_key", "")) if args.get("groq_api_key") else None
            if client:
                return classifier.classify(args["query_text"], client,
                                           args.get("model", "llama-3.3-70b-versatile"),
                                           args.get("role", "student"))
            return classifier._keyword_fallback(args["query_text"])

        elif tool_name == "check_availability":
            from campus import csv_loader
            from agent.tools.availability_checker import check_availability
            schedule = csv_loader.get_lab_schedule()
            return check_availability(
                args["resource"], args["date"],
                args.get("start_time", "09:00"), args.get("end_time", "11:00"),
                schedule,
            )

        elif tool_name == "evaluate_policy":
            from campus import policy_engine
            return policy_engine.evaluate(args["workflow_type"], args["schema"])

        elif tool_name == "handle_complaint":
            from campus import policy_engine
            import uuid
            schema = {**args, "type": "complaint"}
            policy = policy_engine.evaluate("complaint", schema)
            sla_map = {"urgent": 4, "high": 8, "normal": 24, "low": 48}
            return {**policy, "ticket_id": f"TKT-{uuid.uuid4().hex[:6].upper()}",
                    "sla_hours": sla_map.get(args.get("priority", "normal"), 24)}

        elif tool_name == "web_search":
            from groq import Groq
            from campus import web_researcher
            client = Groq(api_key=args.get("groq_api_key", "")) if args.get("groq_api_key") else None
            search_data = web_researcher.search(args["query"], args.get("tavily_api_key", ""))
            if client:
                answer = web_researcher.synthesize_answer(
                    args["query"], search_data, client,
                    args.get("model", "llama-3.3-70b-versatile"),
                    args.get("role", "student"),
                )
            else:
                answer = search_data.get("answer", "No answer.")
            return {"answer": answer, "success": search_data.get("success", False),
                    "sources": [{"title": r.get("title"), "url": r.get("url")}
                                for r in search_data.get("results", [])[:3]]}

        elif tool_name == "send_notification":
            from campus import notifier
            policy = {
                "result": args.get("policy_result", "UNKNOWN"),
                "reason": args.get("policy_reason", ""),
                "alternatives": args.get("alternatives", []),
            }
            return notifier.notify(args.get("workflow_type", ""), args.get("schema", {}),
                                   policy, args.get("role", "student"))

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Direct fallback for '{tool_name}' failed: {e}")
        return {"error": str(e)}


# ── CONVENIENCE HELPERS ───────────────────────────────────────────
# These provide typed wrappers so callers don't need to build
# argument dicts manually.

def mcp_classify(query_text: str, role: str, groq_api_key: str,
                 model: str, on_log=None) -> dict:
    return call_tool("classify_request", {
        "query_text": query_text, "role": role,
        "groq_api_key": groq_api_key, "model": model,
    }, on_log)


def mcp_check_availability(resource: str, date: str,
                            start_time: str = "09:00",
                            end_time: str = "11:00", on_log=None) -> dict:
    return call_tool("check_availability", {
        "resource": resource, "date": date,
        "start_time": start_time, "end_time": end_time,
    }, on_log)


def mcp_evaluate_policy(workflow_type: str, schema: dict, on_log=None) -> dict:
    return call_tool("evaluate_policy", {
        "workflow_type": workflow_type, "schema": schema,
    }, on_log)


def mcp_web_search(query: str, tavily_api_key: str, groq_api_key: str,
                   model: str, role: str, on_log=None) -> dict:
    return call_tool("web_search", {
        "query": query, "tavily_api_key": tavily_api_key,
        "groq_api_key": groq_api_key, "model": model, "role": role,
    }, on_log)


def mcp_send_notification(workflow_type: str, schema: dict,
                           policy_result: str, policy_reason: str,
                           alternatives: list = None, role: str = "student",
                           on_log=None) -> dict:
    return call_tool("send_notification", {
        "workflow_type": workflow_type, "schema": schema,
        "policy_result": policy_result, "policy_reason": policy_reason,
        "alternatives": alternatives or [], "role": role,
    }, on_log)
