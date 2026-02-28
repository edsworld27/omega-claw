# core/interactive_invoker.py — PTY/Expect Claude Invoker (Option B)
"""
Uses pexpect to drive an interactive Claude Code session.
This gives Claude full tool access (read, write, edit, bash).

Requires: pip install pexpect
"""

import os
import re
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Try to import pexpect
try:
    import pexpect
    PEXPECT_AVAILABLE = True
except ImportError:
    PEXPECT_AVAILABLE = False
    logger.warning("pexpect not installed. Run: pip install pexpect")


class InteractiveInvoker:
    """
    Drives Claude Code interactively using PTY/pexpect.
    Claude gets full tool access - can read, write, edit files.
    """

    def __init__(
        self,
        job_id: str,
        job_file: str,
        constitution_dir: str,
        progress_dir: str,
        blockers_dir: str,
        telegram_callback: Optional[Callable] = None
    ):
        self.job_id = job_id
        self.job_file = job_file
        self.constitution_dir = constitution_dir
        self.progress_dir = progress_dir
        self.blockers_dir = blockers_dir
        self.telegram_callback = telegram_callback
        self.child = None
        self.running = False

    async def start(self) -> bool:
        """Start the interactive Claude session."""
        if not PEXPECT_AVAILABLE:
            logger.error("pexpect not available. Cannot start interactive mode.")
            return False

        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            # Try system path
            claude_path = "claude"

        # Build the initial prompt
        initial_prompt = self._build_prompt()

        try:
            # Spawn Claude in interactive mode
            self.child = pexpect.spawn(
                claude_path,
                encoding='utf-8',
                timeout=300,  # 5 min timeout per interaction
                cwd=self.constitution_dir,
                env={**os.environ, 'TERM': 'dumb'}  # Simple terminal
            )

            # Wait for Claude to be ready (look for prompt)
            await self._wait_for_ready()

            # Send the initial job prompt
            self.child.sendline(initial_prompt)
            self.running = True

            # Monitor the session
            await self._monitor_session()

            return True

        except pexpect.ExceptionPexpect as e:
            logger.error(f"pexpect error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start interactive session: {e}")
            return False

    async def _wait_for_ready(self):
        """Wait for Claude to be ready to accept input."""
        # Claude Code shows ">" or similar when ready
        patterns = [
            r'[>»]',  # Common prompt characters
            r'How can I help',  # Initial greeting
            pexpect.TIMEOUT,
            pexpect.EOF
        ]

        try:
            index = self.child.expect(patterns, timeout=30)
            if index == 2:  # TIMEOUT
                logger.warning("Timeout waiting for Claude prompt")
            elif index == 3:  # EOF
                logger.error("Claude exited unexpectedly")
        except Exception as e:
            logger.warning(f"Wait for ready: {e}")

    async def _monitor_session(self):
        """Monitor the Claude session for output, tool requests, blockers."""
        output_buffer = ""
        last_progress_update = datetime.now()

        while self.running:
            try:
                # Read output (non-blocking via expect with short timeout)
                patterns = [
                    r'\[Y/n\]',           # Yes/No prompt (tool permission)
                    r'\[y/N\]',           # Yes/No prompt (default no)
                    r'Enter.*:',          # Input prompt
                    r'BLOCKED:',          # Our blocker marker
                    r'PHASE_COMPLETE:',   # Phase completion marker
                    r'JOB_COMPLETE',      # Job done
                    pexpect.TIMEOUT,
                    pexpect.EOF
                ]

                index = self.child.expect(patterns, timeout=10)
                output_buffer += self.child.before + self.child.after

                if index == 0 or index == 1:  # Tool permission request
                    # Auto-approve tool requests
                    logger.info(f"Auto-approving tool request for job {self.job_id}")
                    self.child.sendline('y')

                elif index == 2:  # Input prompt
                    # Check if this is a blocker that needs user input
                    if 'API_KEY' in output_buffer or 'SECRET' in output_buffer:
                        await self._handle_blocker(output_buffer)
                    else:
                        # Generic input - try to continue
                        self.child.sendline('')

                elif index == 3:  # BLOCKED marker
                    await self._handle_blocker(output_buffer)

                elif index == 4:  # Phase complete
                    await self._report_progress(output_buffer)
                    output_buffer = ""

                elif index == 5:  # Job complete
                    logger.info(f"Job {self.job_id} completed")
                    self.running = False
                    await self._finalize_job(output_buffer)

                elif index == 6:  # TIMEOUT
                    # Check if we should send progress update
                    if (datetime.now() - last_progress_update).seconds > 60:
                        await self._report_progress(output_buffer, periodic=True)
                        last_progress_update = datetime.now()

                elif index == 7:  # EOF
                    logger.info(f"Claude session ended for job {self.job_id}")
                    self.running = False

            except pexpect.TIMEOUT:
                # Normal - just loop again
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)

    async def _handle_blocker(self, context: str):
        """Handle a blocker that needs user input."""
        # Write blocker file
        blocker_file = os.path.join(self.blockers_dir, f"{self.job_id}-blocked.md")

        # Extract what Claude needs
        needs = self._extract_needs(context)

        with open(blocker_file, 'w') as f:
            f.write(f"# Blocker: {self.job_id}\n\n")
            f.write(f"**Time**: {datetime.now().isoformat()}\n\n")
            f.write(f"## What's Needed\n\n{needs}\n\n")
            f.write("## Context\n\n")
            f.write(f"```\n{context[-500:]}\n```\n")

        # Notify via Telegram
        if self.telegram_callback:
            await self.telegram_callback(
                None,
                f"⚠️ **Job Blocked**: {self.job_id}\n\n{needs}\n\nReply with the information needed."
            )

        # Pause and wait for answer file
        await self._wait_for_answer()

    async def _wait_for_answer(self):
        """Wait for user to provide answer via answer file."""
        answer_file = os.path.join(self.blockers_dir, f"{self.job_id}-answer.md")

        while self.running:
            if os.path.exists(answer_file):
                with open(answer_file, 'r') as f:
                    content = f.read()

                # Extract the answer
                answer = self._extract_answer(content)

                # Send to Claude
                self.child.sendline(answer)

                # Clean up
                os.remove(answer_file)
                logger.info(f"Sent user answer for job {self.job_id}")
                break

            await asyncio.sleep(5)

    async def _report_progress(self, output: str, periodic: bool = False):
        """Write progress to file and notify Telegram."""
        progress_file = os.path.join(self.progress_dir, f"{self.job_id}-progress.md")

        # Append to progress file
        with open(progress_file, 'a') as f:
            f.write(f"\n\n---\n**Update**: {datetime.now().isoformat()}\n")
            if periodic:
                f.write("(Periodic update - still working)\n")
            # Include last 500 chars of output
            f.write(f"\n```\n{output[-500:]}\n```\n")

        # Notify Telegram (not for periodic updates to avoid spam)
        if self.telegram_callback and not periodic:
            summary = self._summarize_output(output)
            await self.telegram_callback(
                None,
                f"📊 **Progress Update**: {self.job_id}\n\n{summary}"
            )

    async def _finalize_job(self, output: str):
        """Mark job complete and send final notification."""
        if self.telegram_callback:
            await self.telegram_callback(
                None,
                f"✅ **Job Complete**: {self.job_id}\n\nClaude has finished building."
            )

    def _build_prompt(self) -> str:
        """Build the initial prompt for Claude."""
        return f"""You are the Omega Master Orchestrator running in AUTONOMOUS mode.

READ THESE FILES:
1. {self.job_file}
2. {self.constitution_dir}/CONSTITUTION/INSTRUCTOR.xml

AUTONOMOUS PROTOCOL:
1. Read and understand the job requirements
2. Execute the build following the Kit specified
3. After each major phase, output: PHASE_COMPLETE: [phase name]
4. If you need user input (API key, decision), output: BLOCKED: [what you need]
5. When completely done, output: JOB_COMPLETE
6. Write your progress to: {self.progress_dir}/{self.job_id}-progress.md

IMPORTANT:
- You have FULL tool access (read, write, edit, bash)
- Work autonomously - only ask the user when truly blocked
- Report progress after each phase

BEGIN NOW. Read the job file first."""

    def _extract_needs(self, context: str) -> str:
        """Extract what Claude needs from the context."""
        # Look for common patterns
        patterns = [
            r'(need[s]?\s+(?:an?\s+)?(?:API|key|token|secret|password|credential)[^\n]+)',
            r'(require[s]?\s+(?:an?\s+)?[^\n]+)',
            r'(please\s+provide[^\n]+)',
            r'(BLOCKED:\s*[^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1)

        # Fallback: last meaningful line
        lines = [l.strip() for l in context.split('\n') if l.strip()]
        return lines[-1] if lines else "Claude needs input (check logs)"

    def _extract_answer(self, content: str) -> str:
        """Extract the answer from answer file."""
        # Look for ## Answer section
        match = re.search(r'## Answer\s*\n+(.+)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return content.strip()

    def _summarize_output(self, output: str) -> str:
        """Summarize output for Telegram notification."""
        # Extract key points
        lines = output.split('\n')
        summary_lines = []

        for line in lines[-20:]:  # Last 20 lines
            line = line.strip()
            if any(kw in line.lower() for kw in ['created', 'wrote', 'updated', 'complete', 'done', 'error', 'failed']):
                summary_lines.append(f"• {line[:100]}")

        if summary_lines:
            return '\n'.join(summary_lines[:5])  # Max 5 points
        return "(Progress details in hive/progress/)"

    def stop(self):
        """Stop the interactive session."""
        self.running = False
        if self.child:
            self.child.close()

    async def send_input(self, text: str):
        """Send input to the running Claude session."""
        if self.child and self.running:
            self.child.sendline(text)
