# ============================================================
# executor.py — Routes plan steps to tool functions (CampusBot)
# ============================================================
# PURPOSE:
#   The executor takes the JSON plan from planner.py and runs each
#   step by calling the correct tool function. It is the "hands"
#   of the agent — it does the actual work.
#
# INFORMATION FLOW (4-tool pipeline):
#   request_classifier   → needs only the student request
#   form_parser          → needs request + classifier output
#   availability_checker → needs request + form + classifier outputs
#   email_router         → needs request + form + classifier + availability outputs
#
# RESILIENCE:
#   Each tool call is wrapped in retry logic with exponential backoff.
# ============================================================

import time

from agent.tools import (  # type: ignore
    request_classifier,
    knowledge_retriever,
    hod_escalator,
    response_drafter,
)
from agent.tools import form_parser, availability_checker, email_router  # type: ignore

MAX_RETRIES = 2
RETRY_DELAY = 2


def _run_with_retry(fn, tool_name, on_log):
    """Run a tool function with retry logic for transient API errors."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt <= MAX_RETRIES:
                wait = RETRY_DELAY * (2 ** (attempt - 1))
                on_log(f"Tool {tool_name} error (attempt {attempt}): {e} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                on_log(f"Tool {tool_name} failed after {attempt} attempts: {e}")
                raise last_error


def run_plan(plan, idea, client, model, on_log):
    """Execute each step in the CampusBot plan by routing to the correct tool."""

    results = {}

    for step in plan:
        tool = step["tool"]
        on_log(f"Running tool: {tool} — {step['reason']}")

        # ── ROUTE TO THE CORRECT TOOL ────────────────────────────────

        if tool == "request_classifier":
            # Tool 1: Classify the student's request and extract key details
            results["request_classifier"] = _run_with_retry(
                lambda: request_classifier.run(idea, client, model),
                tool, on_log,
            )

        elif tool == "form_parser":
            # Tool 2: Parse PDF/text form — extract name, type, date, department
            rc = results.get("request_classifier", "{}")
            results["form_parser"] = _run_with_retry(
                lambda: form_parser.run(idea, client, model),
                tool, on_log,
            )

        elif tool == "availability_checker":
            # Tool 3: Check Google Sheets for slot/room availability
            fp = results.get("form_parser", "{}")
            rc = results.get("request_classifier", "{}")
            results["availability_checker"] = _run_with_retry(
                lambda: availability_checker.run(idea, fp, rc, client, model),
                tool, on_log,
            )

        elif tool == "email_router":
            # Tool 4: Send routed email to HOD and Telegram confirmation to student
            fp = results.get("form_parser", "{}")
            rc = results.get("request_classifier", "{}")
            av = results.get("availability_checker", "{}")
            results["email_router"] = _run_with_retry(
                lambda: email_router.run(idea, fp, rc, av, client, model),
                tool, on_log,
            )

        else:
            on_log(f"Unknown tool: {tool} — skipping")
            continue

        on_log(f"Tool {tool} complete ✓")

    return results
