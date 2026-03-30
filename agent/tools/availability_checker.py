# ============================================================
# availability_checker.py — Tool 3: Check slot/resource availability
# ============================================================
# PURPOSE:
#   Checks whether a requested lab slot or room is available by
#   querying a Google Sheets backend (or the embedded sample data
#   when running offline / without credentials).
#
# GOOGLE SHEETS INTEGRATION:
#   Set these env vars in .env:
#     SHEETS_CREDENTIALS_JSON = path to your service-account JSON file
#     SHEETS_SPREADSHEET_ID   = your spreadsheet ID from the URL
#
#   The sheet must have columns:
#     resource | date | start_time | end_time | booked_by | department | status
#
# OFFLINE FALLBACK:
#   If credentials are missing, SAMPLE_SCHEDULE (15 rows) is used.
#   This guarantees the tool works in full demo mode without any
#   external services.
# ============================================================

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


from campus import csv_loader

# OFFLINE FALLBACK:
#   If credentials are missing, csv_loader fetches lab_schedule.csv instead
#   of the deprecated SAMPLE_SCHEDULE hardcoded data.


def _fetch_from_google_sheets() -> List[Dict[str, str]]:
    """Fetch all rows from Google Sheets. Returns [] on any error."""
    if not GSPREAD_AVAILABLE:
        return []
    creds_path     = os.getenv("SHEETS_CREDENTIALS_JSON", "")
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID", "")
    if not creds_path or not spreadsheet_id:
        return []
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc    = gspread.authorize(creds)
        sh    = gc.open_by_key(spreadsheet_id)
        ws    = sh.sheet1
        return ws.get_all_records()
    except Exception:
        return []


