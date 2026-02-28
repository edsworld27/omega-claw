# core/autonomous_runner.py — Omega Claw Autonomous Job Runner
"""
Watches for new FOUNDER_JOBs and invokes Claude Code CLI to execute them.
Reports progress back to Telegram.
Handles blockers by asking user for input.

Supports three invoker modes:
- SIMPLE: Basic -p mode (limited, no tool access)
- INTERACTIVE: PTY/pexpect mode (full tool access, requires pexpect)
- SCRIPT: Script generation mode (Claude generates scripts, Python executes)
"""

import os
import subprocess
import time
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class InvokerMode(Enum):
    """Available invoker modes."""
    SIMPLE = "simple"           # Basic -p mode (limited)
    INTERACTIVE = "interactive"  # PTY/pexpect (full power)
    SCRIPT = "script"           # Script generation (reliable)

# Paths — AI-native communication layer
HIVE_DIR = os.path.expanduser(os.getenv(
    "OMEGA_HIVE_DIR",
    "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10/USER SPACE/dev-work/hive"
))
# AI Communication directories (created by install_ai_layer.py)
INBOX_DIR = os.path.join(HIVE_DIR, "ai_inbox")      # Jobs FROM user TO Claude
OUTBOX_DIR = os.path.join(HIVE_DIR, "ai_outbox")    # Reports FROM Claude TO user
STATE_DIR = os.path.join(HIVE_DIR, "ai_state")      # Agent status
BLOCKERS_DIR = os.path.join(HIVE_DIR, "blockers")   # When Claude needs input
PROGRESS_DIR = os.path.join(HIVE_DIR, "progress")   # Detailed progress logs
CONSTITUTION_DIR = os.path.expanduser(
    "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10"
)

# Ensure directories exist
for d in [INBOX_DIR, OUTBOX_DIR, STATE_DIR, BLOCKERS_DIR, PROGRESS_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)


