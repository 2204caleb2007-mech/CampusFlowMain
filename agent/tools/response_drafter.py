# ============================================================
# response_drafter.py — Tool 4: Draft Telegram Reply + Log to KB
# ============================================================
# PURPOSE:
#   The final step in the CampusBot pipeline. This tool:
#     1. Drafts a clear, friendly Telegram response to the student
#     2. Generates a knowledge base log entry (Q&A pair) for Google Sheets
#        so the agent self-learns from every conversation
#
# SYSTEM PROMPT DESIGN:
#   The reply must be warm, campus-appropriate, concise, and tell the
#   student exactly what has happened (answered, escalated, pending).
#   The KB log enables the self-learning loop described in the architecture.
# ============================================================


def run(student_request, classifier_output, knowledge_output, escalator_output, client, model):
    """Draft the final Telegram reply to the student and the KB log entry."""

    prompt = f"""You are the Response Drafter for CampusBot — the final step of an autonomous student support system.

You receive all outputs from the previous 3 tools and must:
1. Draft a concise, helpful Telegram message for the student
2. Generate a knowledge base log entry so this Q&A can be stored in Google Sheets for future learning

STUDENT REQUEST: "{student_request}"

CLASSIFIER OUTPUT:
{classifier_output}

KNOWLEDGE RETRIEVER OUTPUT:
{knowledge_output}

HOD ESCALATOR OUTPUT:
{escalator_output}

TELEGRAM REPLY RULES:
- Be warm, friendly, and campus-appropriate
- Use simple markdown (bold with * for Telegram — avoid HTML)
- If resolved: give the answer directly
- If escalated: tell the student that their request has been forwarded to the HOD with expected timeline
- Never say "I don't know" — either answer or inform about escalation status
- Keep it under 200 words

KNOWLEDGE BASE LOG RULES:
- Format it as a simple one-line Q&A pair that could be stored in a spreadsheet
- Pattern: "Q: <student question> | A: <resolved answer or 'Escalated to HOD'>"
- This is what makes the bot self-learning

Return ONLY this exact valid JSON:
{{
  "telegram_reply": "<the full Telegram message to send to the student>",
  "knowledge_base_log": {{
    "question": "<cleaned version of student query>",
    "answer": "<final answer or 'Escalated to HOD for manual approval'>",
    "category": "<leave | lab | event | general_faq>",
    "timestamp": "auto"
  }},
  "workflow_summary": "<1-2 sentence summary of how this query was handled by the agent>"
}}

Only output raw JSON. No markdown block. No extra text.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()
