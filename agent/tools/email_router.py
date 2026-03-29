# ============================================================
# email_router.py — Tool 6: Send routed email + Telegram confirmation
# ============================================================
# PURPOSE:
#   Two outbound actions in one tool:
#     A) Route formal email to HOD / lab-in-charge via Gmail API (OAuth2)
#     B) Send Telegram confirmation message back to the student
#
# ENV VARIABLES REQUIRED (.env):
#   GMAIL_CLIENT_SECRET_JSON  — path to OAuth2 client_secret.json from GCP Console
#   GMAIL_TOKEN_JSON          — path where user token will be cached (auto-created)
#   GMAIL_SENDER              — your Gmail address
#   HOD_EMAIL_CSE / ECE / IT / MECH / EEE / DEFAULT
#   TELEGRAM_BOT_TOKEN        — your bot token from @BotFather
#   TELEGRAM_CHAT_ID          — student's Telegram chat_id
#
# GRACEFUL DEGRADATION:
#   All external calls degrade to "simulated" mode if credentials are absent.
#   Full demo works with zero configuration.
#
# AUTONOMY LOG:
#   Every send action is appended to autonomy_logs.json with a
#   THINK→UPDATE trace.
# ============================================================

import json
import os
import base64
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, Optional

try:
    from googleapiclient.discovery import build as google_build  # type: ignore
    from google.oauth2.credentials import Credentials as GCredentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    from google.auth.transport.requests import Request as GRequest  # type: ignore
    GMAIL_SDK_AVAILABLE = True
except ImportError:
    GMAIL_SDK_AVAILABLE = False

try:
    import requests as _requests  # type: ignore
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "autonomy_logs.json",
)


def _resolve_hod_email(department: str) -> str:
    dept = department.upper().strip()
    mapping: Dict[str, str] = {
        "CSE":  os.getenv("HOD_EMAIL_CSE",  "hod.cse@campus.edu"),
        "ECE":  os.getenv("HOD_EMAIL_ECE",  "hod.ece@campus.edu"),
        "IT":   os.getenv("HOD_EMAIL_IT",   "hod.it@campus.edu"),
        "MECH": os.getenv("HOD_EMAIL_MECH", "hod.mech@campus.edu"),
        "EEE":  os.getenv("HOD_EMAIL_EEE",  "hod.eee@campus.edu"),
    }
    for key, val in mapping.items():
        if key in dept:
            return val
    return os.getenv("HOD_EMAIL_DEFAULT", "principal@campus.edu")


