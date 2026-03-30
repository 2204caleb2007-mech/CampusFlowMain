# ============================================================
# campus/db.py — SQLite Persistence Layer
# ============================================================
# All campus workflows, messages, logs, and audit trails are
# stored here. Replaces the JSON file system for all new data.
# Existing chat_history/ JSON sessions are still supported for
# the message display layer in main.py.
# ============================================================

import sqlite3
import os
import json
import datetime
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campusflow.db")


def get_conn() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row_factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _seed_academic_calendar():
    """Populate exam dates dynamically (current year) on first run."""
    import datetime as _dt
    year = _dt.date.today().year
    exam_dates = [
        (f"{year}-04-15", "EXAM", "Semester Exam Day 1"),
        (f"{year}-04-16", "EXAM", "Semester Exam Day 2"),
        (f"{year}-04-17", "EXAM", "Semester Exam Day 3"),
        (f"{year}-04-18", "EXAM", "Semester Exam Day 4"),
        (f"{year}-04-22", "EXAM", "Semester Exam Day 5"),
        (f"{year}-04-23", "EXAM", "Semester Exam Day 6"),
    ]
    conn = get_conn()
    now = _dt.datetime.now().isoformat()
    with conn:
        for date, etype, name in exam_dates:
            conn.execute(
                "INSERT OR IGNORE INTO academic_calendar (event_type, event_name, date, created_at) VALUES (?,?,?,?)",
                (etype, name, date, now),
            )
    conn.close()


def get_exam_dates() -> list[str]:
    """Return all exam dates from DB (replaces hardcoded EXAM_DATES list)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT date FROM academic_calendar WHERE event_type='EXAM'"
    ).fetchall()
    conn.close()
    return [r["date"] for r in rows]


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT,
            created_at  TEXT,
            role        TEXT DEFAULT 'student',
            user_id     TEXT,
            workflow_type TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            role        TEXT,
            content     TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS requests (
            id              TEXT PRIMARY KEY,
            session_id      TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            workflow_type   TEXT,
            schema_json     TEXT,
            status          TEXT DEFAULT 'pending',
            policy_result   TEXT,
            policy_reason   TEXT,
            alternatives    TEXT,
            created_at      TEXT,
            updated_at      TEXT,
            retry_count     INTEGER DEFAULT 0,
            last_attempt    TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            level       TEXT DEFAULT 'INFO',
            message     TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            actor_role  TEXT,
            action      TEXT,
            target      TEXT,
            result      TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS kpis (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT,
            workflow_type   TEXT,
            submitted_at    TEXT,
            resolved_at     TEXT,
            resolution_mins REAL,
            outcome         TEXT,
            loops_used      INTEGER
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id            TEXT PRIMARY KEY,
            resource_id   TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            date          TEXT NOT NULL,
            time_slot     TEXT NOT NULL,
            session_id    TEXT,
            status        TEXT DEFAULT 'confirmed',
            created_at    TEXT,
            expires_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS academic_calendar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT NOT NULL,
            event_name  TEXT,
            date        TEXT NOT NULL UNIQUE,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS scheduler_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name    TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            outcome     TEXT,
            detail      TEXT
        );
        """)
        
        # ── Migration: Add user_id if missing and assign old chats to admin ──
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            conn.execute("UPDATE sessions SET user_id='admin' WHERE user_id IS NULL")
        except sqlite3.OperationalError:
            pass # Column already exists
            
    conn.close()
    _seed_academic_calendar()


# ── SESSION CRUD ─────────────────────────────────────────────────

def create_session(session_id: str, title: str, role: str = "student",
                   workflow_type: str = "", user_id: str = "") -> None:
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, title, created_at, role, user_id, workflow_type) VALUES (?,?,?,?,?,?)",
            (session_id, title, now, role, user_id, workflow_type)
        )
    conn.close()


def list_sessions(user_id: str = None, role: str = None) -> list[dict]:
    """Retrieve chat sessions via user access rules."""
    conn = get_conn()
    
    if role == "admin":
        # Admin sees everything
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    elif user_id:
        # Others see only their own sessions
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY created_at DESC", 
            (user_id,)
        ).fetchall()
    else:
        # Fallback
        rows = []
        
    conn.close()
    return [dict(r) for r in rows]


