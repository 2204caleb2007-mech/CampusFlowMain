# ============================================================
# problem_definer.py — Tool 1: Generate Problem Statement + Target Users
# ============================================================
# PURPOSE:
#   This tool takes a raw project idea and generates two of the
#   six CP1 form fields:
#     Field 1: Problem Statement (textarea, min 50 chars)
#     Field 2: Target Users (input, min 10 chars)
#
# WHY THIS IS A SEPARATE FILE (single responsibility):
#   Each tool does ONE job. problem_definer focuses only on the
#   problem and who has it — it doesn't propose solutions. This
#   forces the agent to understand the problem BEFORE jumping to
#   solutions, which is how good product thinking works.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Change problem_definer.py to extract problems specific to
#    [your domain]. For example, for a healthcare agent, extract
#    patient pain points and clinical workflow gaps."
# ============================================================


def run(idea, client, model):
    """Generate the Problem Statement and Target Users for CP1."""

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    prompt = f"""You are helping a student team fill out their CP1 submission for StudAI Foundry — India's national autonomous AI hackathon.

Given this project idea, generate EXACTLY two outputs matching the CP1 form fields.

PROJECT IDEA: {idea}

Respond with these EXACT two sections (use the exact headers):

**FIELD 1 — Problem Statement:**
Write what problem this AI agent solves. Be specific — not "students struggle with learning" but describe the exact pain point, who experiences it, how often, and why it needs solving NOW. Must be at least 50 characters. Write 3-5 sentences. Be specific to India where relevant.

**FIELD 2 — Target Users:**
Who will use this? Be specific — not "students" but "2nd-3rd year engineering students in tier-2 Indian colleges" or "small restaurant owners in semi-urban India." One clear sentence, at least 10 characters.

Be concrete and specific. No generic filler. No buzzwords."""

    # ── CALL THE LLM ─────────────────────────────────────────────
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=400,
    )

    return response.choices[0].message.content
