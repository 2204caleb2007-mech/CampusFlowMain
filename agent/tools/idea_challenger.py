# ============================================================
# idea_challenger.py — Tool 3: Devil's Advocate Analysis
# ============================================================
# PURPOSE:
#   This tool acts as a "devil's advocate" — it takes the problem
#   analysis and solution architecture, and actively challenges
#   them. It looks for weaknesses, blind spots, unrealistic claims,
#   and missing considerations.
#
# WHY A CHALLENGER EXISTS:
#   Without this tool, the agent produces optimistic output that
#   tells students what they want to hear. A devil's advocate
#   forces the submission to address hard questions BEFORE judges
#   ask them. The submission_writer then uses these challenges to
#   write a stronger, more honest draft.
#
#   This is also a key demonstration of MULTI-PERSPECTIVE AI:
#   the same LLM can argue FOR and AGAINST an idea when prompted
#   differently. The agent uses both perspectives to produce a
#   balanced output.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Change idea_challenger.py to challenge [your domain's]
#    assumptions. For example, for a healthcare agent, challenge
#    regulatory feasibility, data privacy risks, and clinical
#    validation requirements."
# ============================================================


def run(idea, problem_analysis, solution_architecture, client, model):
    """Challenge the idea — find weaknesses, blind spots, and hard questions."""

    # ── BUILD THE PROMPT ─────────────────────────────────────────
    prompt = f"""You are a tough but fair hackathon judge reviewing a CP1 submission for StudAI Foundry — India's national autonomous AI hackathon.

Your job is NOT to praise the idea. Your job is to find WEAKNESSES, BLIND SPOTS, and HARD QUESTIONS that the team hasn't addressed. Be specific and constructive.

PROJECT IDEA: {idea}

PROBLEM ANALYSIS:
{problem_analysis}

SOLUTION ARCHITECTURE:
{solution_architecture}

Respond with these exact sections:

**Fatal Flaw Check:**
Is there a fundamental reason this can't work? (technical impossibility, legal barrier, market timing). If no fatal flaw, say "No fatal flaw found" and move on.

**Blind Spots (2-3):**
What has the team NOT considered? Examples: edge cases, user segments they're ignoring, scaling issues, data availability, cost of LLM calls at scale, dependency on a single API.

**Hard Questions Judges Will Ask:**
List 3 specific questions a judge would ask about this submission. These should be questions the team needs to have answers for.

**Strengthening Recommendations:**
How can the submission be stronger? Give 2-3 specific suggestions that would make the Autonomy Loop Plan more convincing and the Expected Output more concrete.

Be brutally honest but constructive. Under 250 words. No fluff."""

    # ── CALL THE LLM ─────────────────────────────────────────────
    # Why temperature 0.5: we want genuinely challenging perspectives,
    # not the safe/obvious critique. Slightly more creative than other tools.
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=400,
    )

    return response.choices[0].message.content
