# agents/orchestrator_agent/__init__.py — Omega Claw
from agents.base_agent import BaseAgent
from db.database import create_job
import os
import json
import fcntl
from datetime import datetime
from pathlib import Path
import re

class OrchestratorAgent(BaseAgent):
    """
    The brain of Omega Claw.
    Handles the structured onboarding interview via Telegram,
    then drops a FOUNDER_JOB into the Hive for Claude Code to pick up.
    """
    
    # SECURITY §3.3: Capability Matrix
    AGENT_ROLE = "Structured onboarding wizard + FOUNDER_JOB file writer"
    PERMITTED_INPUTS = ["Telegram text messages via Orchestrator"]
    PERMITTED_OUTPUTS = ["Write .md files to telegram_inbox/", "Write JSON state to telegram_inbox/", "Insert rows into SQLite jobs table"]
    FORBIDDEN_ACTIONS = ["Execute shell commands", "Read files outside hive/", "Send network requests", "Delete files"]
    MAX_BLAST_RADIUS = "Can create .md files in telegram_inbox/ and write to SQLite. Cannot execute code or access network."
    
    def __init__(self):
        super().__init__()
        self.hive_dir = os.path.expanduser(os.getenv(
            "OMEGA_HIVE_DIR",
            "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10/USER SPACE/dev-work/hive"
        ))
        self.telegram_inbox = os.path.join(self.hive_dir, "telegram_inbox")
        self.state_file = os.path.join(self.telegram_inbox, "active_conversations.json")
        
        Path(self.telegram_inbox).mkdir(parents=True, exist_ok=True)
        
        self.questions = [
            {"key": "name",     "prompt": "📝 **Step 1/4: Project Name**\nWhat are we building? (e.g. TaskFlow, CryptoBot)"},
            {"key": "audience", "prompt": "👥 **Step 2/4: Audience & Purpose**\nWho is this for and what is the main goal in one sentence?"},
            {"key": "kit",      "prompt": "🧰 **Step 3/4: Architecture Kit**\nWhich Omega blueprint?\n`website` · `web-app` · `api` · `automation` · `other`"},
            {"key": "mode",     "prompt": "⚙️ **Step 4/4: Autonomy Mode**\nHow should Claude Code operate?\n`1` Full Discovery (strict checkpoints)\n`2` Quick Start (balanced)\n`3` Just Build (max autonomy)"}
        ]

    def _build_registry(self):
        self.registry = {
            "orchestrator:build":  lambda user_text="", **kw: self._handle_build_flow(user_text),
            "orchestrator:status": lambda **kw: self._check_inbox(),
            "orchestrator:cancel": lambda **kw: self._cancel_flow(),
            "orchestrator:install": lambda user_text="", **kw: self._handle_install(user_text),
        }

    # --- State Management (SECURITY §3.7: File locking) ---
    
    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reads
                    data = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
                    return data
            except:
                return {}
        return {}

    def _save_state(self, state):
        with open(self.state_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writes
            json.dump(state, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)

    # --- Flow Logic ---

    def _handle_build_flow(self, user_text: str) -> str:
        state = self._load_state()
        
        # Start a new flow
        if "active" not in state or not state["active"]:
            state = {"active": True, "step": 0, "answers": {}}
            self._save_state(state)
            return f"🚀 **Omega Claw — New Project Setup**\n\n{self.questions[0]['prompt']}\n\n_Reply directly. Type `cancel` to abort._"

        # Cancel check
        if user_text.strip().lower() in ["cancel", "stop", "abort"]:
            return self._cancel_flow()

        # Record answer and advance
        step = state["step"]
        current_q = self.questions[step]
        state["answers"][current_q["key"]] = user_text
        step += 1
        state["step"] = step

        if step < len(self.questions):
            self._save_state(state)
            return self.questions[step]["prompt"]
        
        # Flow complete — generate the job
        answers = state["answers"]
        state = {"active": False, "step": 0, "answers": {}}
        self._save_state(state)
        
        # SECURITY §2.1: Validate project name — allowlist only
        name = answers.get("name", "").strip()
        name = re.sub(r'[^a-zA-Z0-9 _-]', '', name)[:50]
        if not name:
            return "❌ Invalid project name. Use letters, numbers, spaces only."
        answers["name"] = name
        
        return self._generate_founder_job(answers)

    def _generate_founder_job(self, answers: dict) -> str:
        job_id = f"FOUNDER_JOB-{self._get_next_id():03d}"
        slug = self._slugify(answers["name"])
        job_file = os.path.join(self.telegram_inbox, f"{job_id}-{slug}.md")
        
        # Normalize mode
        mode = answers["mode"]
        if "1" in mode or "discovery" in mode.lower(): mode = "FULL DISCOVERY"
        elif "2" in mode or "quick" in mode.lower():   mode = "QUICK START"
        elif "3" in mode or "just" in mode.lower() or "build" in mode.lower(): mode = "JUST BUILD"

        content = f"""# {job_id}: {answers["name"]}

**STATUS**: PENDING
**CREATED**: {datetime.now().isoformat()}
**DELEGATED TO**: Claude Code (Master Orchestrator / Founder)

---

## 🏛️ Constitution Context

- **Kit**: `{answers["kit"]}`
- **Requested Mode**: `{mode}`

## 🎯 The Objective

**Project Name**: {answers["name"]}
**Audience & Purpose**: {answers["audience"]}

---

## 🐝 Hive Execution Instructions

Claude Code, you are the **Founder**.
This is a brand new project dropped from the human pilot's Telegram.

1. Initialize the `SESSION_CONTEXT.md` with the Kit and Mode above.
2. Calculate the required scale for this build.
3. Apply the **Rule of 3**: Spawn 1 Manager for every 1-3 Workers. For every 1-3 Managers, spawn 1 Mega-Manager. This scales infinitely.
4. Set up the nested `USER SPACE/dev-work/hive/` directories.
5. Create the `MANAGER_JOB.md` and `MEGA_JOB.md` files, and the underlying worker `JOB.md` files.
6. Await human confirmation that the Agents have been launched.

---
*Progress will be monitored via the `master-job-board.md`.*
"""
        with open(job_file, 'w') as f:
            f.write(content)
        
        # Log to SQLite
        create_job(job_id, answers["name"], answers["kit"], mode)
        
        return (
            f"✅ **{job_id} Dispatched to Omega!**\n\n"
            f"**Project**: {self._escape_md(answers['name'])}\n"
            f"**Kit**: {self._escape_md(answers['kit'])}\n"
            f"**Mode**: {mode}\n\n"
            f"Claude Code will detect this and begin scaffolding the Hive.\n"
            f"Use `status` to check progress."
        )

    def _cancel_flow(self) -> str:
        self._save_state({"active": False, "step": 0, "answers": {}})
        return "🛑 **Setup Cancelled.** Ready for new commands."

    def _check_inbox(self) -> str:
        if not os.path.exists(self.telegram_inbox):
            return "📋 **Inbox**: Empty"
        jobs = sorted([f for f in os.listdir(self.telegram_inbox) if f.startswith("FOUNDER_JOB") and f.endswith(".md")])
        if not jobs:
            return "📋 **Inbox**: No pending jobs."
        lines = [f"• {j.replace('.md', '')}" for j in jobs]
        return f"📋 **Inbox** ({len(jobs)} jobs)\n\n" + "\n".join(lines)

    def _handle_install(self, user_text: str, user_id: int = None) -> str:
        import shutil
        # parse: "install plugin name"
        query = user_text.lower().replace("install", "").replace("add kit", "").replace("fetch skill", "").replace("get mcp", "").strip()
        if not query:
            return "❌ What would you like to install? Example: `install postgres skill`"
            
        # 1. Check if this is a built-in MCP wizard blueprint
        from core.mcp_wizard import MCP_BLUEPRINTS
        for blueprint_id in MCP_BLUEPRINTS:
            if blueprint_id in query:
                from db.database import set_wizard_state
                if not user_id:
                    return f"⚙️ **MCP Installation Detected**\n\nYou requested the `{blueprint_id}` MCP, but I couldn't identify your Telegram session."
                state = {"mcp_id": blueprint_id, "step": 0, "answers": {}}
                set_wizard_state(user_id, state)
                from core.mcp_wizard import handle_wizard_input
                return handle_wizard_input(user_id, "", state)
        
        # 2. Search the Omega Store for files
        store_path = os.path.expanduser("~/Documents/Omega Constitution Pack/Omega System Public/Constution Store v1/omega-store")
        if not os.path.exists(store_path):
            return "❌ Omega Store repository not found on disk."
            
        # Search the store for a generic match
        matches = []
        for root, dirs, files in os.walk(store_path):
            if ".git" in root: continue
            # Try to match a folder name conceptually
            dirname = os.path.basename(root).lower()
            if query in dirname or dirname in query.replace(" ", "-"):
                matches.append(root)

        # Filter out parent directories if child is matched (simplified search)
        if not matches:
            return f"❌ Could not find an asset matching `{query}` in the Omega Store."
            
        # Just take the best/first match for now
        target = matches[0]
        name = os.path.basename(target)
        parent = os.path.basename(os.path.dirname(target))
        
        if parent == "skills":
            dest = os.path.expanduser("~/Documents/omega-claw/skills")
            os.makedirs(dest, exist_ok=True)
            try:
                shutil.copytree(target, os.path.join(dest, name), dirs_exist_ok=True)
                return f"✅ **Skill Installed!**\n\nThe `{name}` skill has been injected into Omega Claw. Restart the bot to load new intents."
            except Exception as e:
                return f"❌ Failed to install skill: {e}"
                
        elif parent in ["examples", "kits", "seeds"]:
            dest = os.path.join(self.hive_dir, "../seeds", name)
            os.makedirs(dest, exist_ok=True)
            try:
                shutil.copytree(target, dest, dirs_exist_ok=True)
                return f"✅ **Kit Installed!**\n\nThe `{name}` kit has been staged in your active workspace seeds. You can now use it in your next build."
            except Exception as e:
                return f"❌ Failed to install kit: {e}"
                
        elif parent == "mcps":
            mcp_id = name.replace("-mcp.json", "").replace(".json", "")
            from db.database import set_wizard_state
            if not user_id:
                return f"⚙️ **MCP Installation Detected**\n\nYou requested the `{name}` MCP, but I couldn't identify your Telegram session to start the wizard."
            
            state = {"mcp_id": mcp_id, "step": 0, "answers": {}}
            set_wizard_state(user_id, state)
            
            from core.mcp_wizard import handle_wizard_input
            return handle_wizard_input(user_id, "", state)
            
        else:
            return f"❌ Found `{name}`, but I don't know how to install assets of type `{parent}`."

    # --- Helpers ---
    
    def _get_next_id(self) -> int:
        max_id = 0
        if os.path.exists(self.telegram_inbox):
            for f in os.listdir(self.telegram_inbox):
                match = re.match(r"FOUNDER_JOB-(\d+)", f)
                if match:
                    max_id = max(max_id, int(match.group(1)))
        return max_id + 1

    def _slugify(self, text: str) -> str:
        words = text.split()[:3]
        slug = "-".join(words)
        return re.sub(r'[^a-zA-Z0-9-]', '', slug).title()

    # SECURITY §2.2: Escape Markdown special characters in user input
    @staticmethod
    def _escape_md(text: str) -> str:
        for ch in ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text
