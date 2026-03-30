# ============================================================
# scheduler/jobs.py — Background APScheduler (Singleton)
# ============================================================
# Runs fully independently of Streamlit's user-triggered flow.
# Uses MODULE-LEVEL singleton to prevent duplicate threads on reruns.
# All jobs use structured DB logging (not string parsing).
# ============================================================

import datetime
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from campus import db

# ── FILE LOGGER (separate file, non-intrusive) ─────────────────────
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scheduler_jobs.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("campusflow.scheduler")

# ── SHARED UI STATUS STORE ─────────────────────────────────────────
# Module-level dict — safe since scheduler runs in a single background thread.
JOB_STATUS: dict = {
    "sla_monitor":  {"last_run": None, "result": "—"},
    "retry_failed": {"last_run": None, "result": "—"},
    "health_log":   {"last_run": None, "result": "—"},
    "data_sync":    {"last_run": None, "result": "—"},
    "booking_cleanup": {"last_run": None, "result": "—"},
}

# SLA thresholds in minutes per workflow type
SLA_THRESHOLDS = {
    "lab_booking":   30,
    "leave_request": 60,
    "room_booking":  30,
    "complaint":     240,
}

MAX_RETRY = 3


# ── HELPERS ────────────────────────────────────────────────────────

def _update_status(job_name: str, result: str):
    """Update shared UI status and write structured DB log."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    JOB_STATUS[job_name] = {"last_run": ts, "result": result}
    try:
        db.log_scheduler_job(job_name, "success", result)
    except Exception:
        pass
    logger.info(f"[{job_name}] {result}")


def _notify_sla_breach(req_id: str, workflow_type: str, age_mins: float):
    """Send SLA breach notification via Formspree to admin + student, and audit log."""
    msg = (
        f"⚠️ SLA BREACH — {workflow_type.replace('_', ' ').title()} "
        f"(req_id={req_id[:8]}…) exceeded threshold by {age_mins:.0f} min. "
        f"Auto-escalated."
    )
    logger.warning(msg)

    # Write to audit log so admins can see it in the UI
    try:
        db.add_audit(
            session_id="scheduler",
            actor_role="scheduler",
            action="sla_escalate",
            target=req_id,
            result=msg,
        )
    except Exception:
        pass

    # Send dual Formspree notification (admin + student)
    try:
        from campus import notifier as _notifier
        schema = {"request_id": req_id, "sla_breach": f"{age_mins:.0f} min elapsed"}
        policy = {
            "result": "ESCALATED",
            "reason": msg,
            "alternatives": ["Please review immediately."],
        }
        _notifier.notify(workflow_type, schema, policy, role="scheduler")
    except Exception as notify_err:
        logger.warning(f"SLA breach notifier failed: {notify_err}")


# ── JOB 1: SLA MONITORING ─────────────────────────────────────────
def job_sla_monitor():
    """
    Runs every 5 minutes.
    Finds pending requests exceeding their SLA → escalates in DB + notifies.
    Idempotent: only escalates requests still in 'pending' status.
    """
    job_name = "sla_monitor"
    try:
        conn = db.get_conn()
        now = datetime.datetime.now()
        pending_rows = conn.execute(
            "SELECT id, workflow_type, created_at, status FROM requests WHERE status='pending'"
        ).fetchall()
        escalated_count = 0

        for row in pending_rows:
            wt = row["workflow_type"]
            threshold = SLA_THRESHOLDS.get(wt, 60)
            try:
                created = datetime.datetime.fromisoformat(row["created_at"])
                age_mins = (now - created).total_seconds() / 60
                if age_mins > threshold:
                    conn.execute(
                        """UPDATE requests
                           SET status='escalated', policy_result='ESCALATED',
                               policy_reason=?, updated_at=?
                           WHERE id=?""",
                        (
                            f"SLA breach: {wt} exceeded {threshold}-min threshold "
                            f"({age_mins:.0f} min elapsed). Auto-escalated by scheduler.",
                            now.isoformat(),
                            row["id"],
                        ),
                    )
                    _notify_sla_breach(row["id"], wt, age_mins)
                    escalated_count += 1
            except Exception as inner_e:
                logger.warning(f"SLA check skipped for {row['id']}: {inner_e}")

        conn.commit()
        conn.close()
        result = f"Checked {len(pending_rows)} pending | Escalated {escalated_count}"
        _update_status(job_name, result)

    except Exception as e:
        err = f"ERROR: {e}"
        JOB_STATUS[job_name] = {"last_run": datetime.datetime.now().strftime("%H:%M:%S"), "result": err}
        db.log_scheduler_job(job_name, "error", str(e))
        logger.error(f"[{job_name}] FAILED: {e}")


# ── JOB 2: RETRY FAILED OPERATIONS ────────────────────────────────
def job_retry_failed():
    """
    Runs every 10 minutes.
    Uses db.increment_retry() — structured fields, no string parsing.
    Retries requests where retry_count < MAX_RETRY.
    """
    job_name = "retry_failed"
    try:
        conn = db.get_conn()
        failed_rows = conn.execute(
            "SELECT id, workflow_type, retry_count FROM requests WHERE status='failed' AND retry_count < ?",
            (MAX_RETRY,),
        ).fetchall()
        conn.close()

        retried_count = 0
        for row in failed_rows:
            new_count = db.increment_retry(row["id"])
            logger.info(f"[retry_failed] Retrying {row['id']} (attempt {new_count}/{MAX_RETRY})")
            retried_count += 1

        result = f"Found {len(failed_rows)} failed | Retried {retried_count}"
        _update_status(job_name, result)

    except Exception as e:
        JOB_STATUS[job_name] = {"last_run": datetime.datetime.now().strftime("%H:%M:%S"), "result": f"ERROR: {e}"}
        db.log_scheduler_job(job_name, "error", str(e))
        logger.error(f"[{job_name}] FAILED: {e}")


# ── JOB 3: SYSTEM HEALTH / LOGGING ────────────────────────────────
def job_health_log():
    """
    Runs every 10 minutes.
    Reads DB for health metrics and writes a structured log entry.
    Purely observational — does NOT modify any data.
    """
    job_name = "health_log"
    try:
        conn = db.get_conn()
        total   = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        failed  = conn.execute("SELECT COUNT(*) FROM requests WHERE status='failed'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM requests WHERE status='pending'").fetchone()[0]
        resolved = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE policy_result IN ('APPROVED','RESOLVED')"
        ).fetchone()[0]
        avg_row = conn.execute("SELECT AVG(resolution_mins) FROM kpis").fetchone()
        avg_mins = round(avg_row[0] or 0, 1)
        conn.close()

        result = (
            f"Total={total} | Resolved={resolved} | "
            f"Failed={failed} | Pending={pending} | AvgRes={avg_mins}min"
        )
        _update_status(job_name, result)

    except Exception as e:
        JOB_STATUS[job_name] = {"last_run": datetime.datetime.now().strftime("%H:%M:%S"), "result": f"ERROR: {e}"}
        db.log_scheduler_job(job_name, "error", str(e))
        logger.error(f"[{job_name}] FAILED: {e}")


# ── JOB 4: DATA SYNC / CACHE REFRESH ──────────────────────────────
def job_data_sync():
    """
    Runs every 15 minutes.
    Clears @lru_cache on attendance CSV loader so fresh data is picked up
    without restarting the app.
    """
    job_name = "data_sync"
    try:
        # 1. Clear attendance CSV cache
        from campus.policy_engine import _load_attendance_csv
        _load_attendance_csv.cache_clear()

        # 2. Clear lab schedule / timetable CSV cache
        try:
            from campus import csv_loader as _csv_loader
            _csv_loader.clear_cache()
        except Exception:
            pass

        result = "CSV caches cleared (attendance + lab schedule) — fresh data on next call"
        _update_status(job_name, result)

    except Exception as e:
        JOB_STATUS[job_name] = {"last_run": datetime.datetime.now().strftime("%H:%M:%S"), "result": f"ERROR: {e}"}
        db.log_scheduler_job(job_name, "error", str(e))
        logger.error(f"[{job_name}] FAILED: {e}")


# ── JOB 5: EXPIRED BOOKING CLEANUP ────────────────────────────────
def job_booking_cleanup():
    """
    Runs every 30 minutes.
    Marks bookings past their expires_at timestamp as 'expired'.
    Safe: only touches confirmed bookings whose time has passed.
    """
    job_name = "booking_cleanup"
    try:
        count = db.expire_old_bookings()
        result = f"Expired {count} old booking(s)"
        _update_status(job_name, result)

    except Exception as e:
        JOB_STATUS[job_name] = {"last_run": datetime.datetime.now().strftime("%H:%M:%S"), "result": f"ERROR: {e}"}
        db.log_scheduler_job(job_name, "error", str(e))
        logger.error(f"[{job_name}] FAILED: {e}")


# ── APScheduler event listener ──────────────────────────────────────
def _on_job_event(event):
    if event.exception:
        logger.error(f"Job {event.job_id} raised: {event.exception}")


# ── MODULE-LEVEL SINGLETON ─────────────────────────────────────────
# Initialized ONCE at module import time — not inside Streamlit session.
# This prevents duplicate scheduler threads on Streamlit reruns.

_scheduler: BackgroundScheduler | None = None


def _build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(job_sla_monitor,    "interval", minutes=5,  id="sla_monitor",    replace_existing=True)
    sched.add_job(job_retry_failed,   "interval", minutes=10, id="retry_failed",   replace_existing=True)
    sched.add_job(job_health_log,     "interval", minutes=10, id="health_log",     replace_existing=True)
    sched.add_job(job_data_sync,      "interval", minutes=15, id="data_sync",      replace_existing=True)
    sched.add_job(job_booking_cleanup,"interval", minutes=30, id="booking_cleanup",replace_existing=True)
    sched.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    return sched


def get_scheduler() -> BackgroundScheduler:
    """Return the module-level singleton scheduler instance."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = _build_scheduler()
        _scheduler.start()
        logger.info("CampusFlow BackgroundScheduler started (module-level singleton).")
    return _scheduler


def start_scheduler():
    """Public entry point called from main.py. Idempotent — safe to call multiple times."""
    get_scheduler()
