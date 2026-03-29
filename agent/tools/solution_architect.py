# ============================================================
# solution_architect.py — Tool 2: Generate Autonomy Loop Plan + Tools & APIs
# ============================================================
# PURPOSE:
#   This tool takes the idea AND the problem analysis from Tool 1,
#   then generates two of the six CP1 form fields:
#     Field 3: Autonomy Loop Plan (textarea, min 50 chars)
#     Field 4: Tools & APIs (comma-separated input)
#
# WHY THIS TAKES problem_analysis AS INPUT (information chaining):
#   The autonomy design must directly address the problem from Tool 1.
#   If we skipped Tool 1, the LLM might design an autonomy loop for
#   a DIFFERENT problem. Information chaining keeps the pipeline
#   grounded — each tool builds on the previous one's output.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Update solution_architect.py to design autonomy loops for
#    [your domain]. Change the tool/API recommendations to match
#    your hackathon's requirements."
# ============================================================


def run(idea, problem_analysis, client, model):
    """Generate the Autonomy Loop Plan and Tools & APIs for CP1."""

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    prompt = f"""You are helping a student team fill out their CP1 submission for StudAI Foundry — India's national autonomous AI hackathon.

The team has defined their problem. Now design how the autonomous agent works.

PROJECT IDEA: {idea}

PROBLEM ANALYSIS FROM PREVIOUS STEP:
{problem_analysis}

Respond with these EXACT two sections (use the exact headers):

**FIELD 3 — Autonomy Loop Plan:**
Describe how the AI agent operates autonomously using the 5-step loop. Map each step to THIS specific product:

- THINK: What does the agent analyse before starting? (e.g., "Parses the student's syllabus and identifies weak topics from past exam scores")
- PLAN: What action plan does it create? (e.g., "Creates a JSON plan: first run topic_analyzer, then gap_finder, then study_plan_writer")
- EXECUTE: What tools does it run and in what order? What does each tool produce?
- REVIEW: How does it evaluate its own output? What quality criteria does it check? (e.g., "Scores the study plan on coverage, difficulty progression, and time feasibility")
- UPDATE: What specific feedback does it use to improve on retry? (e.g., "If coverage score is below 7, adds more practice questions for weak topics")

Write this as a flowing paragraph or structured list. Must be at least 50 characters. Be specific to THIS product — not generic autonomy descriptions. 4-6 sentences.

**FIELD 4 — Tools & APIs:**
List the specific tools, APIs, and libraries this agent would use, comma-separated. Include:
- LLM provider (e.g., Groq, OpenAI)
- UI framework (e.g., Streamlit, Gradio)
- Key Python libraries
- Any external APIs (free tiers only)
Format: comma-separated, like "Groq API, Streamlit, Python, LangChain, Tavily Search API"

Be realistic for a student team building in 10 days."""

    # ── CALL THE LLM ─────────────────────────────────────────────
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )

    return response.choices[0].message.content
