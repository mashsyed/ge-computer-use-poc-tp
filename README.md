# 🚀 Gemini Computer Use Generalized Adaptive Platform

An end-to-end, site-agnostic Web Automation Platform powered by **Gemini 3.8 Flash** and **Playwright**.

---

## 🌟 Key Architecture & Capabilities

```text
                        ┌──────────────────────────────┐
                        │   User Enters URL & Prompt   │
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │ Has URL Been Visited Before? │
                        └──────┬───────────────┬───────┘
                               │ NO            │ YES
                               │               │
                               │        ┌──────▼────────────────┐
                               │        │  Has the UI Changed?  │
                               │        └─┬───────────────────┬─┘
                               │          │ YES               │ NO
                               │          │ (Self-Healing)    │ (Fast-Path)
                               │          │                   │
                        ┌──────▼──────────▼─────┐       ┌─────▼────────────────┐
                        │  Gemini 3.8 Flash     │       │ Cached Playwright    │
                        │  Computer Use (Vision)│       │ DOM Actions          │
                        └──────────────┬────────┘       └─────┬────────────────┘
                                       │                      │
                        ┌──────────────▼────────┐             │
                        │ Update Site Cache     │             │
                        │ & UI Fingerprint      │             │
                        └──────────────┬────────┘             │
                                       │                      │
                        ┌──────────────▼──────────────────────▼┐
                        │ Itemized Token & Cost Tracker Output │
                        └──────────────────────────────────────┘
```

1. **Smart Decision Engine**: Automatically evaluates whether a target website has been visited before and whether its UI layout has changed.
2. **Zero-Token Fast-Path Execution**: On unchanged site visits, executes stored Playwright actions directly in sub-seconds for **$0.00 USD**.
3. **Dual-Layer UI Fingerprinting**: Combines structural DOM HTML tag hashing with visual screenshot hashing to detect layout changes, popups, and shifting form fields.
4. **Self-Healing Automation**: If a target website updates its UI layout, Gemini 3.8 Flash Computer Use visually re-locates elements, completes the task, and automatically updates the site cache.
5. **Itemized Cost & Token Accounting**: Step-by-step cost breakdown including input tokens, output tokens, and USD cost per run.
6. **Interactive Web UI Dashboard**: Local web interface for initiating web tasks, monitoring execution badges, and inspecting live logs.

---

## 📂 Project Structure

- `app.py`: Main CLI entry point.
- `adaptive_agent.py`: Core Smart Decision Engine and Playwright/Gemini integration.
- `ui_fingerprint.py`: Structural DOM tag hashing and screenshot visual comparison.
- `script_cache.py`: JSON cache manager storing learned Playwright actions under `./site_cache/`.
- `cost_tracker.py`: Token usage and itemized cost accounting module.
- `web_dashboard.py`: Interactive Web Dashboard server running at `http://localhost:8501`.

---

## 🛠️ Quick Start

### 1. Installation

```bash
git clone https://github.com/mashsyed/ge-computer-use-poc-tp.git
cd ge-computer-use-poc-tp
pip install -r requirements.txt
playwright install chromium
```

### 2. Authentication

Authenticate with Google Cloud:

```bash
gcloud auth application-default login
```

### 3. Run Web Dashboard

Launch the interactive web UI:

```bash
python web_dashboard.py
```

Open **`http://localhost:8501`** in your browser to enter target URLs, task prompts, and run automations.

### 4. Run via CLI

Run directly from terminal:

```bash
python app.py \
  --url "https://www.soapdetailing.com/" \
  --prompt "Click on Book Now, select Polish and Sealer, select Regular, click Add"
```

---

## 📊 Example Fast-Path Output ($0.00 Cost)

```text
🎯 [SMART DECISION ENGINE]: UI layout is unchanged (100% Match).
🚀 Fast-Path Activated: Executing zero-token cached Playwright actions!

==================================================================================
             📊 ITEMIZED COST BREAKDOWN (https://www.soapdetailing.com/)            
==================================================================================
Step / Action              | Type           | In Tokens | Out Tokens | Cost (USD)
----------------------------------------------------------------------------------
----------------------------------------------------------------------------------
TOTALS                     | ALL STEPS      | 0         | 0          | $0.000000
💡 Estimated Cost per 1,000 Runs: $0.00 USD
==================================================================================
```
