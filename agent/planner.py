# ============================================================
# planner.py — Creates a JSON execution plan from goal + feedback
# ============================================================
# PURPOSE:
#   The planner asks the LLM to create a step-by-step action plan
#   in JSON format. It tells the LLM what tools are available and
#   lets the LLM decide the order and reasoning for each step.
#
# THE PLANNING PATTERN:
#   An autonomous agent doesn't just "do stuff" — it first PLANS
#   what to do. The plan is a list of tool calls in order. This is
#   what separates an agent from a chatbot: the agent decides its
#   own workflow before executing it.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Add a new tool to AVAILABLE_TOOLS in planner.py called
#    market_validator with a description. Then add the routing
#    in executor.py."
# ============================================================

import json

# ── AVAILABLE TOOLS ──────────────────────────────────────────────
# This list tells the LLM what tools exist. When you add a new tool
# file in agent/tools/, you MUST also add it here — otherwise the
# planner won't know it exists and will never include it in a plan.
AVAILABLE_TOOLS = [
    {
        "name": "request_classifier",
        "description": "Takes the student request, classifies type (lab/leave/event), and extracts key details",
    },
    {
        "name": "form_parser",
        "description": "Parses a PDF or text form to extract structured fields: name, request_type, date, department using PyMuPDF",
    },
    {
        "name": "availability_checker",
        "description": "Checks Google Sheets for the requested lab slot or room and returns available or conflict with alternative slots",
    },
    {
        "name": "email_router",
        "description": "Sends the routed email to HOD/lab-in-charge via Gmail API and sends Telegram confirmation to the student",
    },
]


def create_plan(idea, feedback, client, model):
    """Ask the LLM to generate a JSON execution plan for the given idea."""

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    feedback_section = ""
    if feedback:
        feedback_section = f"""
FEEDBACK FROM PREVIOUS ATTEMPT (use this to improve the plan):
{feedback}
"""

    tools_description = "\n".join(
        [f'  - {t["name"]}: {t["description"]}' for t in AVAILABLE_TOOLS]
    )

    prompt = f"""You are a planning engine for CampusBot, an autonomous AI agent for campus workflows.

GOAL: Plan the autonomous execution for a student query sent to CampusBot on Telegram.
The agent must classify the request, parse the form, check availability,
route the email to HOD if needed, and draft a final response.

STUDENT REQUEST: {idea}
{feedback_section}
AVAILABLE TOOLS:
{tools_description}

Create an execution plan with exactly 4 steps, one per tool in this exact order:
  request_classifier → form_parser → availability_checker → email_router

The email_router MUST always be last.

Return ONLY valid JSON — no markdown, no explanation, no extra text.
Use this exact format:
[
  {{"step": 1, "tool": "request_classifier",   "reason": "why this step"}},
  {{"step": 2, "tool": "form_parser",           "reason": "why this step"}},
  {{"step": 3, "tool": "availability_checker",  "reason": "why this step"}},
  {{"step": 4, "tool": "email_router",           "reason": "why this step"}}
]"""

    # ── CALL THE LLM ─────────────────────────────────────────────
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
    )

    raw = response.choices[0].message.content

    # ── PARSE THE JSON ───────────────────────────────────────────
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    plan = json.loads(raw)
    return plan
