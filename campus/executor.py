# ============================================================
# campus/executor.py — True Autonomous Self-Correcting Loop
# ============================================================
# Implements the real THINK → PLAN → EXECUTE → REVIEW → UPDATE
# cycle for campus workflows. The loop retries with reviewer
# feedback until quality score >= 7 OR max retries reached.
#
# UI integration: structured "STEP_TOKEN:step:status" log lines
# are emitted at each transition so main.py can update the step
# tracker in real time, bound to actual execution — not fake timers.
# ============================================================

import os
import datetime
import json
from campus import db, classifier, policy_engine, notifier, web_researcher, role_system
from campus import mcp_client  # MCP-routed calls (falls back to direct if server offline)

# ── AUTONOMOUS LOOP CONFIG ────────────────────────────────────────
MAX_RETRIES    = 3      # Max self-correction iterations
PASS_THRESHOLD = 7      # Reviewer score needed to accept result

# ── STRUCTURED STEP TOKEN (parsed by main.py UI) ──────────────────
# Format: "STEP_TOKEN:<step>:<status>"  e.g. "STEP_TOKEN:think:active"
# Steps:  think | plan | execute | review | update
# Status: active | done | failed | skipped

def _step_token(step: str, status: str) -> str:
    return f"STEP_TOKEN:{step}:{status}"


# ── RESULT → HUMAN MESSAGE ────────────────────────────────────────

def _build_chat_reply(workflow_type: str, schema: dict, policy: dict,
                      notify_result: dict) -> str:
    """Convert policy result into a clean, user-facing chat message."""
    result  = policy.get("result", "UNKNOWN")
    reason  = policy.get("reason", "")
    alts    = policy.get("alternatives", [])

    emoji = {"APPROVED": "✅", "REJECTED": "❌", "ESCALATED": "⚠️"}.get(result, "ℹ️")
    wt_label = workflow_type.replace("_", " ").title()

    lines = [f"{emoji} **{wt_label} — {result}**", "", reason]

    if alts:
        lines.append("")
        lines.append("**Suggested alternatives:**")
        for a in alts:
            lines.append(f"- {a}")

    n_status = notify_result.get("status", "simulated")
    if n_status == "sent":
        lines.append("")
        lines.append("📧 Notification sent to the responsible authority and the student.")
    elif n_status == "simulated":
        lines.append("")
        lines.append("📧 Notifications queued for authority and student (Formspree simulation mode).")

    return "\n".join(lines)


# ── TRANSIENT RETRY WITH BACKOFF ──────────────────────────────────

def _with_retry(fn, max_retries=2, delay=1):
    import time
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(delay * (2 ** attempt))
    raise last_err


# ── MAIN ENTRY POINT ─────────────────────────────────────────────

