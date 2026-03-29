# ============================================================
# request_classifier.py — Tool 1: Classify Student Request
# ============================================================
# PURPOSE:
#   This tool acts as the first step in the CampusBot pipeline.
#   It takes a raw student request (e.g., from Telegram) as input,
#   classifies the type of query (e.g., lab, leave, event), and
#   extracts the key details needed for the rest of the workflow.
#
# SYSTEM PROMPT DESIGN:
#   The prompt here is specifically designed to make the AI reason
#   correctly for campus workflows. It forces the agent to extract
#   all necessary actionable items.
# ============================================================
import json

def run(student_request, client, model):
    """Classify the student request and extract key entities using Gemini/Groq API."""

    prompt = f"""You are the Request Classifier for CampusBot, an autonomous AI agent handling student queries via Telegram.
Your role is the very first step in the system logic: understanding what the student wants so the downstream tools (Knowledge Retriever, Escalator) can act upon it.

You must analyze the incoming student request, categorize the intent, and extract necessary variables.

STUDENT REQUEST INCOMING:
"{student_request}"

INSTRUCTIONS:
1. CLASSIFY the intent into one of the designated categories:
   - "leave" (requesting time off, OD, medical leave, vacation)
   - "lab" (booking lab equipment, lab schedule, software queries)
   - "event" (hackathons, symposiums, club events)
   - "general_faq" (anything else related to campus data/circulars)

2. EXTRACT the key details based on the intent. (e.g., for leave: dates, reason. for lab: equipment name, time).

3. CHECK ESCALATION: Does this typically require HOD or faculty approval? (Leave and equipment booking almost always do).

Respond with EXACTLY valid JSON, ensuring all keys are present. Follow this schema:
{{
  "classification": {{
      "intent": "leave | lab | event | general_faq",
      "confidence_score": <float between 0.0 and 1.0>
  }},
  "extracted_details": {{
      "dates_mentioned": "<list of dates or 'none'>",
      "reason_or_topic": "<brief summary of request>",
      "urgency": "high | medium | low"
  }},
  "requires_hod_approval": <true or false>,
  "reasoning_for_downstream": "<1-2 sentences explaining why this was classified this way so the next tool understands>"
}}

Only output the raw JSON. No markdown block backticks. No explanation.
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
