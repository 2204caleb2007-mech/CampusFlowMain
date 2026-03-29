# ============================================================
# campus/classifier.py — LLM-Powered Request Classifier
# ============================================================
# Classifies free-text student input into a structured schema
# for one of the 4 supported workflows.
# Falls back to keyword matching if LLM is unavailable.
# Supports role-aware response generation.
# ============================================================

import json
import re
from campus import role_system

WORKFLOW_TYPES = ["lab_booking", "leave_request", "room_booking", "complaint", "web_search"]

CLASSIFIER_PROMPT_BASE = """
Analyze the request message and extract a structured JSON schema.

Classify into one of these workflows:
- lab_booking: student wants to book a computer/electronics/physics/CAD/software lab
- leave_request: student wants leave, medical, emergency, holiday, sick day
- room_booking: student wants to book a seminar hall, conference room, event space
- complaint: student reporting an issue, maintenance problem, facility complaint
- web_search: student asking an academic doubt, subject question, general knowledge, or internet query

Return ONLY valid JSON with this structure:

For lab_booking:
{"type":"lab_booking","student_id":"STU001","lab_id":"LAB204","date":"YYYY-MM-DD","time_slot":"HH:MM-HH:MM","purpose":"","course_code":""}

For leave_request:
{"type":"leave_request","student_id":"STU001","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","reason":"","requires_hod":false}

For room_booking:
{"type":"room_booking","organizer_id":"STU001","room_id":"SEMINAR_HALL_A","date":"YYYY-MM-DD","time_slot":"HH:MM-HH:MM","event_name":"","expected_attendees":30}

For complaint:
{"type":"complaint","student_id":"STU001","category":"maintenance","location":"","description":"","priority":"medium","sla_hours":24}

For web_search:
{"type":"web_search","query":"<the exact question to search for>"}

Extract all values you can from the message. Use sensible defaults for missing fields.
Set priority: "high" if urgent/dangerous/no power/flooding, "medium" for normal issues, "low" for minor inconveniences.
For lab_booking, infer lab_id from context: CS/computer→LAB204, electronics→LAB301, physics→LAB102, CAD/design→LAB303, software→LAB205.
For room_booking, infer room_id: seminar/large→SEMINAR_HALL_A, conference/small meeting→CONF_ROOM_1.
If today's date context is needed, use 2026-04-01 as reference.
Return ONLY the JSON object. No extra text.
""".strip()


def classify_with_llm(text: str, client, model: str, role: str = "student") -> dict:
    """Use Groq LLM to extract a structured schema from free text.
    
    Args:
        text: The user's query text
        client: Groq client instance
        model: The LLM model to use
        role: The current user role (affects system prompt)
    
    Returns:
        A structured schema dictionary
    """
    try:
        # Build role-aware system prompt by injecting role context
        role_prompt = role_system.get_role_system_prompt(role, {"workflow_type": "classification"})
        full_system_prompt = f"""{role_prompt}

{CLASSIFIER_PROMPT_BASE}"""
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        schema = json.loads(raw)
        return schema
    except Exception as e:
        return _keyword_fallback(text)


def _keyword_fallback(text: str) -> dict:
    """Simple keyword-based classifier as a fallback."""
    t = text.lower()

    # Lab booking keywords
    if any(k in t for k in ["lab", "book", "slot", "computer lab", "electronics lab",
                              "physics lab", "cad lab", "software lab"]):
        lab_id = "LAB204"
        if "electronic" in t or "301" in t:
            lab_id = "LAB301"
        elif "physic" in t or "102" in t:
            lab_id = "LAB102"
        elif "cad" in t or "design" in t or "303" in t:
            lab_id = "LAB303"
        elif "software" in t or "205" in t:
            lab_id = "LAB205"
        return {
            "type": "lab_booking",
            "student_id": "STU001",
            "lab_id": lab_id,
            "date": "2026-04-05",
            "time_slot": "14:00-16:00",
            "purpose": "extracted from query",
            "course_code": "",
        }

    # Leave/medical keywords
    if any(k in t for k in ["leave", "sick", "medical", "fever", "hospital",
                              "emergency", "holiday", "absent", "attendance"]):
        return {
            "type": "leave_request",
            "student_id": "STU001",
            "start_date": "2026-04-05",
            "end_date": "2026-04-05",
            "reason": "personal",
            "requires_hod": False,
        }

    # Room booking keywords
    if any(k in t for k in ["seminar", "hall", "conference", "room", "event",
                              "auditorium", "meeting room"]):
        return {
            "type": "room_booking",
            "organizer_id": "STU001",
            "room_id": "SEMINAR_HALL_A",
            "date": "2026-04-10",
            "time_slot": "10:00-12:00",
            "event_name": "event",
            "expected_attendees": 30,
        }

    # Complaint keywords
    if any(k in t for k in ["complaint", "broken", "not working", "damaged",
                              "maintenance", "ac", "fan", "light", "flood",
                              "power", "electricity", "projector", "wifi"]):
        priority = "medium"
        if any(k in t for k in ["urgent", "dangerous", "flood", "fire",
                                  "no power", "electrical", "emergency"]):
            priority = "high"
        elif any(k in t for k in ["minor", "small", "tiny"]):
            priority = "low"
        return {
            "type": "complaint",
            "student_id": "STU001",
            "category": "maintenance",
            "location": "unspecified",
            "description": text,
            "priority": priority,
            "sla_hours": {"high": 4, "medium": 24, "low": 72}.get(priority, 24),
        }

    # If it asks a question (how to, what is, explain, etc. or ends with ?)
    if "?" in t or any(k in t for k in ["what", "how", "explain", "who", "why", "define", "difference"]):
        return {
            "type": "web_search",
            "query": text
        }

    # Unknown — default to web search for general conversational queries
    return {
        "type": "web_search",
        "query": text
    }


def classify(text: str, client=None, model: str = "", role: str = "student") -> dict:
    """
    Classify student input into a workflow schema.
    Uses LLM if client is provided, else falls back to keywords.
    
    Args:
        text: The user's query text
        client: Groq client instance (optional)
        model: The LLM model to use (optional)
        role: The current user role (affects response tone)
    
    Returns:
        A structured schema dictionary
    """
    if client and model:
        return classify_with_llm(text, client, model, role)
    return _keyword_fallback(text)
