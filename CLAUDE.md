# CLAUDE.md — Project Brain for AI Coding Tools

## 1. What This Project Does

This is **StudAI LaunchPad** — the hands-on workshop product for **StudAI Foundry**, India's national autonomous AI systems hackathon. The workshop (March 19, 2026) is where engineering students at SRMIST learn the difference between a chatbot and an autonomous AI agent by cloning this repo, running it live, and then using "vibe coding" (directing GitHub Copilot or Claude Code) to build their own autonomous agent for the Foundry hackathon.

The product itself is a **CP1 Submission Drafter** — an autonomous AI agent (not a chatbot). The user enters their hackathon project idea. The agent autonomously defines the problem, architects the solution, **challenges the idea like a devil's advocate**, then writes a submission that addresses those challenges. It reviews each field individually against CP1 criteria and self-corrects until the draft passes 7/10. Students walk out with a usable CP1 draft and per-field copy boxes to paste directly into the submission form.

## 2. The 5-Step Autonomy Loop

```
┌─────────────────────────────────────────────────────┐
│           THE AUTONOMOUS AGENT LOOP                 │
│                                                     │
│   THINK → PLAN → EXECUTE → REVIEW → UPDATE          │
│     ↑                                   │           │
│     └───────────── (if score < 7) ──────┘           │
│                                                     │
│   Max 3 loops. Passes when review score >= 7/10.    │
└─────────────────────────────────────────────────────┘
```

- **THINK**: Parse the goal and incorporate feedback from any previous failed attempt — context awareness
- **PLAN**: Ask the LLM to generate a JSON step-by-step execution plan — the agent decides its own workflow
- **EXECUTE**: Run each tool in the plan (define → architect → challenge → write) — tool use with information chaining
- **REVIEW**: Score each field individually 1-10 against CP1 criteria — **self-evaluation, the core of autonomy**
- **UPDATE**: If review failed, carry field-specific feedback into the next loop iteration — self-correction

**Why is the REVIEW step what makes this autonomous?** A chatbot returns whatever the LLM generates. An autonomous agent *judges its own work* against a quality standard and decides whether to accept it or try again with specific improvements. This self-evaluation loop is what separates "I called an API" from "I built an autonomous system."

## 3. File Map — Every File and Its Purpose

```
studai-foundry-launchpad/
│
├── CLAUDE.md                    ← This file — project brain for AI tools
├── README.md                    ← Student setup guide (3 steps)
├── requirements.txt             ← groq, streamlit, python-dotenv
├── .env.example                 ← API key template
├── .gitignore                   ← Exclude .env and __pycache__
│
├── main.py                      ← Streamlit UI — tabs, per-field boxes, score dashboard
│
└── agent/
    ├── __init__.py               ← Package marker
    ├── loop.py                   ← THE CORE — the 5-step autonomy loop
    ├── planner.py                ← LLM call → JSON plan (4 tools)
    ├── executor.py               ← Routes plan steps → tool functions (with retry)
    ├── reviewer.py               ← Per-field scoring against CP1 rubric → pass/fail
    │
    └── tools/
        ├── __init__.py           ← Package marker
        ├── problem_definer.py    ← Tool 1: Fields 1-2 (Problem Statement + Target Users)
        ├── solution_architect.py ← Tool 2: Fields 3-4 (Autonomy Loop Plan + Tools & APIs)
        ├── idea_challenger.py    ← Tool 3: Devil's advocate critique
        └── submission_writer.py  ← Tool 4: Compiles all 6 fields using challenger insights
```

**main.py** is UI only. It renders tabs (Per-Field View, Full Draft, Agent Reasoning, Raw Outputs), validation badges, score dashboard, and educational content. Do NOT put agent logic, LLM calls, or tool functions here.

**agent/loop.py** is the core autonomy loop. It orchestrates THINK → PLAN → EXECUTE → REVIEW → UPDATE. It imports planner, executor, and reviewer — nothing else. Do NOT modify its structure. This is the universal agent architecture.

**agent/planner.py** creates a JSON action plan with 4 steps. It knows what tools are available (AVAILABLE_TOOLS list). To add a new tool, add it here first.

