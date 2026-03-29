# ============================================================
# campus/executor.py — Unified Multi-Workflow Executor
# ============================================================
# Orchestrates a full request lifecycle:
#   1. Classify free-text into a structured schema
#   2. Evaluate schema against the policy engine
#   3. Persist request, logs, and KPIs to SQLite
#   4. Send notification via Formspree
#   5. Return a human-readable AI reply for the chat UI
# ============================================================

import datetime
import json
from campus import db, classifier, policy_engine, notifier, web_researcher, role_system

# ── RESULT → HUMAN MESSAGE ───────────────────────────────────────

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

    # Notification confirmation
    n_status = notify_result.get("status", "simulated")
    if n_status == "sent":
        lines.append("")
        lines.append("📧 Notification sent to the responsible authority.")
    elif n_status == "simulated":
        lines.append("")
        lines.append("📧 Notification queued (Formspree simulation mode).")

    return "\n".join(lines)


# ── RETRY WITH BACKOFF ────────────────────────────────────────────

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
    Full autonomous workflow execution for a single query.

    Returns:
        {
          "workflow_type": str,
          "schema": dict,
          "policy": dict,
          "notify_result": dict,
          "chat_reply": str,
          "request_id": str,
        }
    """
    submitted_at = datetime.datetime.now().isoformat()

    def log(msg: str, level: str = "INFO"):
        db.add_log(session_id, msg, level)
        if on_log:
            on_log(msg)

    # ── STEP 1: CLASSIFY ─────────────────────────────────────────
    log("THINK: Classifying request...")
    try:
        schema = _with_retry(
            lambda: classifier.classify(query_text, client, model, role)
        )
    except Exception as e:
        log(f"Classification failed: {e}", "ERROR")
        schema = classifier._keyword_fallback(query_text)

    workflow_type = schema.get("type", "web_search")
    log(f"PLAN: Workflow identified → {workflow_type}")
    log(f"PLAN: Schema extracted → {json.dumps(schema)}")

    # ── SPECIAL BYPASS FOR WEB SEARCH ────────────────────────────
    if workflow_type == "web_search":
        search_q = schema.get("query", query_text)
        log("EXECUTE: Running Tavily Web Search...")
        search_data = web_researcher.search(search_q, tavily_api_key)

        log("REVIEW: Synthesizing answer with LLM...")
        answer = web_researcher.synthesize_answer(search_q, search_data, client, model, role)

        # Audit/KPI
        db.add_audit(session_id, role, "web_search", search_q, "completed")
        db.record_kpi(session_id, workflow_type, submitted_at, "resolved", 1)

        log("UPDATE: Done.")
        return {
            "workflow_type": workflow_type,
            "schema": schema,
            "policy": {"result": "RESOLVED", "reason": "Gathered data from web."},
            "notify_result": {"status": "skipped", "note": "Not applicable to web search"},
            "chat_reply": answer,
            "request_id": "web_" + str(datetime.datetime.now().timestamp()),
        }

    # ── STEP 2: POLICY ENGINE ────────────────────────────────────
    log("EXECUTE: Evaluating against campus policy rules...")
    try:
        policy = _with_retry(
            lambda: policy_engine.evaluate(workflow_type, schema)
        )
    except Exception as e:
        log(f"Policy evaluation error: {e}", "ERROR")
        policy = {"result": "ESCALATED", "reason": "Policy engine error — escalated for manual review.", "alternatives": []}

    log(f"REVIEW: Policy decision → {policy.get('result')} | {policy.get('reason')}")

    # ── STEP 3: PERSIST REQUEST ──────────────────────────────────
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
    except Exception as e:
        log(f"DB persist error: {e}", "WARN")
        req_id = "unknown"

    # ── STEP 4: SEND NOTIFICATION ─────────────────────────────────
    log("UPDATE: Sending notification...")
    try:
        notify_result = notifier.notify(workflow_type, schema, policy, role)
    except Exception:
        notify_result = notifier.notify_simulated(workflow_type, schema, policy, role)

    log(f"Notification: {notify_result.get('status', 'unknown')}")

    # ── STEP 5: AUDIT LOG ────────────────────────────────────────
    db.add_audit(
        session_id=session_id,
        actor_role=role,
        action=f"submit_{workflow_type}",
        target=req_id,
        result=policy["result"],
    )

    # ── STEP 6: KPI ──────────────────────────────────────────────
    outcome = policy["result"].lower()
    db.record_kpi(session_id, workflow_type, submitted_at, outcome, loops_used=1)

    # ── BUILD REPLY ───────────────────────────────────────────────
    base_chat_reply = _build_chat_reply(workflow_type, schema, policy, notify_result)
    
    # Apply role-based response modulation
    chat_reply = role_system.modulate_response(base_chat_reply, role, workflow_type)
    
    log("Done. Response ready for student.")

    return {
        "workflow_type": workflow_type,
        "schema": schema,
        "policy": policy,
        "notify_result": notify_result,
        "chat_reply": chat_reply,
        "request_id": req_id,
    }