def _parse_time(t: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    try:
        h, m = map(int, t.strip().split(":"))
        return h * 60 + m
    except Exception:
        return 0


def _times_overlap(s1: str, e1: str, s2: str, e2: str) -> bool:
    a1, b1 = _parse_time(s1), _parse_time(e1)
    a2, b2 = _parse_time(s2), _parse_time(e2)
    return a1 < b2 and a2 < b1


def _normalize(name: str) -> str:
    return name.strip().lower()


def check_availability(resource: str, date: str, start_time: str,
                       end_time: str, schedule: List[Dict[str, str]]) -> Dict[str, Any]:
    norm_resource = _normalize(resource)
    conflicts = []  # type: ignore
    free_slots = []  # type: ignore

    # Step 1: Check Timetable database constraints first
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        day_of_week = dt.strftime("%A")
    except ValueError:
        day_of_week = ""

    timetable = csv_loader.get_lab_timetable()
    for row in timetable:
        if _normalize(row.get("resource", "")) != norm_resource:
            continue
        if str(row.get("day_of_week", "")).strip().lower() != day_of_week.lower():
            continue
            
        if _times_overlap(start_time, end_time,
                          str(row.get("start_time", "")), str(row.get("end_time", ""))):
            conflicts.append({
                "resource":   str(row.get("resource", "")),
                "date":       date,
                "start_time": str(row.get("start_time", "")),
                "end_time":   str(row.get("end_time", "")),
                "booked_by":  f"Timetable: {row.get('course', '')}",
                "department": str(row.get("department", "")),
            })

    # Step 2: Check standard schedule bookings (CSV or Google Sheets)
    for row in schedule:
        if _normalize(row.get("resource", "")) != norm_resource:
            continue
        if str(row.get("date", "")).strip() != date:
            continue
        status = str(row.get("status", "")).strip().lower()
        if status == "booked":
            if _times_overlap(start_time, end_time,
                              str(row.get("start_time", "")), str(row.get("end_time", ""))):
                conflicts.append({
                    "resource":   str(row.get("resource", "")),
                    "date":       str(row.get("date", "")),
                    "start_time": str(row.get("start_time", "")),
                    "end_time":   str(row.get("end_time", "")),
                    "booked_by":  str(row.get("booked_by", "")),
                    "department": str(row.get("department", "")),
                })
        elif status == "available" or status == "free":
            free_slots.append({
                "resource":   str(row.get("resource", "")),
                "date":       str(row.get("date", "")),
                "start_time": str(row.get("start_time", "")),
                "end_time":   str(row.get("end_time", "")),
            })

    return {
        "available":           len(conflicts) == 0,
        "conflicts":           conflicts,
        "free_slots_same_day": free_slots,
    }


def _extract_booking_fields(form_output: str, classifier_output: str) -> Dict[str, str]:
    """Pull resource / date / time from form_parser or classifier JSON."""
    fields: Dict[str, str] = {
        "resource":   "",
        "date":       "",
        "start_time": "",
        "end_time":   "",
    }

    for raw in [form_output, classifier_output]:
        data: dict = {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            pass

        extracted = data.get("extracted_details", {})
        details: dict = extracted if isinstance(extracted, dict) else {}

        if not fields["resource"]:
            for key in ["resource", "equipment", "reason_or_topic", "raw_text_snippet"]:
                val = str(data.get(key) or details.get(key, ""))
                combined_candidates = csv_loader.get_lab_schedule() + csv_loader.get_lab_timetable()
                for candidate in combined_candidates:
                    if candidate.get("resource") and _normalize(candidate["resource"]) in val.lower():
                        fields["resource"] = candidate["resource"]
                        break
                if fields["resource"]:
                    break

        if not fields["date"]:
            for key in ["date", "dates_mentioned"]:
                val = str(data.get(key) or details.get(key, ""))
                if val and val not in ("none", "None", ""):
                    fields["date"] = val.strip()
                    break

    if not fields["resource"]:
        fields["resource"] = "CS Lab 1"
    if not fields["date"]:
        fields["date"] = datetime.now().strftime("%Y-%m-%d")
    if not fields["start_time"]:
        fields["start_time"] = "09:00"
    if not fields["end_time"]:
        fields["end_time"] = "11:00"

    return fields


def run(student_request: str, form_output: str, classifier_output: str,
        client: Any, model: str) -> str:
    """
    Check resource/slot availability for the student's request.

    Returns JSON string with: resource, date, start_time, end_time,
    available, status_msg, conflicts, free_slots, data_source.
    """
    schedule = _fetch_from_google_sheets()
    data_source = "google_sheets" if schedule else "csv_data"
    if not schedule:
        schedule = csv_loader.get_lab_schedule()

    fields = _extract_booking_fields(form_output, classifier_output)

    result = check_availability(
        resource=fields["resource"],
        date=fields["date"],
        start_time=fields["start_time"],
        end_time=fields["end_time"],
        schedule=schedule,
    )

    if result["available"]:
        status_msg = (
            f"\u2705 {fields['resource']} is AVAILABLE on {fields['date']} "
            f"from {fields['start_time']} to {fields['end_time']}."
        )
    else:
        conflict_summary = "; ".join(
            f"{c['start_time']}\u2013{c['end_time']} by {c['booked_by']}"
            for c in result["conflicts"]
        )
        status_msg = (
            f"\u274c CONFLICT: {fields['resource']} is already booked on "
            f"{fields['date']} ({conflict_summary})."
        )
        if result["free_slots_same_day"]:
            free = result["free_slots_same_day"][0]
            status_msg += (
                f" Alternative: {free['start_time']}\u2013{free['end_time']} is free."
            )

    output: Dict[str, Any] = {
        "resource":    fields["resource"],
        "date":        fields["date"],
        "start_time":  fields["start_time"],
        "end_time":    fields["end_time"],
        "available":   result["available"],
        "status_msg":  status_msg,
        "conflicts":   result["conflicts"],
        "free_slots":  result["free_slots_same_day"],
        "data_source": data_source,
    }

    return json.dumps(output, indent=2)
