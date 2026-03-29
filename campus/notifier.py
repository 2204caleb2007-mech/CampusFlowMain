# ============================================================
# campus/notifier.py — Formspree Email Trigger
# ============================================================
# Sends campus notifications via Formspree (no SMTP required).
# Endpoint: https://formspree.io/f/mdapedkq
# ============================================================

import json
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

FORMSPREE_URL = "https://formspree.io/f/mdapedk"


def _build_body(workflow_type: str, schema: dict, policy: dict, role: str) -> dict:
    """Build the Formspree POST payload."""
    result = policy.get("result", "UNKNOWN")
    reason = policy.get("reason", "")
    alts   = policy.get("alternatives", [])

    subject_map = {
        "lab_booking":   "CampusFlow: Lab Booking Request",
        "leave_request": "CampusFlow: Leave Request",
        "room_booking":  "CampusFlow: Room Booking Request",
        "complaint":     "CampusFlow: Complaint Filed",
    }
    subject = subject_map.get(workflow_type, "CampusFlow: Campus Request")

    body_lines = [
        f"Workflow: {workflow_type.replace('_', ' ').title()}",
        f"Role: {role}",
        f"Policy Decision: {result}",
        f"Reason: {reason}",
        "",
        "Request Details:",
        json.dumps(schema, indent=2),
    ]
    if alts:
        body_lines += ["", "Alternatives Suggested:", *[f"  - {a}" for a in alts]]

    return {
        "_subject": subject,
        "message": "\n".join(body_lines),
        "workflow": workflow_type,
        "decision": result,
    }


def notify(workflow_type: str, schema: dict, policy: dict,
           role: str = "student") -> dict:
    """
    Send a notification via Formspree.
    Returns {"status": "sent"|"simulated"|"error", ...}
    """
    if not REQUESTS_AVAILABLE:
        return {"status": "simulated", "note": "requests library not installed"}

    payload = _build_body(workflow_type, schema, policy, role)
    try:
        resp = _requests.post(
            FORMSPREE_URL,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            return {"status": "sent", "formspree_response": resp.json()}
        return {
            "status": "error",
            "http_status": resp.status_code,
            "body": resp.text[:200],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def notify_simulated(workflow_type: str, schema: dict, policy: dict,
                     role: str = "student") -> dict:
    """Return a simulated notification result without making an HTTP call."""
    return {
        "status": "simulated",
        "note": "Formspree call skipped in simulation mode",
        "would_send": _build_body(workflow_type, schema, policy, role),
    }