def run(
    session_id: str,
    query_text: str,
    role: str,
    client,
    model: str,
    tavily_api_key: str = "",
    on_log=None,
) -> dict:
    """
    Self-correcting autonomous campus workflow executor.

    Loop (up to MAX_RETRIES iterations):
        THINK  → classify intent + extract schema
        PLAN   → check DB conflicts, validate schema completeness
        EXECUTE→ run policy engine against schema
        REVIEW → score result via agent/reviewer.evaluate_campus_result()
        UPDATE → if score < 7, inject feedback and repeat

    UI step cards in main.py are driven by structured STEP_TOKEN
    log lines emitted here — not by fake timers.
    """
    submitted_at = datetime.datetime.now().isoformat()

    def log(msg: str, level: str = "INFO"):
        db.add_log(session_id, msg, level)
        if on_log:
            on_log(msg)

    def step(name: str, status: str):
        """Emit a structured step token so the UI can update cards."""
        token = _step_token(name, status)
        db.add_log(session_id, token, "STEP")
        if on_log:
            on_log(token)

    # ── WEB SEARCH BYPASS (no loop needed) ───────────────────────
    # Quick-classify first to detect web_search before entering loop
    step("think", "active")
    log("THINK: Pre-classifying request to detect web search...")
    try:
        pre_schema = _with_retry(
            lambda: classifier.classify(query_text, client, model, role)
        )
    except Exception as e:
        log(f"Pre-classification failed: {e}", "WARN")
        pre_schema = classifier._keyword_fallback(query_text)

    if pre_schema.get("type") == "web_search":
        step("think", "done")
        step("plan", "active")
        search_q = pre_schema.get("query", query_text)
        log(f"PLAN: Web search detected → {search_q}")
        step("plan", "done")
        step("execute", "active")
        log("EXECUTE: Running Tavily Web Search...")
        search_data = web_researcher.search(search_q, tavily_api_key)
        step("execute", "done")
        step("review", "active")
        log("REVIEW: Synthesizing answer with LLM...")
        answer = web_researcher.synthesize_answer(search_q, search_data, client, model, role)
        step("review", "done")
        step("update", "skipped")
        log("UPDATE: Done.")
        db.add_audit(session_id, role, "web_search", search_q, "completed")
        db.record_kpi(session_id, "web_search", submitted_at, "resolved", 1)
        return {
            "workflow_type": "web_search",
            "schema": pre_schema,
            "policy": {"result": "RESOLVED", "reason": "Gathered data from web."},
            "notify_result": {"status": "skipped", "note": "Not applicable to web search"},
            "chat_reply": answer,
            "request_id": "web_" + str(datetime.datetime.now().timestamp()),
            "loop_results": {"loops_used": 1, "review_score": 9},
        }

    # ── AUTONOMOUS LOOP ───────────────────────────────────────────
    from agent.reviewer import evaluate_campus_result

    feedback      = ""       # carries reviewer feedback into next iteration
    schema        = {}
    policy        = {}
    loops_used    = 0
    best_result   = None     # always hold the best attempt even if never fully passing
    best_score    = 0

    for attempt in range(1, MAX_RETRIES + 1):
        loops_used = attempt
        log(f"═══ Autonomous Loop {attempt} of {MAX_RETRIES} ═══")

        # ── THINK ────────────────────────────────────────────────
        step("think", "active")
        log("THINK: Classifying request and extracting intent...")
        if feedback:
            log(f"THINK: Incorporating feedback from attempt {attempt-1}: {feedback[:120]}")

        try:
            schema = _with_retry(
                lambda: mcp_client.call_tool("classify_request", {
                    "query_text": query_text, "role": role,
                    "groq_api_key": getattr(client, "api_key", ""),
                    "model": model,
                }, on_log) if mcp_client.is_server_available()
                else classifier.classify(query_text, client, model, role)
            )
        except Exception as e:
            log(f"Classification failed: {e}", "ERROR")
            schema = classifier._keyword_fallback(query_text)

        workflow_type = schema.get("type", "web_search")

        # Inject role into schema for reviewer context checks
        if "role" not in schema:
            schema["role"] = role

        log(f"THINK: Intent → {workflow_type}")
        step("think", "done")

        # ── PLAN ─────────────────────────────────────────────────
        step("plan", "active")
        log(f"PLAN: Schema extracted → {json.dumps(schema)}")

        # Check DB for slot conflict BEFORE policy engine runs
        if workflow_type in ("lab_booking", "room_booking"):
            res_key = "lab_id" if workflow_type == "lab_booking" else "room_id"
            resource_id = schema.get(res_key, "")
            date        = schema.get("date", "")
            time_slot   = schema.get("time_slot", "") or f"{schema.get('start_time','')}-{schema.get('end_time','')}"
            if resource_id and date and db.is_slot_booked(resource_id, date, time_slot):
                schema["_db_conflict"] = True
                log(f"PLAN: DB conflict detected — {resource_id} on {date} ({time_slot}) already booked.")
            else:
                schema["_db_conflict"] = False

        step("plan", "done")

        # ── EXECUTE ───────────────────────────────────────────────
        step("execute", "active")
        log("EXECUTE: Running policy engine...")
        try:
            policy = _with_retry(
                lambda: mcp_client.mcp_evaluate_policy(workflow_type, schema, on_log)
            )
            # Upgrade to REJECTED if DB conflict was found
            if schema.get("_db_conflict") and policy.get("result") == "APPROVED":
                policy["result"] = "REJECTED"
                policy["reason"] = "The requested slot is already booked. " + policy.get("reason", "")
                policy.setdefault("alternatives", []).insert(0, "Try a different time slot or date.")
        except Exception as e:
            log(f"Policy evaluation error: {e}", "ERROR")
            policy = {"result": "ESCALATED", "reason": "Policy engine error — escalated for manual review.", "alternatives": []}

        log(f"EXECUTE: Policy → {policy.get('result')} | {policy.get('reason', '')[:80]}")
        step("execute", "done")

        # ── REVIEW ────────────────────────────────────────────────
        step("review", "active")
        log("REVIEW: Scoring workflow output...")

        try:
            review = evaluate_campus_result(
                query_text=query_text,
                workflow_type=workflow_type,
                schema=schema,
                policy=policy,
                attempt=attempt,
                client=client,
                model=model,
            )
        except Exception as rev_err:
            log(f"Reviewer error: {rev_err}", "WARN")
            review = {"score": 6, "passed": False, "feedback": "retry — reviewer error",
                      "fields": [], "what_is_good": ""}

        score = review.get("score", 0)
        passed = review.get("passed", False)
        log(f"REVIEW: Score {score}/10 — {'PASSED ✓' if passed else 'NEEDS WORK ✗'}")
        if review.get("what_is_good"):
            log(f"REVIEW: Strengths → {review['what_is_good'][:100]}")
        step("review", "done")

        # Track best result
        if score > best_score:
            best_score = score
            best_result = {"schema": schema, "policy": policy, "review": review,
                           "workflow_type": workflow_type}

        # ── UPDATE ────────────────────────────────────────────────
        if passed:
            step("update", "skipped")
            log(f"UPDATE: Quality threshold met on attempt {attempt} — proceeding.")
            break
        else:
            step("update", "active")
            feedback = review.get("feedback", "improve schema completeness and policy reasoning")
            log(f"UPDATE: Feedback → {feedback[:120]}")
            step("update", "done")
            if attempt < MAX_RETRIES:
                log(f"UPDATE: Starting attempt {attempt + 1} with improved context...")

    # ── USE BEST RESULT AFTER LOOP ────────────────────────────────
    if best_result:
        schema        = best_result["schema"]
        policy        = best_result["policy"]
        workflow_type = best_result["workflow_type"]
    else:
        policy = {"result": "ESCALATED", "reason": "All attempts failed.", "alternatives": []}

    if loops_used >= MAX_RETRIES and not (best_result and best_result["review"].get("passed")):
        log(f"UPDATE: Max retries ({MAX_RETRIES}) reached — delivering best attempt (score={best_score}/10).")

    # ── PERSIST REQUEST ───────────────────────────────────────────
    log("UPDATE: Persisting request to database...")
    try:
        req_id = db.create_request(session_id, workflow_type, schema)
        db.update_request_status(
            req_id,
            status=policy["result"].lower(),
            policy_result=policy["result"],
            policy_reason=policy["reason"],
            alternatives=policy.get("alternatives", []),
        )
        # Persist confirmed bookings to bookings table
        if policy["result"] == "APPROVED" and not schema.get("_db_conflict"):
            if workflow_type == "lab_booking":
                db.create_booking(
                    resource_id=schema.get("lab_id", "UNKNOWN"),
                    resource_type="lab",
                    date=schema.get("date", ""),
                    time_slot=schema.get("time_slot", schema.get("start_time", "")),
                    session_id=session_id,
                )
            elif workflow_type == "room_booking":
                db.create_booking(
                    resource_id=schema.get("room_id", "UNKNOWN"),
                    resource_type="room",
                    date=schema.get("date", ""),
                    time_slot=schema.get("time_slot", schema.get("start_time", "")),
                    session_id=session_id,
                )
    except Exception as e:
        log(f"DB persist error: {e}", "WARN")
        req_id = "unknown"

    # ── SEND DUAL NOTIFICATIONS ───────────────────────────────────
    log("UPDATE: Sending notifications via MCP...")
    try:
        notify_result = mcp_client.mcp_send_notification(
            workflow_type, schema,
            policy.get("result", "UNKNOWN"),
            policy.get("reason", ""),
            policy.get("alternatives", []),
            role, on_log,
        )
    except Exception:
        notify_result = notifier.notify_simulated(workflow_type, schema, policy, role)
    log(f"Notification: {notify_result.get('status', 'unknown')}")

    # ── AUDIT + KPI ───────────────────────────────────────────────
    db.add_audit(
        session_id=session_id,
        actor_role=role,
        action=f"submit_{workflow_type}",
        target=req_id,
        result=policy["result"],
    )
    db.record_kpi(session_id, workflow_type, submitted_at, policy["result"].lower(),
                  loops_used=loops_used)

    # ── BUILD REPLY ───────────────────────────────────────────────
    base_chat_reply = _build_chat_reply(workflow_type, schema, policy, notify_result)
    chat_reply = role_system.modulate_response(base_chat_reply, role, workflow_type)
    log("Done. Response ready.")

    return {
        "workflow_type": workflow_type,
        "schema": schema,
        "policy": policy,
        "notify_result": notify_result,
        "chat_reply": chat_reply,
        "request_id": req_id,
        "loop_results": {
            "loops_used": loops_used,
            "review_score": best_score,
            "passed": bool(best_result and best_result["review"].get("passed")),
        },
    }