def _get_gmail_service() -> Any:
    if not GMAIL_SDK_AVAILABLE:
        return None
    secret_path = os.getenv("GMAIL_CLIENT_SECRET_JSON", "")
    token_path  = os.getenv("GMAIL_TOKEN_JSON", "token.json")
    if not secret_path or not os.path.isfile(secret_path):
        return None

    creds: Any = None
    if os.path.isfile(token_path):
        creds = GCredentials.from_authorized_user_file(token_path, GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secret_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return google_build("gmail", "v1", credentials=creds)


def _send_gmail(to: str, subject: str, body: str) -> Dict[str, Any]:
    service = _get_gmail_service()
    sender  = os.getenv("GMAIL_SENDER", "campusbot@gmail.com")
    if not service:
        return {
            "status": "simulated",
            "to": to,
            "subject": subject,
            "note": "Gmail SDK or credentials not configured — email logged only.",
        }
    try:
        msg = MIMEMultipart("alternative")
        msg["To"]      = to
        msg["From"]    = sender
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result: Dict[str, Any] = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return {"status": "sent", "message_id": str(result.get("id")), "to": to, "subject": subject}
    except Exception as e:
        return {"status": "error", "error": str(e), "to": to, "subject": subject}


def _send_telegram(chat_id: str, message: str) -> Dict[str, Any]:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token or not REQUESTS_AVAILABLE:
        return {
            "status": "simulated",
            "chat_id": chat_id,
            "note": "TELEGRAM_BOT_TOKEN not set — Telegram message logged only.",
        }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = _requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
        data: Dict[str, Any] = resp.json()
        if data.get("ok"):
            return {"status": "sent", "message_id": str(data["result"]["message_id"])}
        return {"status": "error", "error": str(data.get("description", "Unknown error"))}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _append_autonomy_log(entry: Dict[str, Any]) -> None:
    try:
        logs: list = []
        if os.path.isfile(_LOG_PATH):
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                logs = json.load(f)
        logs.append(entry)
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[email_router] Failed to write autonomy log: {e}")


def run(student_request: str, form_output: str, classifier_output: str,
        availability_output: str, client: Any, model: str,
        telegram_chat_id: Optional[str] = None) -> str:
    """
    Route email to HOD/lab-in-charge and send Telegram confirmation.

    Returns JSON string with: email_result, telegram_result, department,
    hod_email, telegram_message, timestamp, autonomy_log_id.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    chat_id   = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "0")

    form_data:       Dict[str, Any] = {}
    classifier_data: Dict[str, Any] = {}
    avail_data:      Dict[str, Any] = {}

    for raw, target in [
        (form_output,         form_data),
        (classifier_output,   classifier_data),
        (availability_output, avail_data),
    ]:
        try:
            target.update(json.loads(raw))
        except Exception:
            pass

    department: str = (
        str(form_data.get("department") or
            (classifier_data.get("extracted_details") or {}).get("department") or
            "CSE")
    )
    hod_email = _resolve_hod_email(department)

    escalation_triggered: bool = bool(classifier_data.get("requires_hod_approval", False))
    email_result: Dict[str, Any] = {"status": "skipped", "reason": "No escalation triggered"}

    if escalation_triggered:
        subject = f"Student Request — {student_request}"
        body    = f"Dear HOD,\n\nA student has requested the following:\n{student_request}\n\nAvailability from System:\n{avail_data.get('status_msg', 'N/A')}\n\nPlease approve or deny.\n\nThanks,\nCampusBot"
        email_result = _send_gmail(hod_email, subject, body)

    avail_msg    = str(avail_data.get("status_msg", ""))
    intent       = str((classifier_data.get("classification") or {}).get("intent", "general_faq"))
    student_name = str(form_data.get("name") or "Student")

    # Only include availability info if the request is lab/resource related
    is_lab_request = intent.lower() in ("lab_booking", "lab", "room", "resource", "facility", "availability")

    if escalation_triggered:
        avail_section = f"\U0001f4cb *Availability*: {avail_msg}\n\n" if is_lab_request and avail_msg else ""
        tg_message = (
            f"\U0001f44b Hi {student_name}!\n\n"
            f"Your *{intent}* request has been received and forwarded to the HOD ({department}).\n\n"
            f"{avail_section}"
            f"\U0001f4e7 Email has been sent to {hod_email}. "
            f"You will receive a response within 24 hours.\n\n"
            f"_Ref timestamp: {timestamp}_"
        )
    else:
        if is_lab_request and avail_msg:
            avail_section = f"{avail_msg}\n\n"
        else:
            avail_section = ""
        tg_message = (
            f"\U0001f44b Hi {student_name}!\n\n"
            f"Your *{intent}* query has been resolved:\n\n"
            f"{avail_section}"
            f"_Ref timestamp: {timestamp}_"
        )

    telegram_result = _send_telegram(chat_id, tg_message)

    log_entry: Dict[str, Any] = {
        "id":              f"log_{timestamp}",
        "timestamp":       timestamp,
        "cycle":           "THINK\u2192PLAN\u2192EXECUTE\u2192REVIEW\u2192UPDATE",
        "student_request": student_request,
        "THINK": {
            "parsed_form":       form_data,
            "classified_intent": classifier_data,
        },
        "EXECUTE": {
            "availability_check": avail_data,
        },
        "UPDATE": {
            "email_result":    email_result,
            "telegram_result": telegram_result,
            "hod_email":       hod_email,
            "department":      department,
        },
    }
    _append_autonomy_log(log_entry)

    output: Dict[str, Any] = {
        "email_result":    email_result,
        "telegram_result": telegram_result,
        "department":      department,
        "hod_email":       hod_email,
        "telegram_message": tg_message,
        "timestamp":       timestamp,
        "autonomy_log_id": log_entry["id"],
    }

    return json.dumps(output, indent=2)