**agent/executor.py** routes each plan step to the correct tool function. Information chaining: problem_definer → solution_architect → idea_challenger → submission_writer. Each tool gets progressively more context. Includes retry logic with exponential backoff.

**agent/reviewer.py** scores each of the 6 CP1 fields individually (1-10) and returns per-field status (pass/needs_work/fail). Returns overall score. PASS_THRESHOLD = 7.

**agent/tools/problem_definer.py** — Tool 1. Generates Field 1 (Problem Statement) and Field 2 (Target Users). Only needs the idea as input (first in the chain).

**agent/tools/solution_architect.py** — Tool 2. Generates Field 3 (Autonomy Loop Plan) and Field 4 (Tools & APIs). Takes idea + problem analysis.

**agent/tools/idea_challenger.py** — Tool 3. Devil's advocate that finds Fatal Flaws, Blind Spots, Hard Judge Questions, and Strengthening Recommendations. Takes idea + problem + solution.

**agent/tools/submission_writer.py** — Tool 4. ADDRESSES the challenger critique and compiles all 6 CP1 fields. Takes idea + problem + solution + challenger output. Always runs last.

## 4. The One Rule

**THE LOOP NEVER CHANGES. THE TOOLS DO.**

`agent/loop.py` stays the same no matter what domain the agent is for. To change what the agent does — from CP1 drafting to customer support to invoice processing — you only change the files in `agent/tools/`, update `AVAILABLE_TOOLS` in `planner.py`, update the routing in `executor.py`, and adjust the review criteria in `reviewer.py`.

This constraint is intentional. It teaches students that ALL autonomous agents — regardless of domain — follow the exact same 5-step loop: understand the goal, plan the work, execute tools, evaluate quality, self-correct. The domain-specific work lives in the tools. The autonomy architecture is universal.

## 5. How to Change the Domain

Step-by-step process:
1. **Rewrite tool files** in `agent/tools/` for your new domain
2. **Update `AVAILABLE_TOOLS`** in `planner.py` with new tool names and descriptions
3. **Update `elif` branches** in `executor.py` to route to your new tools
4. **Update review criteria** in `reviewer.py` to match your new output format
5. **Do NOT touch `loop.py`** — the autonomy loop is domain-independent

| Current Tool | Customer Support Agent | Invoice Processor | Sales Lead Qualifier |
|---|---|---|---|
| `problem_definer` | `ticket_classifier` | `invoice_parser` | `lead_scorer` |
| `solution_architect` | `response_generator` | `line_item_validator` | `company_researcher` |
| `idea_challenger` | `tone_checker` | `discrepancy_finder` | `objection_predictor` |
| `submission_writer` | `resolution_summary` | `approval_report` | `outreach_draft` |

## 6. Copy-Paste Prompts for GitHub Copilot / Claude Code

### Prompt 1: Change the domain
```
Change this from a CP1 submission drafter to a customer support agent. Keep loop.py
exactly the same. Replace the 4 tools:
- problem_definer.py → ticket_classifier.py (classify the support ticket)
- solution_architect.py → response_generator.py (draft a response)
- idea_challenger.py → tone_checker.py (verify tone is professional and empathetic)
- submission_writer.py → resolution_summary.py (write the final resolution)
Update AVAILABLE_TOOLS in planner.py, the elif branches in executor.py, and the
review criteria in reviewer.py. Do not change loop.py or main.py structure.
```

### Prompt 2: Add a new tool
```
Add a new tool called market_validator to the agent. Create a new file
agent/tools/market_validator.py with a run(idea, problem_analysis, client, model)
function that asks the LLM to validate market size claims and identify 3 real
competitors. Add it to AVAILABLE_TOOLS in planner.py. Add an elif branch in
executor.py that routes to it. Make it run as step 3 (after solution_architect,
before idea_challenger). Do not change loop.py.
```

### Prompt 3: Make the reviewer stricter
```
In agent/reviewer.py, change PASS_THRESHOLD from 7 to 9. Update the scoring
criteria to require: all 6 fields present with minimum char lengths met,
autonomy explanation with all 5 steps mapped, specific target users (not generic),
and challenger critique fully addressed. Do not change any other file.
```

