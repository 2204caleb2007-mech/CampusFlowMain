# ============================================================
# reviewer.py — Scores CP1 draft with FIELD-LEVEL breakdown
# ============================================================
# PURPOSE:
#   The reviewer is what makes this an AUTONOMOUS agent instead of
#   a chatbot. It scores the CP1 draft against the actual 6-field
#   form requirements and decides pass or retry.
#
#   UPGRADE: Now returns per-field scores so the UI can show
#   exactly which fields passed and which need improvement.
#
# CP1 FORM FIELDS IT CHECKS:
#   Field 1: Problem Statement   (min 50 chars, specific pain point)
#   Field 2: Target Users        (min 10 chars, specific segment)
#   Field 3: Autonomy Loop Plan  (min 50 chars, maps THINK/PLAN/EXECUTE/REVIEW/UPDATE)
#   Field 4: Tools & APIs        (comma-separated, realistic stack)
#   Field 5: Evaluation Logic    (min 20 chars, measurable criteria)
#   Field 6: Expected Output     (min 20 chars, concrete deliverable)
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Make the reviewer stricter — require score 9 to pass instead
#    of 7. Check that the Autonomy Loop Plan mentions all 5 steps
#    explicitly (THINK, PLAN, EXECUTE, REVIEW, UPDATE)."
# ============================================================

import json

# ── PASS THRESHOLD ───────────────────────────────────────────────
# Score 7+ = pass. Below 7 = the agent retries with feedback.
PASS_THRESHOLD = 7

# ── FIELD DEFINITIONS ────────────────────────────────────────────
FIELDS = [
    {"id": 1, "name": "Classification Accuracy", "min_chars": 10},
    {"id": 2, "name": "Policy Compliance", "min_chars": 10},
    {"id": 3, "name": "Escalation Logic", "min_chars": 10},
    {"id": 4, "name": "Student Response", "min_chars": 10},
    {"id": 5, "name": "Knowledge Loop", "min_chars": 10},
    {"id": 6, "name": "Overall Tone", "min_chars": 10},
]


def evaluate(idea, results, client, model):
    """Score the workflow results with per-metric breakdown."""

    email_router_output = results.get("email_router", "{}")
    try:
        draft = json.loads(email_router_output).get("telegram_message", "No response generated")
    except Exception:
        draft = "No response generated"
        
    classifier_output = results.get("request_classifier", "No classification generated")

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    prompt = f"""You are a quality reviewer for CampusBot, an autonomous student support agent.

Review the agent's workflow execution below and score EACH metric individually.

STUDENT REQUEST: {idea}

CLASSIFIER OUTPUT:
{classifier_output}

FINAL RESPONSE:
{draft}

SCORE EACH METRIC on a 1-10 scale:

Field 1 — Classification Accuracy:
  Did the agent correctly identify if this is a lab, leave, or event query? Were key details extracted accurately?

Field 2 — Policy Compliance:
  Is the response accurate according to standard campus rules? (Assuming no hallucination).

Field 3 — Escalation Logic:
  If it requires HOD approval (like leave), did it escalate properly? If not, did it correctly decide to skip escalation?

Field 4 — Student Response:
  Is the Telegram reply clear, polite, and helpful? Does it directly answer the student?

Field 5 — Knowledge Loop:
  Are the details formatted well enough to be logged back to Google Sheets?

Field 6 — Overall Tone:
  Does the agent sound like a professional yet approachable campus assistant?

Return ONLY valid JSON — no markdown, no explanation, no extra text.
Use this exact format:
{{"overall_score": 8, "passed": true, "fields": [{{"field": 1, "name": "Classification Accuracy", "score": 8, "status": "pass", "note": "specific and clear"}}, {{"field": 2, "name": "Policy Compliance", "score": 7, "status": "pass", "note": "good"}}, {{"field": 3, "name": "Escalation Logic", "score": 6, "status": "needs_work", "note": "missing step"}}, {{"field": 4, "name": "Student Response", "score": 9, "status": "pass", "note": "polite"}}, {{"field": 5, "name": "Knowledge Loop", "score": 7, "status": "pass", "note": "loggable"}}, {{"field": 6, "name": "Overall Tone", "score": 8, "status": "pass", "note": "approachable"}}], "critique_addressed": true, "what_is_good": "strengths summary", "feedback": "specific improvements needed"}}

RULES for field status:
- score >= 7 → "pass"
- score 5-6 → "needs_work"
- score < 5 → "fail"
overall_score = average of all 6 field scores (rounded to nearest integer)"""

    # ── CALL THE LLM ─────────────────────────────────────────────
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
    )

    raw = response.choices[0].message.content

    # ── PARSE THE JSON ───────────────────────────────────────────
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    review = json.loads(raw)

    # ── ENFORCE THRESHOLD ────────────────────────────────────────
    score = review.get("overall_score", review.get("score", 0))
    review["score"] = score
    review["passed"] = score >= PASS_THRESHOLD

    return review
