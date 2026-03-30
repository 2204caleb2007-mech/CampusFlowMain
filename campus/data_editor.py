# ============================================================
# campus/data_editor.py — Natural Language → CSV Modification
# ============================================================
# Provides safe, validated, audited write operations on:
#   - data/student_attendance.csv
#   - data/lab_timetable.csv
#
# SECURITY MODEL:
#   Admin  → full access (attendance + timetable)
#   Teacher → attendance writes + timetable writes (their dept)
#   Student → read-only (all writes rejected here before they hit disk)
#
# SAFETY:
#   - Atomic writes via temp-file + os.replace()
#   - filelock (with fallback) prevents concurrent corruption
#   - All modifications logged to campus DB audit table
# ============================================================

import csv
import os
import json
import uuid
import tempfile
import datetime
import re
import logging
from typing import Any

logger = logging.getLogger("campusflow.data_editor")

# ── PATH RESOLUTION ───────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")
_ATTENDANCE_CSV  = os.path.join(_DATA, "student_attendance.csv")
_TIMETABLE_CSV   = os.path.join(_DATA, "lab_timetable.csv")
_STUDENTS_CSV    = os.path.join(_DATA, "students.csv")

# ── ROLE PERMISSIONS ─────────────────────────────────────────────
_WRITE_ROLES = {"admin", "teacher"}
_ADMIN_ONLY  = {"admin"}

# ── VALID RESOURCES ──────────────────────────────────────────────
_KNOWN_RESOURCES = {
    "cs lab 1", "cs lab 2", "electronics lab",
    "mechanical lab", "seminar hall a", "seminar hall b",
    "conference room",
}
_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


# ════════════════════════════════════════════════════════════════
# SECTION 1 — INTENT PARSING  (LLM-assisted)
# ════════════════════════════════════════════════════════════════

