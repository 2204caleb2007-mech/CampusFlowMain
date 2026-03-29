# ============================================================
# campus/policy_engine.py — Rule-Based Policy Engine
# ============================================================
# Evaluates structured request schemas against campus rules.
# Returns: APPROVED | REJECTED | ESCALATED + reason + alternatives
# ============================================================

import datetime
import random

# ── MOCK DATA (replace with real DB/API in production) ───────────

LAB_SCHEDULE: dict = {
    # lab_id -> list of booked slots {"date": "YYYY-MM-DD", "slot": "HH:MM-HH:MM"}
    "LAB204": [
        {"date": "2026-04-05", "slot": "14:00-16:00"},
        {"date": "2026-04-07", "slot": "10:00-12:00"},
    ],
    "LAB301": [],
    "LAB102": [{"date": "2026-04-10", "slot": "09:00-11:00"}],
    "LAB205": [],
}

ROOM_SCHEDULE: dict = {
    "SEMINAR_HALL_A": [{"date": "2026-04-10", "slot": "10:00-12:00"}],
    "SEMINAR_HALL_B": [],
    "CONF_ROOM_1":    [],
}

EXAM_DATES: list[str] = ["2026-04-15", "2026-04-16", "2026-04-17",
                          "2026-04-18", "2026-04-22", "2026-04-23"]

STUDENT_ATTENDANCE: dict = {
    # student_id -> attendance percentage (mock)
    "STU001": 82,
    "STU002": 65,  # below threshold
    "DEFAULT": 78,
}


def _is_exam_week(start: str, end: str) -> bool:
    """Check whether any leave date falls within exam dates."""
    try:
        s = datetime.date.fromisoformat(start)
        e = datetime.date.fromisoformat(end)
        leave_days = {
            (s + datetime.timedelta(days=i)).isoformat()
            for i in range((e - s).days + 1)
        }
        return bool(leave_days & set(EXAM_DATES))
    except Exception:
        return False


def _leave_duration(start: str, end: str) -> int:
    try:
        s = datetime.date.fromisoformat(start)
        e = datetime.date.fromisoformat(end)
        return max((e - s).days + 1, 1)
    except Exception:
        return 1


def _is_slot_booked(schedule: dict, resource_id: str, date: str, slot: str) -> bool:
    bookings = schedule.get(resource_id.upper(), [])
    return any(b["date"] == date and b["slot"] == slot for b in bookings)


def _suggest_lab_slots(lab_id: str, requested_date: str) -> list[str]:
    """Generate 3 alternative available slots near the requested date."""
    try:
        base = datetime.date.fromisoformat(requested_date)
    except Exception:
        base = datetime.date.today()
    slots = ["09:00-11:00", "11:00-13:00", "14:00-16:00", "16:00-18:00"]
    booked = LAB_SCHEDULE.get(lab_id.upper(), [])
    suggestions = []
    for delta in range(1, 8):
        candidate_date = (base + datetime.timedelta(days=delta)).isoformat()
        for slot in slots:
            if not any(b["date"] == candidate_date and b["slot"] == slot for b in booked):
                suggestions.append(f"{candidate_date} {slot}")
            if len(suggestions) >= 3:
                return suggestions
    return suggestions


# ── POLICY FUNCTIONS ─────────────────────────────────────────────

def evaluate_lab_booking(schema: dict) -> dict:
    """
    Returns:
        {"result": "APPROVED"|"REJECTED"|"ESCALATED",
         "reason": str,
         "alternatives": list[str]}
    """
    lab_id   = schema.get("lab_id", "").upper()
    date     = schema.get("date", "")
    slot     = schema.get("time_slot", "")
    student  = schema.get("student_id", "DEFAULT")

    alts = []

    if not lab_id or not date or not slot:
        return {"result": "REJECTED", "reason": "Missing lab, date, or time slot.", "alternatives": []}

    if _is_slot_booked(LAB_SCHEDULE, lab_id, date, slot):
        alts = _suggest_lab_slots(lab_id, date)
        return {
            "result": "ESCALATED",
            "reason": f"{lab_id} is already booked on {date} for {slot}. Here are 3 available alternatives.",
            "alternatives": alts,
        }

    # Simulated maintenance check
    if lab_id == "LAB999":
        return {"result": "REJECTED", "reason": f"{lab_id} is under maintenance.", "alternatives": []}

    # Auto-approve
    return {
        "result": "APPROVED",
        "reason": f"{lab_id} is available on {date} for {slot}. Booking confirmed.",
        "alternatives": [],
    }