class AutonomousRunner:
    """
    Watches for jobs, invokes Claude, monitors progress, handles blockers.

    Supports multiple invoker modes:
    - SIMPLE: Basic -p mode (limited tool access)
    - INTERACTIVE: PTY/pexpect mode (full tool access)
    - SCRIPT: Script generation mode (Claude generates, Python executes)
    """

    def __init__(self, telegram_callback: Optional[Callable] = None, mode: str = None):
        """
        Args:
            telegram_callback: async function(user_id, message) to send Telegram updates
            mode: Invoker mode - "simple", "interactive", or "script"
        """
        self.telegram_callback = telegram_callback
        self.active_jobs = {}  # job_id -> {"status": "...", "user_id": ..., "invoker": ...}
        self.sent_reports = set()  # Track reports already sent to Telegram
        self.running = False
        self.poll_interval = 10  # seconds

        # Determine mode from env or parameter
        mode_str = mode or os.getenv("OMEGA_INVOKER_MODE", "script")
        try:
            self.mode = InvokerMode(mode_str.lower())
        except ValueError:
            logger.warning(f"Unknown mode '{mode_str}', defaulting to SCRIPT")
            self.mode = InvokerMode.SCRIPT

        logger.info(f"AutonomousRunner using {self.mode.value} mode")

    async def start(self):
        """Start the autonomous watcher loop."""
        self.running = True
        logger.info("AutonomousRunner started")

        while self.running:
            try:
                await self._check_for_new_jobs()
                await self._check_outbox()      # Watch for Claude's reports
                await self._check_blockers()
            except Exception as e:
                logger.error(f"AutonomousRunner error: {e}")

            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stop the watcher loop."""
        self.running = False
        logger.info("AutonomousRunner stopped")

    async def _check_for_new_jobs(self):
        """Scan inbox for new PENDING jobs and start building them."""
        if not os.path.exists(INBOX_DIR):
            return

        for filename in os.listdir(INBOX_DIR):
            # Accept both JOB-* (new format) and FOUNDER_JOB* (legacy)
            if not (filename.startswith("JOB-") or filename.startswith("FOUNDER_JOB")):
                continue
            if not filename.endswith(".md"):
                continue

            job_id = filename.replace(".md", "")

            # Skip if already active
            if job_id in self.active_jobs:
                continue

            filepath = os.path.join(INBOX_DIR, filename)
            with open(filepath, 'r') as f:
                content = f.read()

            # Only pick up PENDING jobs
            if "STATUS**: PENDING" not in content and "STATUS: PENDING" not in content:
                continue

            # Start this job
            logger.info(f"New job detected: {job_id}")
            await self._start_job(job_id, filepath)

    async def _start_job(self, job_id: str, job_file: str):
        """Start building a job by invoking Claude Code."""
        # Update status to BUILDING
        self._update_job_status(job_file, "BUILDING")

        # Track it
        self.active_jobs[job_id] = {
            "status": "BUILDING",
            "started": datetime.now().isoformat(),
            "file": job_file
        }

        # Create initial progress file
        progress_file = os.path.join(PROGRESS_DIR, f"{job_id}-progress.md")
        with open(progress_file, 'w') as f:
            f.write(f"# Progress: {job_id}\n\n")
            f.write(f"**Started**: {datetime.now().isoformat()}\n")
            f.write(f"**Status**: BUILDING\n\n")
            f.write("## Phases\n\n")
            f.write("- [ ] PRE-PRODUCTION (Planning)\n")
            f.write("- [ ] PRODUCTION (Building)\n")
            f.write("- [ ] POST-PRODUCTION (Testing)\n")

        # Notify via Telegram
        mode_label = self.mode.value.capitalize()
        if self.telegram_callback:
            await self.telegram_callback(
                None,  # Will need user_id from job file
                f"🚀 **Job Started**: {job_id}\n\n"
                f"Mode: {mode_label}\n"
                f"Building autonomously. I'll report after each phase."
            )

        # Invoke Claude Code using the selected mode
        asyncio.create_task(self._invoke_by_mode(job_id, job_file))

    async def _invoke_by_mode(self, job_id: str, job_file: str):
        """Invoke Claude using the appropriate mode."""
        if self.mode == InvokerMode.INTERACTIVE:
            await self._invoke_interactive(job_id, job_file)
        elif self.mode == InvokerMode.SCRIPT:
            await self._invoke_script(job_id, job_file)
        else:
            await self._invoke_simple(job_id, job_file)

    async def _invoke_interactive(self, job_id: str, job_file: str):
        """Use PTY/pexpect for full interactive Claude session."""
        try:
            from core.interactive_invoker import InteractiveInvoker, PEXPECT_AVAILABLE

            if not PEXPECT_AVAILABLE:
                logger.warning("pexpect not available, falling back to script mode")
                await self._invoke_script(job_id, job_file)
                return

            invoker = InteractiveInvoker(
                job_id=job_id,
                job_file=job_file,
                constitution_dir=CONSTITUTION_DIR,
                progress_dir=PROGRESS_DIR,
                blockers_dir=BLOCKERS_DIR,
                telegram_callback=self.telegram_callback
            )

            self.active_jobs[job_id]["invoker"] = invoker
            await invoker.start()

            # Update status when done
            self._update_job_status(job_file, "COMPLETE")
            self.active_jobs[job_id]["status"] = "COMPLETE"

        except Exception as e:
            logger.error(f"Interactive invoker failed: {e}")
            self._update_job_status(job_file, "FAILED")

    async def _invoke_script(self, job_id: str, job_file: str):
        """Use script generation mode."""
        try:
            from core.script_invoker import ScriptInvoker

            invoker = ScriptInvoker(
                job_id=job_id,
                job_file=job_file,
                constitution_dir=CONSTITUTION_DIR,
                progress_dir=PROGRESS_DIR,
                blockers_dir=BLOCKERS_DIR,
                outbox_dir=OUTBOX_DIR,
                telegram_callback=self.telegram_callback
            )

            self.active_jobs[job_id]["invoker"] = invoker
            await invoker.start()

            # Update status when done
            self._update_job_status(job_file, "COMPLETE")
            self.active_jobs[job_id]["status"] = "COMPLETE"

        except Exception as e:
            logger.error(f"Script invoker failed: {e}")
            self._update_job_status(job_file, "FAILED")

    async def _invoke_simple(self, job_id: str, job_file: str):
        """Invoke Claude Code CLI to build the job (simple -p mode)."""
        prompt = f"""You are the Omega Master Orchestrator.

READ THESE FILES IN ORDER:
1. {job_file}
2. {CONSTITUTION_DIR}/CONSTITUTION/INSTRUCTOR.xml
3. {CONSTITUTION_DIR}/USER SPACE/dev-work/hive/MASTER_ORCHESTRATOR.md

EXECUTE:
1. Claim this job (update STATUS to BUILDING if not already)
2. Follow the Kit and Mode specified in the job
3. After each major phase, write progress to: {PROGRESS_DIR}/{job_id}-progress.md
4. If you need something from the user (API key, decision, clarification):
   - Write a blocker file to: {BLOCKERS_DIR}/{job_id}-blocked.md
   - Include: what you need, why, and what happens next
   - STOP and wait (the bot will ask the user)
