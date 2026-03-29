# ============================================================
# knowledge_retriever.py — Tool 2: Query knowledge base & policies
# ============================================================
# PURPOSE:
#   Searches Google Sheets (FAQs / campus data) and parses campus
#   PDF circulars to find relevant answers for the classified query.
#   Returns a grounded answer if found, or "NOT_FOUND" to trigger
#   escalation to HOD in the next tool step.
#
# SYSTEM PROMPT DESIGN:
#   The prompt forces the agent to behave like a knowledgeable
#   campus admin — providing precise, policy-grounded answers
#   and never hallucinating when information is unavailable.
# ============================================================


def run(student_request, classifier_output, client, model):
    """Retrieve relevant campus knowledge based on the classified request."""

    prompt = f"""You are the Knowledge Retriever for CampusBot — an autonomous Telegram agent serving students at a college campus.

You receive a classified student request and must search through the campus knowledge base to find a relevant, policy-grounded answer.

STUDENT REQUEST: "{student_request}"

CLASSIFIER OUTPUT (already parsed intent):
{classifier_output}

YOUR KNOWLEDGE BASE SIMULATION (pretend you have access to):
- Google Sheets with FAQs, campus schedules, leave policies
- PDF circulars: lab schedules, event announcements, department notices

Based on the intent and details, respond in the following JSON format:
{{
  "answer_found": true or false,
  "knowledge_source": "google_sheets_faq | pdf_circular | none",
  "retrieved_answer": "<the actual policy text or FAQ answer. If none found, write 'NOT_FOUND'>",
  "relevant_policy": "<1-2 sentences about the campus rule or circular that applies>",
  "unresolved_reason": "<if answer_found is false, explain WHY it needs HOD — e.g. 'Leave requires manual approval'>"
}}

RULES:
- For leave requests: answer_found = false (always requires HOD approval). retrieved_answer = "NOT_FOUND"
- For lab queries: check if it is a schedule question (can be answered) or booking (needs approval)
- For events: general info questions can be answered; registration confirmations need escalation
- NEVER hallucinate a policy. If you're unsure, say NOT_FOUND and let the escalator handle it

Only output the raw JSON. No markdown, no extra text.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()
