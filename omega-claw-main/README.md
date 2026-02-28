# 🦀 Omega Claw

The Constitution-governed agentic orchestration engine.  
Text your phone → agents build your project.

## Part of the Omega Ecosystem

| Repo | Role |
|------|------|
| [omega-constitution](https://github.com/edsworld27/omega-constitution) | The law — governs all agent behavior |
| **omega-claw** (this repo) | The remote control — Telegram → Hive → Agents |
| [omega-store](https://github.com/edsworld27/omega-store) | The marketplace — kits, skills, MCPs |

## Architecture

```
You (Phone) → Telegram → Omega Claw
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         IntentAgent    Orchestrator   Reporter
         (classify)     (onboard +     (hive + job
                         job drop)      history)
              │             │             │
              └──────── SQLite DB ────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          skills/        mcps/        Omega Hive
         (plug &        (plug &       (Claude Code
          play)          play)         picks up jobs)
```

## Quick Start

### 1. Get Your Telegram Credentials (2 minutes)

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, follow prompts, copy the **token**
3. Message **@userinfobot**, copy your **user ID**

### 2. Configure & Run

```bash
cd "Omega Claw v1"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Edit .env with your token and user ID
nano .env

# Run
python main.py
```

### 3. Test It

Message your bot: `start project`
Complete the 4-step wizard, job drops to Hive.

## Commands

| You Text | Bot Does |
|----------|----------|
| `start project` | 4-step onboarding wizard → drops FOUNDER_JOB |
| `status` | Full Hive + job history report |
| `inbox` | Pending Founder Jobs |
| `job history` | Past builds from SQLite |

## Extending Omega Claw

### Skills (Plug-and-Play)
Drop a folder into `skills/` to add new bot capabilities.  
See `skills/_template/` for the blueprint.

### MCPs (Model Context Protocol)
Drop a config into `mcps/` to wire external services into your builds.  
See `mcps/README.md` for the config format.

## Roadmap

- [x] **Phase 1:** Dual-Vector Engine (CLI + GUI)
- [x] **Phase 1.5:** Advanced GUI Landmarks
- [x] **Phase 1.6:** 10m Watchdog & Model Routing
- [ ] **Phase 4:** Ghost Hardening (Active State Detection)
- [ ] **Phase 5:** Omega Hub (Multi-Agent Workspaces)
- [ ] **Phase 6:** AI-to-AI Bridge (Prompter Logic)

## Stack

- **Python 3.9+**
- **python-telegram-bot** (free Telegram interface)
- **PyAutoGUI** (robotic control)
- **PyTesseract** (computer vision)
- **SQLite** (built into Python)
- **Zero LLM APIs** — free forever

## License

Part of the Omega Constitution framework.
