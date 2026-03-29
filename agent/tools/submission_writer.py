# ============================================================
# submission_writer.py — Tool 4: Compile all 6 CP1 fields
# ============================================================
# PURPOSE:
#   This tool synthesises outputs from Tools 1-3 (problem analysis,
#   solution architecture, AND devil's advocate challenges) to
#   produce all 6 CP1 fields in copy-paste-ready format.
#
#   The challenger's critique makes the output STRONGER — the
#   submission addresses weaknesses before judges find them.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Change submission_writer.py to output a CP2 demo script
#    instead. Include: Demo Flow, Talking Points, Live Demo
#    Checklist, and Backup Plan."
# ============================================================


def run(idea, problem_analysis, solution_architecture, challenger_critique, client, model):
    """Compile all 6 CP1 fields using insights from all previous tools."""

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    prompt = f"""You are writing the final CP1 submission for StudAI Foundry — India's national autonomous AI hackathon.

You have THREE inputs from previous tools:
1. Problem analysis (Fields 1-2 raw material)
2. Solution architecture (Fields 3-4 raw material)
3. Devil's advocate critique (use this to STRENGTHEN the submission)

PROJECT IDEA: {idea}

PROBLEM ANALYSIS:
{problem_analysis}

SOLUTION ARCHITECTURE:
{solution_architecture}

DEVIL'S ADVOCATE CRITIQUE:
{challenger_critique}

IMPORTANT: The critique above found weaknesses. ADDRESS THEM in your output. Don't ignore them — weave the answers into the relevant fields. This is what makes the submission stronger than a naive first draft.

Write EXACTLY 6 fields with these EXACT headers. Each field MUST be clearly separated.

### FIELD 1 — Problem Statement
Write 3-5 sentences answering: "What problem does your AI agent solve?"
Be specific. Include who has the problem, what the pain is, and why it needs solving NOW.
Address any blind spots the challenger found about the problem.
MINIMUM 50 characters.

### FIELD 2 — Target Users
One specific sentence: "Who will use this?"
Not "students" — be specific: demographics, context, location.
MINIMUM 10 characters.

### FIELD 3 — Autonomy Loop Plan
Describe how the AI agent operates autonomously. Map ALL 5 steps:
- THINK: What does the agent analyse first?
- PLAN: What JSON action plan does it create?
- EXECUTE: What tools run and in what order?
- REVIEW: How does it score its own output? What criteria?
- UPDATE: What feedback does it use to improve on retry?
Address the challenger's questions about the autonomy approach.
MINIMUM 50 characters. Write 4-6 specific sentences.

### FIELD 4 — Tools & APIs
Comma-separated list. Example: "Groq API, Streamlit, Python, python-dotenv, Tavily Search"
Keep it realistic for a student team.

### FIELD 5 — Evaluation Logic
How will you measure if the agent's output is successful?
What metrics does the REVIEW step check? Be specific to THIS product.
MINIMUM 20 characters. 2-3 sentences.

### FIELD 6 — Expected Output
What does a successful output look like? Describe the concrete deliverable.
A judge should be able to picture exactly what the user receives.
MINIMUM 20 characters. 2-3 sentences.

RULES:
- Every field must meet its minimum character length
- Address challenger critique — don't leave weaknesses unaddressed
- Be specific to THIS project, not generic
- Judges read 100+ submissions — every sentence must carry weight
- Under 500 words total"""

    # ── CALL THE LLM ─────────────────────────────────────────────
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=900,
    )

    return response.choices[0].message.content
