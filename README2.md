# 🚀 StudAI LaunchPad — CP1 Submission Drafter

> **The official workshop product for [StudAI Foundry](https://studai.one) — India's national autonomous AI systems hackathon**
>
> Organised by **StudAI One × SRMIST × Startup Singam** | Prize pool: **INR 1,00,000+**

```
  ╔═══════════════════════════════════════════════════════════════════╗
  ║                                                                   ║
  ║      ███████╗████████╗██╗   ██╗██████╗  █████╗ ██╗               ║
  ║      ██╔════╝╚══██╔══╝██║   ██║██╔══██╗██╔══██╗██║               ║
  ║      ███████╗   ██║   ██║   ██║██║  ██║███████║██║               ║
  ║      ╚════██║   ██║   ██║   ██║██║  ██║██╔══██║██║               ║
  ║      ███████║   ██║   ╚██████╔╝██████╔╝██║  ██║██║               ║
  ║      ╚══════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝               ║
  ║                                                                   ║
  ║              L A U N C H P A D                                    ║
  ║       CP1 Submission Drafter — Autonomous AI Agent                ║
  ║                                                                   ║
  ╚═══════════════════════════════════════════════════════════════════╝
```

---

## 📋 Table of Contents

- [What Is This?](#-what-is-this)
- [Chatbot vs Autonomous Agent](#-chatbot-vs-autonomous-agent)
- [How the Autonomous Loop Works](#-how-the-autonomous-loop-works)
- [The 4-Tool Pipeline](#-the-4-tool-pipeline)
- [Project Architecture](#-project-architecture)
- [Installation Guide](#-installation-guide)
- [Running the App](#-running-the-app)
- [What You Will See](#-what-you-will-see)
- [Troubleshooting](#-troubleshooting)
- [How to Extend for Your Foundry Project](#-how-to-extend-for-your-foundry-project)
- [Tech Stack](#-tech-stack)
- [Hackathon Timeline](#-hackathon-timeline)
- [Deployment](#-deployment)

---

## 🧠 What Is This?

This is an **autonomous AI agent** that drafts your **CP1 (Checkpoint 1) submission** for the StudAI Foundry hackathon. You give it one input — your project idea. The agent does the rest:

1. **Defines** the core problem and target users (Fields 1-2)
2. **Architects** the solution with autonomy loop plan and tech stack (Fields 3-4)
3. **Challenges** the idea like a devil's advocate — finds blind spots and hard judge questions
4. **Writes** all 6 CP1 fields — ADDRESSING the challenger's critique to make the submission stronger
5. **Reviews** each field individually against the CP1 rubric (per-field scores)
6. **Self-corrects** if the draft isn't submission-ready — and tries again

The final output gives you **per-field copy boxes** you can paste directly into the CP1 submission form, a **score dashboard** showing which fields passed, and the **devil's advocate analysis** that made your submission stronger.

> **This was built for the StudAI LaunchPad workshop** — the official kickoff of StudAI Foundry. Students clone this repo, run it, watch the autonomous loop draft their CP1 live, then use AI coding tools to modify it for their own hackathon project.

---

## 🤖 Chatbot vs Autonomous Agent

This is the core concept taught in the workshop. Understanding this difference is **the entire point**.

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║                         CHATBOT                                  ║
  ║                                                                  ║
  ║    User Input ──→ LLM Call ──→ Output ──→ Done.                  ║
  ║                                                                  ║
  ║    • One shot — whatever the LLM returns, you get                ║
  ║    • No quality check                                            ║
  ║    • No self-correction                                          ║
  ║    • The user must judge if the output is good                   ║
  ╚══════════════════════════════════════════════════════════════════╝

  ╔══════════════════════════════════════════════════════════════════╗
  ║                    AUTONOMOUS AGENT                              ║
  ║                                                                  ║
  ║    User gives a GOAL                                             ║
  ║      │                                                           ║
  ║      ▼                                                           ║
  ║    ┌──────────────────────────────────────────────┐              ║
  ║    │  THINK ──→ PLAN ──→ EXECUTE ──→ REVIEW       │              ║
  ║    │    ▲                              │           │              ║
  ║    │    │         ┌────────────────────┘           │              ║
  ║    │    │         ▼                                │              ║
  ║    │    │    Score < 7?                            │              ║
  ║    │    │     YES → UPDATE (carry feedback) ───┐   │              ║
  ║    │    │      NO → DELIVER result             │   │              ║
  ║    │    │                                      │   │              ║
  ║    │    └──────────────────────────────────────┘   │              ║
  ║    └──────────────────────────────────────────────┘              ║
  ║                                                                  ║
  ║    • Agent decides what to do (PLAN)                             ║
  ║    • Agent runs 4 tools in sequence (EXECUTE)                    ║
  ║    • Agent judges each field (REVIEW)    ← THIS IS KEY           ║
  ║    • Agent improves on retry (UPDATE)                            ║
  ║    • Up to 3 loops — no human in the loop                        ║
  ╚══════════════════════════════════════════════════════════════════╝
```

**The REVIEW step is what makes it autonomous.** A chatbot accepts any output. An autonomous agent evaluates its own work, decides if it's good enough, and self-corrects if it's not.

---

## 🔄 How the Autonomous Loop Works

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                  THE 5-STEP AUTONOMY LOOP                       │
  │                                                                 │
  │   ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐      │
  │   │  THINK  │──→│  PLAN   │──→│ EXECUTE  │──→│ REVIEW  │      │
  │   │         │   │         │   │          │   │         │      │
  │   │ Parse   │   │ Create  │   │ Run 4    │   │ Score   │      │
  │   │ goal +  │   │ JSON    │   │ tools in │   │ each    │      │
  │   │ feedback│   │ action  │   │ sequence │   │ field   │      │
  │   └─────────┘   │ plan    │   └──────────┘   └────┬────┘      │
  │       ▲         └─────────┘                       │            │
  │       │                                           ▼            │
  │       │                                    ┌────────────┐      │
  │       │                                    │ Score >= 7? │      │
  │       │                                    └──────┬─────┘      │
  │       │                                    YES│   │NO          │
  │       │                                       │   ▼            │
  │       │                                       │ ┌────────┐    │
  │       │                                       │ │ UPDATE │    │
  │       │                                       │ │ Carry  │    │
  │       │                                       │ │feedback│    │
  │       │                                       │ └───┬────┘    │
  │       │                                       │     │          │
  │       └───────────────────────────────────────┼─────┘          │
  │                                               │                │
  │                                               ▼                │
  │                                        ┌────────────┐          │
  │                                        │  DELIVER   │          │
  │                                        │  Results   │          │
  │                                        └────────────┘          │
  └─────────────────────────────────────────────────────────────────┘
                        Max 3 loops
```

### What each step does:

| Step | What Happens | Why It Matters |
|------|-------------|---------------|
| **THINK** | Parses the idea + feedback from previous loops | Context awareness — the agent gets smarter each retry |
| **PLAN** | LLM generates a JSON action plan: `[{step, tool, reason}]` | Self-direction — the agent decides its own workflow |
| **EXECUTE** | Runs 4 tools: define → architect → challenge → write | **Information chaining** — each tool builds on the previous |
| **REVIEW** | Scores each of 6 CP1 fields individually 1-10 | **This is autonomy** — per-field quality judgment |
| **UPDATE** | Carries field-specific feedback into the next loop | Directed self-correction, not blind retry |

---

## 🔗 The 4-Tool Pipeline

What makes this submission drafter powerful is the **4-tool pipeline** — especially the devil's advocate.

```
  ┌────────────────┐      ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
  │  Tool 1         │      │  Tool 2         │      │  Tool 3         │      │  Tool 4         │
  │  PROBLEM        │      │  SOLUTION       │      │  IDEA           │      │  SUBMISSION     │
  │  DEFINER        │─────→│  ARCHITECT      │─────→│  CHALLENGER     │─────→│  WRITER         │
  │                 │      │                 │      │                 │      │                 │
  │  Field 1:       │      │  Field 3:       │      │  • Fatal flaws  │      │  All 6 fields   │
  │  Problem        │      │  Autonomy Loop  │      │  • Blind spots  │      │  ADDRESSING     │
  │  Statement      │      │  Plan           │      │  • Hard judge   │      │  the critique   │
  │                 │      │                 │      │    questions    │      │                 │
  │  Field 2:       │      │  Field 4:       │      │  • How to      │      │  Fields 5-6:    │
  │  Target Users   │      │  Tools & APIs   │      │    strengthen  │      │  Eval Logic +   │
  │                 │      │                 │      │                 │      │  Expected Output│
  └────────────────┘      └────────────────┘      └────────────────┘      └────────────────┘
       ▲                                                                         │
       │                                                                         │
       └─── Input: just the idea                                 Output: copy-paste CP1 ───┘
```

**Why the Challenger matters:** Without it, the agent produces optimistic output that tells students what they want to hear. The devil's advocate forces the submission to address hard questions BEFORE judges ask them. The submission writer then incorporates those answers — making the final draft significantly stronger than a naive first attempt.

---

## 🏗️ Project Architecture

### File Structure

```
  studai-foundry-launchpad/
  │
  ├── 📄 CLAUDE.md              ← Project brain for AI coding tools (Copilot/Claude)
  ├── 📄 README.md              ← You are here
  ├── 📄 requirements.txt       ← 3 dependencies: groq, streamlit, python-dotenv
  ├── 📄 .env.example           ← API key template (copy to .env)
  ├── 📄 .gitignore             ← Excludes .env, __pycache__, secrets
  │
  ├── 🖥️ main.py               ← Streamlit UI — tabs, per-field boxes, score dashboard
  │
  └── 🤖 agent/                 ← THE AUTONOMOUS AGENT
      ├── __init__.py
      ├── 🔄 loop.py            ← THE CORE — the 5-step autonomy loop
      ├── 📋 planner.py         ← LLM → JSON action plan (4 tools)
      ├── ⚡ executor.py         ← Routes plan steps → tool functions (with retry)
      ├── ✅ reviewer.py         ← Per-field scoring, decides pass/retry
      │
      └── 🔧 tools/             ← DOMAIN-SPECIFIC TOOLS (these change)
          ├── __init__.py
          ├── problem_definer.py   ← Tool 1: Fields 1-2 (Problem + Users)
          ├── solution_architect.py← Tool 2: Fields 3-4 (Autonomy + Stack)
          ├── idea_challenger.py   ← Tool 3: Devil's advocate critique
          └── submission_writer.py ← Tool 4: All 6 fields (addresses critique)
```

### How Data Flows Through the System

```
  ┌──────────────┐
  │   User       │
  │   enters     │
  │   hackathon  │
  │   idea       │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐         ┌──────────────────────────────────┐
  │   main.py    │────────→│         agent/loop.py            │
  │   (UI only)  │         │    The 5-step autonomy loop      │
  │              │◀────────│    Returns final results dict    │
  └──────────────┘         └───────────────┬──────────────────┘
                                           │
                           ┌───────────────┼───────────────┐
                           ▼               ▼               ▼
                    ┌────────────┐  ┌────────────┐  ┌────────────┐
                    │ planner.py │  │executor.py │  │reviewer.py │
                    │            │  │            │  │            │
                    │ LLM → JSON │  │ Plan → Run │  │ Per-field  │
                    │ action plan│  │ 4 tools    │  │ score 1-10 │
                    └────────────┘  └──────┬─────┘  └────────────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        ▼                  ▼                  ▼
                 ┌────────────┐    ┌────────────┐    ┌────────────┐
                 │  Tool 1    │    │  Tool 2    │    │  Tool 3    │
                 │  problem_  │    │ solution_  │    │   idea_    │
                 │  definer   │───→│ architect  │───→│ challenger │
                 │            │    │            │    │            │
                 │ Fields 1-2 │    │ Fields 3-4 │    │ Critique   │
                 └────────────┘    └────────────┘    └──────┬─────┘
                                                           │
                                                           ▼
                                                    ┌────────────┐
                                                    │  Tool 4    │
                                                    │ submission │
                                                    │  _writer   │
                                                    │            │
                                                    │ All 6      │
                                                    │ fields +   │
                                                    │ addresses  │
                                                    │ critique   │
                                                    └──────┬─────┘
                                                           │
                                                           ▼
                                                    ┌────────────┐
                                                    │  Per-field │
                                                    │  copy boxes│
                                                    │  + score   │
                                                    │  dashboard │
                                                    └────────────┘
```

### Information Chaining Between Tools

```
  Tool 1: problem_definer
    Input:  idea
    Output: Problem Statement + Target Users
              │
              ▼
  Tool 2: solution_architect
    Input:  idea + problem_definer output
    Output: Autonomy Loop Plan + Tools & APIs
              │
              ▼
  Tool 3: idea_challenger
    Input:  idea + problem_definer + solution_architect output
    Output: Fatal flaws, blind spots, hard questions, recommendations
              │
              ▼
  Tool 4: submission_writer
    Input:  idea + ALL previous outputs (including challenger)
    Output: All 6 CP1 fields — with critique addressed
```

> **Why the devil's advocate matters:** The same LLM can argue FOR and AGAINST an idea when prompted differently. The agent uses BOTH perspectives to produce a balanced, stronger submission. This is multi-perspective AI — a key concept for the hackathon.

---

## 💻 Installation Guide

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | Version 3.10 or higher |
| **pip** | Comes with Python |
| **Groq API Key** | Free — no credit card needed |
| **Internet** | Required for LLM API calls |
| **Browser** | Any modern browser (Chrome, Firefox, Edge, Safari) |

### Step 1: Get Your Free Groq API Key

1. Go to **[console.groq.com](https://console.groq.com)**
2. Sign up with Google or email (takes 30 seconds)
3. Click **API Keys** in the left sidebar
4. Click **Create API Key**
5. Copy the key — it looks like: `gsk_xxxxxxxxxxxxxxxxxxxx`
6. Save it somewhere — you'll paste it in Step 3

> **Why Groq?** It's free (14,400 requests/day), fast (300+ tokens/sec), and uses Llama 3.3 70B — a powerful open-source model. Students see results instantly, which is critical for workshop demos.

### Step 2: Clone and Install

#### On Windows (Command Prompt or PowerShell)

```bash
git clone https://github.com/studaiedutech-ui/studai-foundry-launchpad.git
cd studai-foundry-launchpad
pip install -r requirements.txt
copy .env.example .env
```

#### On macOS / Linux (Terminal)

```bash
git clone https://github.com/studaiedutech-ui/studai-foundry-launchpad.git
cd studai-foundry-launchpad
pip install -r requirements.txt
cp .env.example .env
```

> **What gets installed:** Only 3 packages — `groq` (LLM client), `streamlit` (web UI), `python-dotenv` (reads .env files). No heavy frameworks.

### Step 3: Add Your API Key

Open the `.env` file in any text editor and replace the placeholder:

```
# Before:
GROQ_API_KEY=your_groq_api_key_here

# After:
GROQ_API_KEY=gsk_your_actual_key_here
```

> **Alternatively**, you can paste the key directly in the app's sidebar — no `.env` file needed.

### Step 4: Verify Installation

```bash
python -c "from agent import loop; print('All imports OK')"
```

If you see `All imports OK`, you're ready to run.

---

## ▶️ Running the App

```bash
streamlit run main.py
```

The app opens automatically in your browser at **http://localhost:8501**.

### How to Use:

1. **Paste your Groq API key** in the sidebar (or set it in `.env`)
2. **Type your hackathon idea** in the text box — be specific! (or click **💡 Try Example**)
3. **Click 🚀 Draft My CP1** — watch the 5 step cards light up in real time
4. **View per-field results** — each field has a copy box with validation badges
5. **Check the score dashboard** — see which fields passed and which need work
6. **Explore the Agent Reasoning tab** — see the devil's advocate critique
7. **Download** the full draft as markdown

---

## 👀 What You Will See

When you click **Draft My CP1**, the agent works autonomously through 4 tabs:

### Tab 1: Per-Field View
Each CP1 field gets its own copy box with:
- Validation badge (✅/❌) with character count
- Text input or textarea matching the actual CP1 form type
- Field reference table at the bottom

### Tab 2: Full Draft
The complete submission as formatted markdown with a download button.

### Tab 3: Agent Reasoning
- **4-tool pipeline visualization** — see how data flows through the agent
- **Devil's advocate critique** — the weaknesses found and addressed
- **Loop count** — how many self-correction cycles the agent used

### Tab 4: Raw Outputs
Individual outputs from each of the 4 tools — for learning how autonomous agents chain information.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| **`ModuleNotFoundError: No module named 'groq'`** | Run `pip install -r requirements.txt` again |
| **`ModuleNotFoundError: No module named 'agent'`** | Make sure you're in the `studai-foundry-launchpad/` directory when running |
| **"API key missing" error in the app** | Paste your Groq key in the sidebar, or check your `.env` file |
| **"Rate limited" error** | Wait 60 seconds and try again. Free tier has per-minute limits. |
| **"Model error"** | Switch to a different model in the sidebar dropdown |
| **App doesn't open in browser** | Go to `http://localhost:8501` manually |
| **`streamlit: command not found`** | Try `python -m streamlit run main.py` instead |
| **Python version error** | Make sure you're using Python 3.10+: `python --version` |
| **Port 8501 already in use** | Run `streamlit run main.py --server.port 8502` |
| **Stuck on "Agent is working..."** | Check your internet connection — Groq API needs internet |

---

## 🛠️ How to Extend for Your Foundry Project

This repo is your **foundation**. The product you submit to StudAI Foundry is whatever you build on top of it.

### The One Rule

```
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║       THE LOOP NEVER CHANGES. THE TOOLS DO.           ║
  ║                                                       ║
  ║   loop.py  → KEEP IT          (same for every agent)  ║
  ║   tools/   → CHANGE THESE     (your domain goes here) ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
```

### How to Vibe Code Your Own Agent

1. Open the project in **VS Code** with **GitHub Copilot** (or use **Claude Code**)
2. Read `CLAUDE.md` — it explains every file and has **6 ready-to-paste prompts**
3. Paste this into Copilot Chat:

```
I want to build [your idea]. Keep loop.py exactly the same.
Change the 4 tools in agent/tools/ so this agent does [your domain]
instead of CP1 drafting. Update planner.py's AVAILABLE_TOOLS
list and executor.py's routing to match the new tools.
```

### What to Change for Different Domains

```
  ┌─────────────────────┬──────────────────────┬─────────────────────────┐
  │  Current Tool            │  Customer Support    │  Invoice Processor      │
  ├─────────────────────┼──────────────────────┼─────────────────────────┤
  │ problem_definer      │ ticket_classifier    │ document_parser         │
  │ solution_architect   │ knowledge_search     │ line_item_extractor     │
  │ idea_challenger      │ tone_checker         │ discrepancy_finder      │
  │ submission_writer    │ response_drafter     │ approval_report         │
  ├─────────────────────┼──────────────────────┼─────────────────────────┤
  │  Files to change: tools/, planner.py (AVAILABLE_TOOLS),              │
  │  executor.py (elif branches), reviewer.py (scoring criteria)         │
  │                                                                       │
  │  Files to KEEP:  loop.py, main.py                                    │
  └───────────────────────────────────────────────────────────────────────┘
```

### Example Prompts for Copilot / Claude Code

See `CLAUDE.md` for 6 detailed ready-to-paste prompts, including:
- Change domain (e.g., customer support, sales qualifier)
- Add a new tool to the pipeline
- Make the reviewer stricter
- Change the output format for CP2 demo
- Update branding
- Simplify back to 3 tools

---

## ⚙️ Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **LLM Provider** | [Groq API](https://console.groq.com) | Free tier (14,400 req/day), 300+ tokens/sec, no credit card |
| **LLM Model** | Llama 3.3 70B Versatile | Fast, capable, free — perfect for live demos |
| **UI Framework** | [Streamlit](https://streamlit.io) | Zero frontend knowledge needed, live updates native |
| **Language** | Python 3.10+ | Students already know the basics |
| **Dependencies** | `groq`, `streamlit`, `python-dotenv` | **3 packages only** — no bloat |

```
  No database.
  No authentication.
  No external services beyond Groq.
  No framework dependencies (no LangChain, no CrewAI).
  Pure Python agent — students can read every line.
```

---

## 📅 Hackathon Timeline — StudAI Foundry

```
  March 19  ──── 🎓 StudAI LaunchPad Workshop
                    Clone this repo, run the demo, start building
                    │
  March 21  ──── 🔨 Build week starts
                    Use Copilot/Claude Code to vibe-code your agent
                    │
  March 23  ──── 📋 CP1 Deadline (11:59 PM IST)
                    Submit: idea + architecture + initial prototype
                    │
  March 25  ──── 🎥 CP2 — Working Demo
                    Show your agent running live
                    │
  March 26  ──── 🏁 Final Submission
                    Complete product + demo video
                    │
  March 30  ──── 🏆 Grand Finale at SRMIST
                    INR 1,00,000+ prize pool
                    Live demos + judging
```

---

## 🚀 Deployment (Optional)

### Option A: Streamlit Cloud (Free — 3 Steps)

```
  1. Push repo to GitHub (must be public)
            │
            ▼
  2. Go to share.streamlit.io
     Connect your GitHub repo
            │
            ▼
  3. Set GROQ_API_KEY in Secrets
     Click Deploy
            │
            ▼
     Live URL in 2 minutes ✓
     Use this URL for your CP2 demo video
```

### Option B: Run Locally for Demos

```bash
streamlit run main.py
```

Share your screen during the demo. No deployment needed for CP1/CP2.

---

## 🤝 Credits

| | |
|---|---|
| **Built for** | [StudAI Foundry](https://studai.one) — National Autonomous AI Hackathon |
| **Workshop** | StudAI LaunchPad — March 19, 2026 |
| **Organised by** | StudAI One × SRMIST × Startup Singam |
| **Prize Pool** | INR 1,00,000+ |
| **Target Audience** | Engineering students building autonomous AI agents |

---

> **Remember: This repo is not the product. This repo is the foundation. The product is whatever YOU build on top of it in 10 days.**
