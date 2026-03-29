# ============================================================
# hod_escalator.py — Tool 3: Draft HOD Email if Escalation Needed
# ============================================================
# PURPOSE:
#   If the knowledge retriever returns NOT_FOUND, or the query
#   requires manual approval (leave, equipment booking), this tool
#   drafts a professional email to the HOD using Gmail API / SMTP.
#   If no escalation is needed, it gracefully skips.
#
# SYSTEM PROMPT DESIGN:
#   The agent must judge whether to escalate (not all queries need it).
#   If escalation is needed, the email must be professional, concise,
#   and include all necessary student details.
# ============================================================
import json


def run(student_request, classifier_output, knowledge_output, client, model):
    """Draft HOD escalation email if required, or skip if knowledge base resolved the query."""

    # Parse knowledge retriever to check if escalation is needed
    try:
        knowledge_data = json.loads(knowledge_output)
        answer_found = knowledge_data.get("answer_found", False)
        requires_hod = False
        # Also check classifier output for requires_hod_approval flag
        try:
            classifier_data = json.loads(classifier_output)
            requires_hod = classifier_data.get("requires_hod_approval", False)
        except Exception:
            pass
    except Exception:
        answer_found = False
        requires_hod = True

    prompt = f"""You are the HOD Escalator for CampusBot — an autonomous student support agent.

You decide whether to escalate the student request to the HOD, and if so, draft a professional email.

STUDENT REQUEST: "{student_request}"

CLASSIFIER OUTPUT:
{classifier_output}

KNOWLEDGE RETRIEVER OUTPUT:
{knowledge_output}

ESCALATION NEEDED: {"YES — knowledge base could not resolve this or HOD approval is required" if not answer_found or requires_hod else "NO — query was resolved by knowledge base"}

YOUR TASK:
{"Draft a professional, formal email to the HOD with the student's request details. Include all relevant information (dates, reason, urgency). Sign off as 'CampusBot Automated Escalation System'" if not answer_found or requires_hod else "No email needed. The knowledge base resolved this query."}

Respond in this exact JSON format:
{{
  "escalation_triggered": true or false,
  "email_draft": {{
    "to": "hod@department.edu",
    "subject": "<concise subject>",
    "body": "<full professional email body>",
    "priority": "high | medium | low"
  }},
  "escalation_reason": "<why this was escalated or why it was skipped>"
}}

If escalation_triggered is false, set email_draft to null.
Only output the raw JSON. No markdown, no extra text.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()