def evaluate_leave_request(schema: dict) -> dict:
    student    = schema.get("student_id", "DEFAULT")
    start      = schema.get("start_date", "")
    end        = schema.get("end_date", schema.get("start_date", ""))
    reason     = schema.get("reason", "").lower()

    if not start:
        return {"result": "REJECTED", "reason": "No start date provided.", "alternatives": []}

    # Exam conflict
    if _is_exam_week(start, end):
        return {
            "result": "REJECTED",
            "reason": "Leave request overlaps with exam week. Exam dates cannot be taken as leave.",
            "alternatives": ["Please choose dates outside the exam schedule."],
        }

    duration = _leave_duration(start, end)
    attendance = STUDENT_ATTENDANCE.get(student, STUDENT_ATTENDANCE["DEFAULT"])

    # Attendance too low
    if attendance < 75:
        return {
            "result": "REJECTED",
            "reason": f"Your current attendance is {attendance}%. The minimum required is 75% before taking leave.",
            "alternatives": ["Improve attendance before applying for leave."],
        }

    # Long leave or medical → escalate to HOD
    if duration > 3 or "medical" in reason or "surgery" in reason or "hospital" in reason:
        return {
            "result": "ESCALATED",
            "reason": f"{duration}-day leave request has been forwarded to the HOD for approval. You will receive a response within 24 hours.",
            "alternatives": [],
        }

    # Short leave auto-approved
    return {
        "result": "APPROVED",
        "reason": f"Leave approved for {duration} day(s) from {start} to {end}. Your attendance is {attendance}%.",
        "alternatives": [],
    }


def evaluate_room_booking(schema: dict) -> dict:
    room_id   = schema.get("room_id", "").upper()
    date      = schema.get("date", "")
    slot      = schema.get("time_slot", "")
    attendees = int(schema.get("expected_attendees", 0))

    if not room_id or not date or not slot:
        return {"result": "REJECTED", "reason": "Missing room, date, or time slot.", "alternatives": []}

    # Capacity check
    CAPACITY = {"SEMINAR_HALL_A": 120, "SEMINAR_HALL_B": 80, "CONF_ROOM_1": 30}
    cap = CAPACITY.get(room_id, 50)
    if attendees > cap:
        return {
            "result": "REJECTED",
            "reason": f"{room_id} capacity is {cap}. Your event has {attendees} expected attendees.",
            "alternatives": [r for r, c in CAPACITY.items() if c >= attendees and r != room_id],
        }

    # Availability check
    if _is_slot_booked(ROOM_SCHEDULE, room_id, date, slot):
        available = [
            r for r in ROOM_SCHEDULE
            if not _is_slot_booked(ROOM_SCHEDULE, r, date, slot) and CAPACITY.get(r, 50) >= attendees
        ]
        return {
            "result": "ESCALATED",
            "reason": f"{room_id} is already booked for {date} {slot}.",
            "alternatives": available or ["No alternatives found — contact admin."],
        }

    # Large external events → escalate
    if attendees > 100:
        return {
            "result": "ESCALATED",
            "reason": f"Events with more than 100 attendees require admin approval. Forwarded.",
            "alternatives": [],
        }

    return {
        "result": "APPROVED",
        "reason": f"{room_id} booked for {date} at {slot} for {attendees} attendees.",
        "alternatives": [],
    }


def evaluate_complaint(schema: dict) -> dict:
    category    = schema.get("category", "general")
    priority    = schema.get("priority", "medium").lower()
    description = schema.get("description", "")
    location    = schema.get("location", "unspecified")

    SLA = {"high": "4 hours", "medium": "24 hours", "low": "72 hours"}
    ROUTE = {
        "high":   "Maintenance Head + Floor Supervisor",
        "medium": "Floor Supervisor",
        "low":    "Maintenance Queue",
    }

    if not description:
        return {"result": "REJECTED", "reason": "No complaint description provided.", "alternatives": []}

    # High-priority → auto-escalate
    if priority == "high":
        return {
            "result": "ESCALATED",
            "reason": f"High-priority complaint at '{location}' auto-escalated to {ROUTE['high']}. SLA: {SLA['high']}.",
            "alternatives": [],
        }

    return {
        "result": "APPROVED",
        "reason": f"Complaint logged. Routed to {ROUTE.get(priority, 'Maintenance Queue')}. SLA: {SLA.get(priority, '24 hours')}.",
        "alternatives": [],
    }


# ── UNIFIED ENTRY POINT ──────────────────────────────────────────

def evaluate(workflow_type: str, schema: dict) -> dict:
    """Route to the correct policy function."""
    dispatch = {
        "lab_booking":    evaluate_lab_booking,
        "leave_request":  evaluate_leave_request,
        "room_booking":   evaluate_room_booking,
        "complaint":      evaluate_complaint,
    }
    fn = dispatch.get(workflow_type)
    if not fn:
        return {"result": "REJECTED", "reason": f"Unknown workflow type: {workflow_type}", "alternatives": []}
    return fn(schema)