### Prompt 4: Change output to CP2 demo script
```
Change submission_writer.py to output a CP2 demo script instead of a CP1 draft.
Replace the 6 field sections with: Demo Flow (step by step what to show),
Talking Points (what to say at each step), Live Demo Checklist (what must work),
Backup Plan (what to do if the demo breaks), and Key Metrics to Highlight.
Keep the run() function signature the same. Do not change loop.py.
```

### Prompt 5: Rebrand the UI
```
Change the UI title and branding in main.py from "StudAI LaunchPad" to
"[Your Product Name]". Update the header, page title, sidebar text, and
placeholder example to match your product. Keep the tab structure, step card
rendering, log box, and callback structure exactly the same.
```

### Prompt 6: Remove the challenger and go back to 3 tools
```
Remove idea_challenger.py from the pipeline. Update AVAILABLE_TOOLS in planner.py
to remove it (3 tools). Remove its elif branch in executor.py. Update
submission_writer.py to remove the challenger_critique parameter. Keep loop.py
the same. This simplifies the pipeline for simpler domains.
```

## 7. What NOT to Change

- **`loop.py` structure** — The 5-step loop (THINK → PLAN → EXECUTE → REVIEW → UPDATE) must remain intact. This is the universal autonomous agent pattern.
- **Callback pattern** — `on_step(step, status)` and `on_log(message)` must keep their signatures. The UI depends on these exact callbacks.
- **Function signatures** — All tool files must keep `run(...) -> str`. The planner must keep `create_plan(idea, feedback, client, model) -> list`. The executor must keep `run_plan(plan, idea, client, model, on_log) -> dict`.

## 8. Running the Project

```bash
pip install -r requirements.txt
cp .env.example .env       # paste your Groq API key
streamlit run main.py
```

## 9. StudAI Foundry Hackathon Connection

This repo is the **foundation** for StudAI Foundry — the national autonomous AI hackathon organised by [StudAI One](https://studai.one) in partnership with SRMIST and Startup Singam.

Students clone this repo in the LaunchPad workshop, understand the autonomy loop, then vibe-code it into their own product using the tools and prompts above. After 10 days of building, they submit a startup-ready autonomous AI product to the hackathon.

Each Foundry track can be built by swapping the tools in this repo:

| Foundry Track | Tool 1 | Tool 2 | Tool 3 | Tool 4 |
|---|---|---|---|---|
| HealthTech | `symptom_analyser` | `risk_scorer` | `assumption_checker` | `care_plan_writer` |
| EdTech | `learning_gap_finder` | `curriculum_matcher` | `difficulty_calibrator` | `study_plan_writer` |
| FinTech | `expense_categoriser` | `budget_scorer` | `risk_flagger` | `savings_plan_writer` |
| AgriTech | `crop_analyser` | `yield_predictor` | `weather_validator` | `farm_plan_writer` |
| LegalTech | `clause_extractor` | `risk_flagger` | `precedent_checker` | `summary_writer` |
| Social Impact | `need_identifier` | `impact_scorer` | `feasibility_checker` | `proposal_writer` |

**The loop stays the same. The tools change. That's the lesson.**

## 10. Advanced: Adding Real Internet Access (MCP)

The current tools use the LLM's training knowledge only — no live internet access. For students who want to level up during build week:

**Day 2-5: Add Tavily web search**
```
Add a new tool called web_researcher.py that uses the Tavily API (free tier)
to search the internet for real market data and competitor info. Install tavily-python.
Pass the search results into problem_definer so it uses real data instead of
LLM knowledge. Add TAVILY_API_KEY to .env.example.
```

**Day 5-10: Add MCP (Model Context Protocol)**
MCP is Anthropic's protocol that lets AI agents connect to external services (web search, databases, Google Sheets, browser automation) through a standard interface. Think of it like USB for AI agents. Students who add MCP-based tools will stand out at the finale.

**The loop stays the same. The tools get more powerful.**
