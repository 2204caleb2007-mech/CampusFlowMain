# 🎓 CampusFlow — Multi-Domain Autonomous Campus Agent

```
  ╔═══════════════════════════════════════════════════════════════════╗
  ║                                                                   ║
  ║                C A M P U S F L O W  A G E N T                     ║
  ║    A production-ready MCP-compliant autonomous campus assistant   ║
  ║                                                                   ║
  ╚═══════════════════════════════════════════════════════════════════╝
```

---

## 📋 Table of Contents

- [What Is This?](#-what-is-this)
- [Key Features](#-key-features)
- [System Architecture (MCP)](#-system-architecture-mcp)
- [The 5-Step Autonomous Engine](#-the-5-step-autonomous-engine)
- [Installation Guide](#-installation-guide)
- [Running the App](#-running-the-app)
- [Role-Based Access Control](#-role-based-access-control)
- [Troubleshooting](#-troubleshooting)

---

## 🧠 What Is This?

**CampusFlow** is a stateful, robust, and production-ready autonomous AI agent designed to manage campus operations. Instead of a standard chatbot, CampusFlow acts as a fully self-correcting agent that can book labs, process leave requests, resolve IT complaints, and modify campus databases—all through natural language.

By implementing the **Model Context Protocol (MCP)**, the underlying tools are cleanly separated from the AI orchestrator, ensuring a standardized, modular, and highly reliable system.

---

## ✨ Key Features

- **MCP Architecture:** Core tools are exposed via a standalone FastMCP server, allowing the LLM orchestrator to communicate via standardized JSON-RPC protocols. Built-in automatic fallbacks ensure zero downtime if the server goes offline.
- **Natural Language Data Editing:** Teachers and Admins can update Student Attendance or Lab Timetables directly via chat (e.g., *"Mark STU002 present today"* or *"Schedule CS Lab 1 on Friday from 10 to 12"*).
- **Self-Correcting Loop:** A true `MAX_RETRIES=3` autonomous loop (THINK → PLAN → EXECUTE → REVIEW → UPDATE). The agent reviews its own work against strict campus policies and retries automatically if it fails.
- **Role-Based Security:** Granular access control for Students, Teachers, and Admins. Students have read-only access to their isolated data, while Teachers/Admins can modify records.
- **Stateful Persistence:** All chats, logs, requests, and metrics are stored locally in a robust SQLite database (`campusflow.db`).
- **PDF Exporting:** Users can generate and download fully formatted PDF documents of their conversation history using natural language commands.
- **Modern Flexbox UI:** A highly polished Streamlit graphical interface featuring glowing cards, live autonomous loop tracking, and collapsible system logs.

---

## 🏗️ System Architecture (MCP)

CampusFlow operates using a decoupled **Model Context Protocol (MCP)** architecture:

```
  ┌──────────────┐
  │   Streamlit  │
  │   Web UI     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │     LLM      │
  │ Orchestrator │ (Interprets intent, checks DB)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │   Executor   │ (Runs the THINK->PLAN->EXECUTE loop)
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  MCP Client  │ (Routes tool calls / Auto-fallbacks)
  └──────┬───────┘
         │ HTTP / POST
         ▼
  ┌──────────────┐
  │  MCP Server  │ (FastMCP exposed endpoints)
  └──────┬───────┘
         │
  ┌──────┴───────┬──────────────┬──────────────┐
  ▼              ▼              ▼              ▼
 Classifier    Policy     Availability    Notifier
   Tool        Engine      Checker         Tool
```

---

## 🔄 The 5-Step Autonomous Engine

Every complex request goes through our rigorous autonomous evaluation loop:

| Step | What Happens | Why It Matters |
|------|-------------|---------------|
| **THINK** | Parses the student query + extracts entities | Context awareness — understands dates, IDs, and rooms. |
| **PLAN** | Generates a JSON action plan for the tools | Self-direction — the agent sequences its own workflow. |
| **EXECUTE** | Dispatches requests to the MCP Server | Information chaining — tools feed data to one another. |
| **REVIEW** | Evaluates the output against strict policies | **This is autonomy** — scores the logic quality out of 10. |
| **UPDATE** | Self-corrects and tries again if Score < 7 | Directed self-correction, not blind guessing. |

---

## 💻 Installation Guide

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | Version 3.10 or higher |
| **Groq API Key** | Free. Get it at [console.groq.com](https://console.groq.com) |

### Step 1: Clone and Install

```bash
git clone <your-repo-url>
cd CampusFlow
pip install -r requirements.txt
cp .env.example .env
```

### Step 2: Configure Secrets

Open the `.env` file and add your actual API keys:

```ini
GROQ_API_KEY=gsk_your_actual_key_here
TAVILY_API_KEY=tvly_your_actual_key_here
```

---

## ▶️ Running the App

CampusFlow requires two separate processes to run simultaneously. Open two terminal windows.

**Terminal 1 — Start the MCP Server:**
```bash
python mcp_server/server.py --host 127.0.0.1 --port 8765
```

**Terminal 2 — Start the Streamlit App:**
```bash
python -m streamlit run main.py
```

The app will automatically open in your browser at **http://localhost:8501**.

---

## 🔐 Role-Based Access Control

The UI handles distinct operations based on your logged-in role. 

*Initial default accounts (Password for all: `12345678`)*:

*   **Admin (`admin`)**: Can view all campus chats, modify global timetables, and override any student attendance.
*   **Teacher (`teacher_01`)**: Can modify lab timetables and take attendance. Views only their own chat history.
*   **Student (`STU001` - `STU010`)**: Can book labs, query their own attendance, request leave, and file complaints. Read-only limits enforce system safety.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| **`ModuleNotFoundError: No module named 'fastmcp'`** | Run `pip install fastmcp` or `pip install -r requirements.txt`. |
| **"Failed to connect to MCP Server" logs** | Ensure Terminal 1 is running the server. Note: The app will continue to function via direct auto-fallbacks! |
| **"API key missing" error** | Paste your Groq key into the sidebar config menu, or ensure `.env` is loaded. |
| **Attendance CSV not updating** | Ensure you are logged in as a **Teacher** or **Admin**, otherwise writes are strictly rejected. |

---

**Built using Python, Streamlit, and the Model Context Protocol.**