5. When complete, update the job STATUS to COMPLETE

Progress format:
```
## Phase X: [Name]
**Status**: COMPLETE | IN_PROGRESS | BLOCKED
**Summary**: What was done
**Next**: What happens next
```

BEGIN NOW.
"""

        try:
            # Run Claude CLI with -p for non-interactive mode
            claude_path = os.path.expanduser("~/.local/bin/claude")
            result = subprocess.run(
                [claude_path, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
                cwd=CONSTITUTION_DIR
            )

            if result.returncode == 0:
                logger.info(f"Claude completed job: {job_id}")
                self._update_job_status(
                    self.active_jobs[job_id]["file"],
                    "COMPLETE"
                )
                self.active_jobs[job_id]["status"] = "COMPLETE"
            else:
                logger.error(f"Claude failed for {job_id}: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Claude timed out for job: {job_id}")
        except FileNotFoundError:
            logger.error("Claude CLI not found. Install claude-code or check PATH.")
        except Exception as e:
            logger.error(f"Failed to invoke Claude: {e}")

    async def _check_outbox(self):
        """Watch ai_outbox for new REPORT files from Claude and send to Telegram."""
        if not os.path.exists(OUTBOX_DIR):
            return

        for filename in os.listdir(OUTBOX_DIR):
            # Look for REPORT-*.md files
            if not filename.startswith("REPORT-") or not filename.endswith(".md"):
                continue

            filepath = os.path.join(OUTBOX_DIR, filename)

            # Skip if already sent
            if filepath in self.sent_reports:
                continue

            # Read report
            with open(filepath, 'r') as f:
                content = f.read()

            # Extract summary for Telegram (first 1000 chars or until ## Next)
            summary = content[:1500]
            if "## Next" in summary:
                summary = summary.split("## Next")[0]

            # Send to Telegram
            if self.telegram_callback:
                await self.telegram_callback(
                    None,
                    f"📊 **Report**: {filename}\n\n{summary[:1000]}"
                )
                logger.info(f"Sent report to Telegram: {filename}")

            # Mark as sent
            self.sent_reports.add(filepath)

    async def _check_blockers(self):
        """Check for blocker files and ask user for input."""
        if not os.path.exists(BLOCKERS_DIR):
            return

        for filename in os.listdir(BLOCKERS_DIR):
            # Support both BLOCKED-*.md (new) and *-blocked.md (legacy)
            if not (filename.startswith("BLOCKED-") or filename.endswith("-blocked.md")):
                continue
            if not filename.endswith(".md"):
                continue

            # Extract job_id
            if filename.startswith("BLOCKED-"):
                job_id = filename.replace("BLOCKED-", "").replace(".md", "")
            else:
                job_id = filename.replace("-blocked.md", "")

            filepath = os.path.join(BLOCKERS_DIR, filename)

            # Read blocker
            with open(filepath, 'r') as f:
                content = f.read()

            # Notify user
            if self.telegram_callback:
                await self.telegram_callback(
                    None,
                    f"⚠️ **Job Blocked**: {job_id}\n\n{content}\n\nReply with the requested information."
                )

            # Move to processed (so we don't spam)
            processed_path = filepath.replace("-blocked.md", "-blocked-sent.md")
            os.rename(filepath, processed_path)

    def _update_job_status(self, job_file: str, status: str):
        """Update the STATUS in a job file."""
        with open(job_file, 'r') as f:
            content = f.read()

        content = content.replace("STATUS**: PENDING", f"STATUS**: {status}")
        content = content.replace("STATUS: PENDING", f"STATUS: {status}")
        content = content.replace("STATUS**: BUILDING", f"STATUS**: {status}")
        content = content.replace("STATUS: BUILDING", f"STATUS: {status}")

        with open(job_file, 'w') as f:
            f.write(content)

    async def handle_user_response(self, job_id: str, response: str):
        """
        Handle user's response to a blocker.
        Write to an answers file and resume Claude.
        """
        answer_file = os.path.join(BLOCKERS_DIR, f"{job_id}-answer.md")
        with open(answer_file, 'w') as f:
            f.write(f"# User Response for {job_id}\n\n")
            f.write(f"**Received**: {datetime.now().isoformat()}\n\n")
            f.write(f"## Answer\n\n{response}\n")

        # Resume Claude with the answer
        if job_id in self.active_jobs:
            job_file = self.active_jobs[job_id]["file"]
            asyncio.create_task(self._invoke_claude(job_id, job_file))