def get_session(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(session_id: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.close()


def rename_session(session_id: str, new_title: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("UPDATE sessions SET title=? WHERE id=?", (new_title[:40], session_id))
    conn.close()


# ── MESSAGE CRUD ─────────────────────────────────────────────────

def add_message(session_id: str, role: str, content: str) -> None:
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, now)
        )
    conn.close()


def get_messages(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── REQUEST CRUD ─────────────────────────────────────────────────

def create_request(session_id: str, workflow_type: str, schema: dict) -> str:
    req_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO requests
               (id, session_id, workflow_type, schema_json, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (req_id, session_id, workflow_type, json.dumps(schema), "pending", now, now)
        )
    conn.close()
    return req_id


def update_request_status(req_id: str, status: str, policy_result: str = "",
                          policy_reason: str = "", alternatives: list = None) -> None:
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """UPDATE requests
               SET status=?, policy_result=?, policy_reason=?, alternatives=?, updated_at=?
               WHERE id=?""",
            (status, policy_result, policy_reason,
             json.dumps(alternatives or []), now, req_id)
        )
    conn.close()


def get_request(req_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_session_requests(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM requests WHERE session_id=? ORDER BY created_at",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── LOG CRUD ─────────────────────────────────────────────────────

def add_log(session_id: str, message: str, level: str = "INFO") -> None:
    now = datetime.datetime.now().strftime("%H:%M:%S")
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO logs (session_id, level, message, created_at) VALUES (?,?,?,?)",
            (session_id, level, f"[{now}] {message}", now)
        )
    conn.close()


def get_logs(session_id: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT message FROM logs WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return [r["message"] for r in rows]


# ── AUDIT CRUD ───────────────────────────────────────────────────

def add_audit(session_id: str, actor_role: str, action: str,
              target: str, result: str) -> None:
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO audit (session_id, actor_role, action, target, result, created_at) VALUES (?,?,?,?,?,?)",
            (session_id, actor_role, action, target, result, now)
        )
    conn.close()


# ── KPI TRACKING ─────────────────────────────────────────────────

def record_kpi(session_id: str, workflow_type: str,
               submitted_at: str, outcome: str, loops_used: int) -> None:
    resolved_at = datetime.datetime.now().isoformat()
    try:
        s = datetime.datetime.fromisoformat(submitted_at)
        r = datetime.datetime.fromisoformat(resolved_at)
        mins = (r - s).total_seconds() / 60
    except Exception:
        mins = 0.0
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO kpis
               (session_id, workflow_type, submitted_at, resolved_at, resolution_mins, outcome, loops_used)
               VALUES (?,?,?,?,?,?,?)""",
            (session_id, workflow_type, submitted_at, resolved_at, mins, outcome, loops_used)
        )
    conn.close()


def get_kpi_summary() -> dict:
    """Aggregate KPI stats across all sessions."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM kpis").fetchall()
    conn.close()
    if not rows:
        return {}
    total = len(rows)
    resolved = sum(1 for r in rows if r["outcome"] in ("approved", "resolved"))
    avg_mins = sum(r["resolution_mins"] for r in rows) / total if total else 0
    by_type: dict = {}
    for r in rows:
        wt = r["workflow_type"]
        by_type.setdefault(wt, {"total": 0, "resolved": 0})
        by_type[wt]["total"] += 1
        if r["outcome"] in ("approved", "resolved"):
            by_type[wt]["resolved"] += 1
    return {
        "total_requests": total,
        "resolved": resolved,
        "resolution_rate_pct": round(resolved / total * 100, 1) if total else 0,
        "avg_resolution_mins": round(avg_mins, 1),
        "by_workflow": by_type,
    }


# ── BOOKING CRUD (persistent, replaces in-memory dicts) ──────────

def is_slot_booked(resource_id: str, date: str, time_slot: str) -> bool:
    """Check DB for a confirmed booking collision."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM bookings WHERE resource_id=? AND date=? AND time_slot=? AND status='confirmed'",
        (resource_id.upper(), date, time_slot),
    ).fetchone()
    conn.close()
    return row is not None


def create_booking(resource_id: str, resource_type: str, date: str,
                   time_slot: str, session_id: str = "") -> str:
    """Persist a confirmed booking. Returns booking id."""
    import uuid as _uuid
    bid = str(_uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    # Bookings expire after 24h for lab/room; extend if needed
    expires = (datetime.datetime.now() + datetime.timedelta(hours=24)).isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO bookings
               (id, resource_id, resource_type, date, time_slot, session_id, status, created_at, expires_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (bid, resource_id.upper(), resource_type, date, time_slot, session_id, "confirmed", now, expires),
        )
    conn.close()
    return bid


def expire_old_bookings() -> int:
    """Mark bookings past their expires_at as expired. Returns count changed."""
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    cur = conn.execute(
        "UPDATE bookings SET status='expired' WHERE expires_at < ? AND status='confirmed'", (now,)
    )
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


# ── RETRY CRUD (structured — no string parsing) ───────────────────

def increment_retry(req_id: str) -> int:
    """Bump retry_count and last_attempt. Returns new retry count."""
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE requests SET retry_count = retry_count + 1, last_attempt=?, status='pending' WHERE id=?",
        (now, req_id),
    )
    row = conn.execute("SELECT retry_count FROM requests WHERE id=?", (req_id,)).fetchone()
    conn.commit()
    conn.close()
    return row["retry_count"] if row else 0


# ── SCHEDULER LOG ──────────────────────────────────────────────────

def log_scheduler_job(job_name: str, outcome: str, detail: str = "") -> None:
    """Write a structured scheduler job log entry."""
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO scheduler_logs (job_name, executed_at, outcome, detail) VALUES (?,?,?,?)",
            (job_name, now, outcome, detail),
        )
    conn.close()


def get_scheduler_logs(limit: int = 50) -> list[dict]:
    """Return recent scheduler log entries for UI display."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM scheduler_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── INIT ON IMPORT ───────────────────────────────────────────────
init_db()