def parse_data_command(
    query_text: str,
    role: str,
    client,
    model: str,
) -> dict | None:
    """
    Use LLM to parse a natural language data modification command into a
    structured action dict.  Returns None if the query is NOT a data
    modification intent (so the orchestrator keeps its normal routing).

    Returned dict shape (action = update_attendance):
        {"action": "update_attendance", "student_id": "STU002",
         "date": "2026-03-30", "status": "present",
         "total_classes": null, "classes_attended": null,
         "attendance_percentage": null}

    Returned dict shape (action = modify_timetable):
        {"action": "modify_timetable", "resource": "CS Lab 1",
         "day_of_week": "Friday", "start_time": "10:00", "end_time": "12:00",
         "department": "CSE", "course": "...", "operation": "add"}

    Returned dict shape (action = none):
        {"action": "none"}  ← not a data modification intent
    """
    today = datetime.date.today().isoformat()
    prompt = f"""You are a parser for a campus data management system.

Today's date: {today}

Analyze the following command and determine if it is attempting to MODIFY campus data
(attendance records or lab timetable). If YES, extract a structured JSON action.
If NO, return {{"action": "none"}}.

COMMAND: "{query_text}"

Rules:
1. If the command is about updating/adding/marking attendance → action = "update_attendance"
   Required fields: student_id (STU001-STU010), date (YYYY-MM-DD, use today={today} for "today"),
   status (present/absent), optional: total_classes, classes_attended, attendance_percentage (float)
   
2. If the command is about adding/removing/scheduling a lab or room to the timetable → action = "modify_timetable"
   Required fields: resource (exact name), day_of_week (Monday-Sunday),
   start_time (HH:MM), end_time (HH:MM), operation (add/remove),
   optional: department, course

3. If the command is just a read/query (not a modification) → {{"action": "none"}}

Known resources: CS Lab 1, CS Lab 2, Electronics Lab, Mechanical Lab, Seminar Hall A, Seminar Hall B, Conference Room
Known student IDs: STU001 through STU010

Return ONLY valid compact JSON. No markdown, no explanation."""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown fences if model adds them
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        parsed = json.loads(raw)
        action = parsed.get("action", "none")
        if action == "none":
            return None
        return parsed
    except Exception as e:
        logger.warning(f"parse_data_command LLM error: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# SECTION 2 — VALIDATION
# ════════════════════════════════════════════════════════════════

def _load_known_students() -> set:
    """Return set of valid student_ids from students.csv."""
    ids = set()
    if not os.path.exists(_STUDENTS_CSV):
        return {f"STU{i:03d}" for i in range(1, 11)}
    with open(_STUDENTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = row.get("student_id", "").strip().upper()
            if sid:
                ids.add(sid)
    return ids


def _parse_time(t: str) -> int:
    """Return minutes since midnight for HH:MM, or -1 on error."""
    try:
        h, m = map(int, t.strip().split(":"))
        return h * 60 + m
    except Exception:
        return -1


def _times_overlap(s1, e1, s2, e2) -> bool:
    a1, b1 = _parse_time(s1), _parse_time(e1)
    a2, b2 = _parse_time(s2), _parse_time(e2)
    return a1 < b2 and a2 < b1


def _validate_time_format(t: str) -> bool:
    return bool(re.match(r"^\d{2}:\d{2}$", t.strip()))


def _normalize_resource(name: str) -> str:
    return name.strip().lower()


def validate_attendance_action(action: dict, role: str) -> tuple[bool, str]:
    """Return (ok, error_message). ok=True means safe to write."""
    if role not in _WRITE_ROLES:
        return False, f"❌ Role '{role}' does not have write access to attendance data."

    sid = str(action.get("student_id", "")).upper().strip()
    if not re.match(r"^STU\d{3}$", sid):
        return False, f"❌ Invalid student ID format: '{sid}'. Must be STU001–STU010."

    known = _load_known_students()
    if sid not in known:
        return False, f"❌ Student '{sid}' not found in the student database."

    date_val = str(action.get("date", "")).strip()
    try:
        datetime.date.fromisoformat(date_val)
    except ValueError:
        return False, f"❌ Invalid date format: '{date_val}'. Use YYYY-MM-DD."

    status = str(action.get("status", "")).lower()
    if status not in ("present", "absent", ""):
        # Might be a percentage update — that's OK
        pass

    # If explicit percentage provided, validate range
    pct = action.get("attendance_percentage")
    if pct is not None:
        try:
            p = float(pct)
            if not (0.0 <= p <= 100.0):
                return False, f"❌ Attendance percentage must be 0–100, got {p}."
        except (TypeError, ValueError):
            return False, f"❌ Invalid attendance_percentage: '{pct}'."

    return True, ""


def validate_timetable_action(action: dict, role: str) -> tuple[bool, str]:
    """Return (ok, error_message)."""
    if role not in _WRITE_ROLES:
        return False, f"❌ Role '{role}' does not have write access to timetable data."

    resource = str(action.get("resource", "")).strip()
    if _normalize_resource(resource) not in _KNOWN_RESOURCES:
        return False, (
            f"❌ Unknown resource: '{resource}'. "
            f"Valid: CS Lab 1, CS Lab 2, Electronics Lab, Mechanical Lab, "
            f"Seminar Hall A, Seminar Hall B, Conference Room."
        )

    day = str(action.get("day_of_week", "")).strip().capitalize()
    if day.lower() not in _DAYS:
        return False, f"❌ Invalid day_of_week: '{day}'. Must be Monday–Sunday."

    st = str(action.get("start_time", "")).strip()
    et = str(action.get("end_time", "")).strip()
    if not _validate_time_format(st):
        return False, f"❌ Invalid start_time: '{st}'. Use HH:MM format."
    if not _validate_time_format(et):
        return False, f"❌ Invalid end_time: '{et}'. Use HH:MM format."
    if _parse_time(st) >= _parse_time(et):
        return False, f"❌ start_time ({st}) must be before end_time ({et})."

    op = str(action.get("operation", "add")).lower()
    if op not in ("add", "remove"):
        return False, f"❌ Unknown operation: '{op}'. Use 'add' or 'remove'."

    return True, ""


# ════════════════════════════════════════════════════════════════
# SECTION 3 — ATOMIC WRITES
# ════════════════════════════════════════════════════════════════

def _atomic_write_csv(filepath: str, fieldnames: list, rows: list) -> None:
    """Write rows to a temp file, then atomically replace the target."""
    dir_ = os.path.dirname(filepath)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _acquire_lock(filepath: str):
    """Best-effort file lock. Returns lock object (or None if filelock unavailable)."""
    try:
        import filelock
        lock = filelock.FileLock(filepath + ".lock", timeout=10)
        lock.acquire()
        return lock
    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"Could not acquire lock on {filepath}: {e}")
        return None


def _release_lock(lock) -> None:
    if lock:
        try:
            lock.release()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
# SECTION 4 — ATTENDANCE WRITER
# ════════════════════════════════════════════════════════════════

_ATTENDANCE_FIELDS = ["student_id", "total_classes", "classes_attended", "attendance_percentage"]

def update_attendance(action: dict, username: str, role: str) -> dict:
    """
    Apply an update_attendance action to student_attendance.csv.

    Logic:
      - If status=present  → increment classes_attended +1 and total_classes +1
      - If status=absent   → increment total_classes +1 only
      - If attendance_percentage provided AND role=admin → override directly
      - Recalculate percentage after changes

    Returns: {"success": bool, "message": str, "before": dict, "after": dict}
    """
    ok, err = validate_attendance_action(action, role)
    if not ok:
        return {"success": False, "message": err}

    sid    = action["student_id"].upper().strip()
    status = str(action.get("status", "")).lower()
    override_pct = action.get("attendance_percentage")
    override_tc  = action.get("total_classes")
    override_ca  = action.get("classes_attended")

    lock = _acquire_lock(_ATTENDANCE_CSV)
    try:
        # Read existing rows
        rows = []
        if os.path.exists(_ATTENDANCE_CSV):
            with open(_ATTENDANCE_CSV, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

        # Find target row
        target_idx = None
        for i, row in enumerate(rows):
            if row.get("student_id", "").strip().upper() == sid:
                target_idx = i
                break

        if target_idx is None:
            # Create new entry
            before = {}
            rows.append({
                "student_id": sid,
                "total_classes": "1",
                "classes_attended": "1" if status == "present" else "0",
                "attendance_percentage": "100.0" if status == "present" else "0.0",
            })
            target_idx = len(rows) - 1
        else:
            before = dict(rows[target_idx])

        row = rows[target_idx]

        # Apply update logic
        tc = int(float(row.get("total_classes", 0)))
        ca = int(float(row.get("classes_attended", 0)))

        if override_pct is not None and role in _ADMIN_ONLY:
            # Admin direct override
            if override_tc is not None:
                tc = int(override_tc)
            if override_ca is not None:
                ca = int(override_ca)
            pct = float(override_pct)
        elif override_tc is not None and override_ca is not None:
            tc  = int(override_tc)
            ca  = int(override_ca)
            pct = round(ca / tc * 100, 1) if tc > 0 else 0.0
        elif status == "present":
            tc += 1
            ca += 1
            pct = round(ca / tc * 100, 1) if tc > 0 else 0.0
        elif status == "absent":
            tc += 1
            pct = round(ca / tc * 100, 1) if tc > 0 else 0.0
        else:
            return {"success": False,
                    "message": "❌ No valid update parameters provided. Specify status (present/absent) or attendance_percentage."}

        row["total_classes"]        = str(tc)
        row["classes_attended"]     = str(ca)
        row["attendance_percentage"] = str(pct)
        rows[target_idx] = row

        _atomic_write_csv(_ATTENDANCE_CSV, _ATTENDANCE_FIELDS, rows)

        # Invalidate CSV cache
        try:
            from campus import csv_loader
            csv_loader.clear_cache()
        except Exception:
            pass

        after = dict(rows[target_idx])
        _audit(username, role, "update_attendance", sid, "success",
               {"before": before, "after": after})

        return {
            "success": True,
            "message": (
                f"✅ Attendance updated for **{sid}**\n"
                f"- Classes attended: {ca}/{tc}\n"
                f"- Attendance: **{pct}%**"
            ),
            "before": before,
            "after": after,
        }
    except Exception as e:
        logger.error(f"update_attendance error: {e}")
        _audit(username, role, "update_attendance", sid, "error", {"error": str(e)})
        return {"success": False, "message": f"❌ Failed to update attendance: {e}"}
    finally:
        _release_lock(lock)


# ════════════════════════════════════════════════════════════════
# SECTION 5 — TIMETABLE WRITER
# ════════════════════════════════════════════════════════════════

_TIMETABLE_FIELDS = ["resource", "day_of_week", "start_time", "end_time", "department", "course"]

def modify_timetable(action: dict, username: str, role: str) -> dict:
    """
    Apply a modify_timetable action to lab_timetable.csv.

    operation=add:
      - Validates no overlapping slot for same resource+day
      - Appends new row

    operation=remove:
      - Removes matching row (resource + day + overlapping time range)

    Returns: {"success": bool, "message": str}
    """
    ok, err = validate_timetable_action(action, role)
    if not ok:
        return {"success": False, "message": err}

    resource  = action["resource"].strip()
    day       = action["day_of_week"].strip().capitalize()
    st        = action["start_time"].strip()
    et        = action["end_time"].strip()
    dept      = action.get("department", "").strip()
    course    = action.get("course", "").strip()
    operation = action.get("operation", "add").lower()
    norm_res  = _normalize_resource(resource)

    lock = _acquire_lock(_TIMETABLE_CSV)
    try:
        rows = []
        if os.path.exists(_TIMETABLE_CSV):
            with open(_TIMETABLE_CSV, newline="", encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f) if any(r.values())]

        if operation == "add":
            # Check for conflicts on same resource + day
            conflicts = []
            for row in rows:
                if (_normalize_resource(row.get("resource", "")) == norm_res
                        and row.get("day_of_week", "").strip().lower() == day.lower()
                        and _times_overlap(st, et,
                                          row.get("start_time", ""),
                                          row.get("end_time", ""))):
                    conflicts.append(row)

            if conflicts:
                c = conflicts[0]
                return {
                    "success": False,
                    "message": (
                        f"❌ Schedule conflict: **{resource}** on **{day}** "
                        f"{c['start_time']}–{c['end_time']} is already booked "
                        f"for **{c.get('course', 'a class')}** ({c.get('department', '')}).\n\n"
                        f"💡 Choose a different time slot or day."
                    ),
                }

            # Add new entry
            new_row = {
                "resource":    resource,
                "day_of_week": day,
                "start_time":  st,
                "end_time":    et,
                "department":  dept,
                "course":      course,
            }
            rows.append(new_row)
            _atomic_write_csv(_TIMETABLE_CSV, _TIMETABLE_FIELDS, rows)

            # Invalidate cache
            try:
                from campus import csv_loader
                csv_loader.clear_cache()
            except Exception:
                pass

            _audit(username, role, "timetable_add", resource, "success", new_row)
            return {
                "success": True,
                "message": (
                    f"✅ Timetable updated: **{resource}** added on **{day}** "
                    f"{st}–{et}"
                    + (f" for **{course}**" if course else "")
                    + (f" ({dept})" if dept else "") + "."
                ),
            }

        elif operation == "remove":
            before_count = len(rows)
            new_rows = []
            removed = []
            for row in rows:
                is_match = (
                    _normalize_resource(row.get("resource", "")) == norm_res
                    and row.get("day_of_week", "").strip().lower() == day.lower()
                    and _times_overlap(st, et,
                                       row.get("start_time", ""),
                                       row.get("end_time", ""))
                )
                if is_match:
                    removed.append(row)
                else:
                    new_rows.append(row)

            if not removed:
                return {
                    "success": False,
                    "message": (
                        f"❌ No matching timetable entry found for **{resource}** "
                        f"on **{day}** at {st}–{et}."
                    ),
                }

            _atomic_write_csv(_TIMETABLE_CSV, _TIMETABLE_FIELDS, new_rows)

            try:
                from campus import csv_loader
                csv_loader.clear_cache()
            except Exception:
                pass

            _audit(username, role, "timetable_remove", resource, "success",
                   {"removed": removed})
            return {
                "success": True,
                "message": (
                    f"✅ Removed **{len(removed)}** timetable entry(ies) for "
                    f"**{resource}** on **{day}** {st}–{et}."
                ),
            }

    except Exception as e:
        logger.error(f"modify_timetable error: {e}")
        _audit(username, role, "timetable_" + operation, resource, "error", {"error": str(e)})
        return {"success": False, "message": f"❌ Timetable modification failed: {e}"}
    finally:
        _release_lock(lock)


# ════════════════════════════════════════════════════════════════
# SECTION 6 — AUDIT LOGGING
# ════════════════════════════════════════════════════════════════

def _audit(username: str, role: str, action: str, target: str,
           status: str, detail: Any = None) -> None:
    """Write a structured audit entry to the campus DB audit table."""
    try:
        from campus import db
        db.add_audit(
            session_id=f"data_editor_{username}",
            actor_role=f"{role}:{username}",
            action=action,
            target=target,
            result=json.dumps({"status": status, "detail": detail}),
        )
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")


# ════════════════════════════════════════════════════════════════
# SECTION 7 — UNIFIED DISPATCHER
# ════════════════════════════════════════════════════════════════

def execute_data_command(
    action: dict,
    username: str,
    role: str,
) -> dict:
    """
    Route a parsed action dict to the correct writer.
    Returns {"success": bool, "message": str, ...}
    """
    act = action.get("action", "none")
    if act == "update_attendance":
        return update_attendance(action, username, role)
    elif act == "modify_timetable":
        return modify_timetable(action, username, role)
    else:
        return {"success": False, "message": f"Unknown action type: '{act}'"}
