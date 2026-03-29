# ============================================================
# loop.py — THE CORE: The 5-step autonomy loop
# ============================================================
# PURPOSE:
#   This is the most important file in the project. Read this
#   first. Everything else exists to serve this file.
#
#   It implements the 5-step autonomous agent loop:
#     THINK → PLAN → EXECUTE → REVIEW → UPDATE
#
#   This loop is what makes the system an AUTONOMOUS AGENT
#   instead of a chatbot. Read the difference below.
#
# CHATBOT vs AUTONOMOUS AGENT:
#   A chatbot does this:
#     User input → LLM call → Return output → Done.
#     One shot. No quality check. Whatever the LLM says, you get.
#
#   An autonomous agent does this:
#     User gives a GOAL
#       → Agent THINKS about the goal and any past feedback
#       → Agent PLANS what tools to use (it decides, not you)
#       → Agent EXECUTES the tools in sequence
#       → Agent REVIEWS its own output (scores it 1-10)
#       → If score < 7: Agent UPDATES with feedback and loops again
#       → If score >= 7: Agent delivers the result
#
#   The critical difference is steps 4 and 5: REVIEW and UPDATE.
#   The agent evaluates itself and self-corrects. A chatbot never
#   does this. This is what "autonomous" means — the agent makes
#   decisions about its own output quality without human input.
#
# WHY THIS ARCHITECTURE IS UNIVERSAL:
#   Every autonomous AI agent — whether it validates startups,
#   handles customer support, processes invoices, qualifies sales
#   leads, or triages medical cases — follows this exact same loop.
#   The DOMAIN changes. The LOOP does not.
#
#   Think of it like a washing machine: the spin cycle is always
#   the same (wash → rinse → spin → check → repeat if needed).
#   You change the clothes (the tools), not the machine (the loop).
#
# THE ONE RULE:
#   THE LOOP NEVER CHANGES. THE TOOLS DO.
#   To build a different agent, keep this file exactly the same
#   and only change the files in agent/tools/.
#
# HOW TO CUSTOMISE (vibe coding prompt):
#   "Keep loop.py exactly the same. Change the tools in agent/tools/
#    so this agent does [your domain] instead of startup validation."
# ============================================================

from agent import planner, executor, reviewer

# ── CONFIGURATION ────────────────────────────────────────────────
# MAX_LOOPS controls how many self-correction cycles the agent gets.
# Why 3: enough retries to meaningfully improve quality, but not so
# many that a bad idea loops forever burning API calls.
#
# Try changing this:
#   MAX_LOOPS = 1  → behaves like a chatbot (no self-correction)
#   MAX_LOOPS = 5  → more chances to improve, but slower
#   MAX_LOOPS = 3  → sweet spot for demos (default)
MAX_LOOPS = 3


