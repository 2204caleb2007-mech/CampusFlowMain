# ============================================================
# form_parser.py — Tool 2: Parse PDF or text form submissions
# ============================================================
import re
import json
import os
from typing import Optional, Dict, Any

try:
    import fitz  # type: ignore
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)
_NAME_PATTERN = re.compile(
    r"(?:name\s*[:\-]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
    re.IGNORECASE,
)
_DEPT_PATTERN = re.compile(
    r"(?:dept(?:artment)?\s*[:\-]?\s*|branch\s*[:\-]?\s*)"
    r"([A-Za-z &/]+?)(?:\n|,|\.|$)",
    re.IGNORECASE,
)
_TYPE_KEYWORDS: Dict[str, list] = {
    "leave":       ["leave", "absent", "medical", "sick", "od", "on duty", "vacation"],
    "lab":         ["lab", "laboratory", "equipment", "apparatus", "booking", "slot"],
    "event":       ["event", "hackathon", "symposium", "workshop", "seminar", "fest"],
    "general_faq": ["circular", "notice", "fee", "hostel", "library", "timetable"],
}


def _extract_with_regex(text: str) -> Dict[str, Any]:
    """Fast regex-based field extraction from raw text."""
    result: Dict[str, Any] = {
        "name":         None,
        "request_type": None,
        "date":         None,
        "department":   None,
    }

    m = _NAME_PATTERN.search(text)
    if m:
        result["name"] = m.group(1).strip()

    dates = _DATE_PATTERN.findall(text)
    if dates:
        result["date"] = dates[0]

    m = _DEPT_PATTERN.search(text)
    if m:
        result["department"] = m.group(1).strip()

    text_lower = text.lower()
    best_type: Optional[str] = None
    best_count = 0
    for rtype, keywords in _TYPE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_type = rtype
    result["request_type"] = best_type or "general_faq"

    return result


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    if not PYMUPDF_AVAILABLE:
        return ""
    try:
        doc = fitz.open(pdf_path)
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text("text"))
        doc.close()
        return "\n".join(pages_text)
    except Exception as e:
        return f"[PDF_READ_ERROR: {e}]"


def _extract_with_llm(text: str, client: Any, model: str) -> Dict[str, Any]:
    """Ask the LLM to extract fields when regex comes up short."""
    
    # Bypassing the slice notation using a generic cut approach to dodge arbitrary type-checker bugs
    txt_to_prompt = "".join(list(text)[:3000])

    prompt = f"""You are a form parsing assistant for CampusBot.

Extract the following fields from the student form text below.
Fields: name, request_type, date, department.

request_type must be one of: "leave", "lab", "event", "general_faq"

FORM TEXT:
\"\"\"
{txt_to_prompt}
\"\"\"

Return ONLY valid JSON — no markdown, no explanation:
{{
  "name": "<student full name or null>",
  "request_type": "leave | lab | event | general_faq",
  "date": "<date string or null>",
  "department": "<department name or null>"
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=200,
    )
    raw: str = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        parts = raw.split("\n", 1)
        raw = parts[1] if len(parts) > 1 else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def run(student_request: str, client: Any, model: str,
        pdf_path: Optional[str] = None) -> str:
    """
    Parse a student form (PDF or plain text) and extract key fields.

    Returns JSON string with: name, request_type, date, department, source, raw_text_snippet
    """
    source_tag_list = ["text"]
    raw_text: str = student_request

    if pdf_path and os.path.isfile(pdf_path):
        pdf_text = _extract_text_from_pdf(pdf_path)
        if pdf_text and not pdf_text.startswith("[PDF_READ_ERROR"):
            raw_text = pdf_text + "\n" + student_request
            source_tag_list = ["pdf"]

    fields = _extract_with_regex(raw_text)
    regex_confidence = sum(1 for v in fields.values() if v is not None)

    if regex_confidence < 3:
        try:
            llm_fields: Dict[str, Any] = _extract_with_llm(raw_text, client, model)
            for k, v in llm_fields.items():
                if not fields.get(k) and v:
                    fields[k] = v
            source_tag_list.append("+llm")
        except Exception as e:
            fields["_parse_error"] = str(e)
    else:
        source_tag_list.append("+regex")

    result = {
        "name":             fields.get("name"),
        "request_type":     fields.get("request_type", "general_faq"),
        "date":             fields.get("date"),
        "department":       fields.get("department"),
        "source":           "".join(source_tag_list),
        "raw_text_snippet": "".join(list(raw_text)[:200]),
    }

    return json.dumps(result, indent=2)