def run(idea, client, model, on_step, on_log):
    """
    Run the 5-step autonomous agent loop.

    Parameters:
        idea    : str       — the startup idea text from the user
        client  : Groq      — already-initialised Groq client
        model   : str       — model name string (e.g. "llama-3.3-70b-versatile")
        on_step : callable  — UI callback: on_step(step, status)
                              step:   "think" | "plan" | "execute" | "review" | "update"
                              status: "active" | "done" | "failed" | "skipped"
        on_log  : callable  — UI callback: on_log(message) for activity log

    Returns:
        dict — tool results: {"market_research": str, "feasibility": str, "brief_writer": str}
    """

    # ── LOOP STATE ───────────────────────────────────────────────
    # feedback: starts empty. After a failed review, the reviewer
    # fills this with SPECIFIC criticism ("market size is vague",
    # "risks are too generic"). This feedback is passed to the
    # planner on the next loop so the agent knows WHAT to improve.
    # This is the "memory" of the self-correction cycle.
    feedback = ""

    # final_results: always holds the latest tool outputs. Even if
    # the agent can't pass the quality bar after MAX_LOOPS, we
    # still return the best attempt — something is better than nothing.
    final_results = {}

    # ── THE AUTONOMY LOOP ────────────────────────────────────────
    # This for-loop IS the autonomy. Without it, you have a pipeline.
    # With it, you have an agent that can retry and improve.
    for loop_num in range(1, MAX_LOOPS + 1):
        on_log(f"═══ Loop {loop_num} of {MAX_LOOPS} ═══")

        # ── STEP 1: THINK ──────────────────────────────────────────
        # What: The agent acknowledges the goal and any feedback.
        # Why:  Before acting, the agent needs context. On loop 1,
        #       context = just the idea. On loops 2-3, context also
        #       includes feedback from the reviewer: "the market size
        #       was too vague" or "risks were generic." This is how
        #       the agent gets SMARTER on each retry — not random,
        #       but directed by specific self-critique.
        on_step("think", "active")
        on_log(f"Parsing goal: {idea[:80]}...")
        if feedback:
            on_log(f"Incorporating feedback from previous attempt: {feedback[:100]}...")
        on_step("think", "done")

        # ── STEP 2: PLAN ───────────────────────────────────────────
        # What: The agent asks the LLM to create a JSON action plan.
        # Why:  An autonomous agent decides WHAT to do — you don't
        #       tell it "run market research, then feasibility, then
        #       write a brief." The agent figures that out itself by
        #       looking at the available tools and the goal.
        #       The plan is structured JSON: [{step, tool, reason}]
        #       so the executor can parse and run it mechanically.
        on_step("plan", "active")
        try:
            plan = planner.create_plan(idea, feedback, client, model)
            on_log(f"Plan created with {len(plan)} steps:")
            for step in plan:
                on_log(f"  Step {step['step']}: {step['tool']} — {step['reason']}")
            on_step("plan", "done")
        except Exception as e:
            on_log(f"Planning failed: {e}")
            on_step("plan", "failed")
            break

        # ── STEP 3: EXECUTE ────────────────────────────────────────
        # What: The executor runs each tool in the plan in sequence.
        # Why:  EXECUTE is separate from PLAN because the planner
        #       decides what to do, the executor does it. This is
        #       separation of concerns — the same principle used in
        #       every production system. Also, information CHAINS:
        #       market_research output feeds into feasibility, and
        #       both feed into brief_writer. Each tool builds on
        #       the previous one's output.
        on_step("execute", "active")
        try:
            results = executor.run_plan(plan, idea, client, model, on_log)
            final_results = results
            on_step("execute", "done")
        except Exception as e:
            on_log(f"Execution failed: {e}")
            on_step("execute", "failed")
            break

        # ── STEP 4: REVIEW ─────────────────────────────────────────
        # What: The agent scores its own output on a 1-10 scale.
        # Why:  THIS IS THE STEP THAT MAKES IT AUTONOMOUS.
        #
        #       Without REVIEW, the agent is just a pipeline:
        #         input → tool 1 → tool 2 → tool 3 → output
        #       That's a fancy chatbot. It has no quality awareness.
        #
        #       With REVIEW, the agent asks: "Is my output actually
        #       good? Does it have specific market data? Are the
        #       recommendations actionable? Or is this generic filler?"
        #
        #       The reviewer scores the output and returns:
        #         - score: 1-10
        #         - passed: true/false (score >= 7)
        #         - what_is_good: strengths to preserve
        #         - feedback: specific improvements for next loop
        #
        #       A human manager does this exact same thing when they
        #       review a junior employee's work. The agent IS the
        #       manager AND the employee — that's self-evaluation.
        on_step("review", "active")
        try:
            review = reviewer.evaluate(idea, results, client, model)
            on_log(f"Review score: {review.get('score', '?')}/10")
            on_log(f"Quality check: {'PASSED ✓' if review.get('passed') else 'FAILED ✗'}")
            on_log(f"Strengths: {review.get('what_is_good', 'N/A')}")
            on_step("review", "done")
        except Exception as e:
            on_log(f"Review failed: {e}")
            on_step("review", "failed")
            # Why we set a fallback review: even if the reviewer crashes,
            # the loop should continue — we default to "try again"
            review = {"passed": False, "score": 0, "feedback": "retry"}

        # ── STEP 5: UPDATE or COMPLETE ─────────────────────────────
        # What: If review passed → deliver. If not → carry feedback
        #       into the next loop and try again.
        # Why:  UPDATE is what closes the self-correction cycle.
        #       The agent doesn't just retry blindly — it carries
        #       SPECIFIC feedback: "the market size section was too
        #       vague, add numbers" or "the risks were generic."
        #       This feedback goes to the planner on the next loop,
        #       which produces a plan informed by what went wrong.
        #
        #       This is the difference between:
        #         Retry = do the same thing again (hope for the best)
        #         Self-correct = do it again WITH specific improvements
        #
        #       Self-correction is what makes the agent autonomous.
        if review.get("passed"):
            on_step("update", "skipped")
            on_log(f"Quality check passed on loop {loop_num} — delivering results ✓")
            return final_results
        else:
            on_step("update", "active")
            feedback = review.get("feedback", "improve depth and specificity")
            on_log(f"Feedback for next attempt: {feedback}")
            on_step("update", "done")
            if loop_num < MAX_LOOPS:
                on_log(f"Starting loop {loop_num + 1} with improved context...")

    # ── MAX LOOPS REACHED ────────────────────────────────────────
    # Why we still return results: even if the agent couldn't reach
    # the quality threshold after all retries, the best attempt is
    # still useful. In production, you might escalate to a human here.
    on_log(f"Max loops ({MAX_LOOPS}) reached — delivering best attempt")
    return final_results
