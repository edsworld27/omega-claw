# core/script_invoker.py — Script Generation Invoker (Option C)
"""
Claude generates bash/python scripts via -p mode.
Python executes the scripts and loops back results.

Pros: More reliable, no PTY complexity
Cons: Limited to what scripts can do
"""

import os
import re
import json
import subprocess
import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List, Dict

logger = logging.getLogger(__name__)


class ScriptInvoker:
    """
    Claude generates scripts, Python executes them.
    Works in cycles: ask Claude -> get script -> execute -> report results -> repeat.
    """

    def __init__(
        self,
        job_id: str,
        job_file: str,
        constitution_dir: str,
        progress_dir: str,
        blockers_dir: str,
        outbox_dir: str = None,
        telegram_callback: Optional[Callable] = None,
        max_cycles: int = 50  # Safety limit
    ):
        self.job_id = job_id
        self.job_file = job_file
        self.constitution_dir = constitution_dir
        self.progress_dir = progress_dir
        self.blockers_dir = blockers_dir
        # Outbox for AI-native reports (defaults to progress_dir/../ai_outbox)
        self.outbox_dir = outbox_dir or os.path.join(os.path.dirname(progress_dir), "ai_outbox")
        self.telegram_callback = telegram_callback
        self.max_cycles = max_cycles
        self.running = False
        self.cycle_count = 0
        self.execution_log: List[Dict] = []

    async def start(self) -> bool:
        """Start the script-based build cycle."""
        self.running = True
        logger.info(f"ScriptInvoker starting for job {self.job_id}")

        # Read the job file
        with open(self.job_file, 'r') as f:
            job_content = f.read()

        # Initialize context
        context = {
            "job": job_content,
            "phase": "init",
            "completed_actions": [],
            "last_result": None
        }

        # Notify start
        if self.telegram_callback:
            await self.telegram_callback(
                None,
                f"🚀 **Job Started (Script Mode)**: {self.job_id}\n\nBuilding in cycles. Will report progress."
            )

        # Main build loop
        while self.running and self.cycle_count < self.max_cycles:
            try:
                result = await self._run_cycle(context)

                if result["status"] == "complete":
                    logger.info(f"Job {self.job_id} completed")
                    await self._finalize_job()
                    break

                elif result["status"] == "blocked":
                    await self._handle_blocker(result["reason"])
                    # Wait for answer
                    answer = await self._wait_for_answer()
                    context["last_result"] = f"User provided: {answer}"

                elif result["status"] == "continue":
                    context["last_result"] = result.get("output", "")
                    context["completed_actions"].extend(result.get("actions", []))

                elif result["status"] == "error":
                    logger.error(f"Cycle error: {result.get('error')}")
                    context["last_result"] = f"ERROR: {result.get('error')}"

                self.cycle_count += 1

                # Progress update every 5 cycles
                if self.cycle_count % 5 == 0:
                    await self._report_progress(context)

            except Exception as e:
                logger.error(f"Cycle exception: {e}")
                await asyncio.sleep(5)

        if self.cycle_count >= self.max_cycles:
            logger.warning(f"Job {self.job_id} hit max cycles ({self.max_cycles})")
            if self.telegram_callback:
                await self.telegram_callback(
                    None,
                    f"⚠️ **Job Paused**: {self.job_id}\n\nHit cycle limit. May need manual review."
                )

        return True

    async def _run_cycle(self, context: Dict) -> Dict:
        """Run one cycle: ask Claude -> get script -> execute."""

        # Build prompt for Claude
        prompt = self._build_cycle_prompt(context)

        # Call Claude in print mode
        claude_path = os.path.expanduser("~/.local/bin/claude")
        try:
            result = subprocess.run(
                [claude_path, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min per cycle
                cwd=self.constitution_dir
            )

            response = result.stdout if result.returncode == 0 else result.stderr

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Claude timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

        # Parse Claude's response
        return await self._parse_and_execute(response)

    def _build_cycle_prompt(self, context: Dict) -> str:
        """Build the prompt for this cycle."""
        completed = "\n".join(f"- {a}" for a in context["completed_actions"][-10:])
        last = context.get("last_result", "None")[:500]

        return f"""You are the Omega Build Agent working on job: {self.job_id}

## Job Description
{context["job"][:2000]}

## Current Phase: {context["phase"]}

## Completed Actions (recent)
{completed or "None yet"}

## Last Result
{last}

## Your Task
Determine the NEXT action needed. Respond with ONE of these formats:

### To execute a bash command:
```bash
<your command here>
```

### To create/write a file:
```write:path/to/file.ext
<file content>
```

### To indicate you need user input:
```blocked
REASON: <what you need from the user>
```

### To indicate the job is complete:
```complete
SUMMARY: <what was built>
```

### To indicate the next phase:
```phase:<phase_name>
```

IMPORTANT:
- Output ONLY ONE action per response
- Prefer simple, atomic commands
- Check results before proceeding
- If stuck, request user input via blocked

What's the next action?"""

    async def _parse_and_execute(self, response: str) -> Dict:
        """Parse Claude's response and execute if needed."""

        # Check for completion
        if "```complete" in response:
            match = re.search(r'```complete\s*\n?(.*?)```', response, re.DOTALL)
            summary = match.group(1) if match else "Build completed"
            return {"status": "complete", "summary": summary}

        # Check for blocker
        if "```blocked" in response:
            match = re.search(r'```blocked\s*\n?(.*?)```', response, re.DOTALL)
            reason = match.group(1) if match else "Unknown blocker"
            return {"status": "blocked", "reason": reason}

        # Check for phase change
        phase_match = re.search(r'```phase:(\w+)', response)
        if phase_match:
            return {"status": "continue", "phase": phase_match.group(1), "actions": [f"Phase: {phase_match.group(1)}"]}

        # Check for bash command
        bash_match = re.search(r'```bash\s*\n(.*?)```', response, re.DOTALL)
        if bash_match:
            command = bash_match.group(1).strip()
            output = await self._execute_bash(command)
            return {
                "status": "continue",
                "output": output,
                "actions": [f"Ran: {command[:50]}..."]
            }

        # Check for file write
        write_match = re.search(r'```write:([^\n]+)\n(.*?)```', response, re.DOTALL)
        if write_match:
            filepath = write_match.group(1).strip()
            content = write_match.group(2)
            output = await self._write_file(filepath, content)
            return {
                "status": "continue",
                "output": output,
                "actions": [f"Wrote: {filepath}"]
            }

        # No recognizable action - try to continue
        return {
            "status": "continue",
            "output": f"Claude said: {response[:200]}...",
            "actions": ["(No action extracted)"]
        }

    async def _execute_bash(self, command: str) -> str:
        """Execute a bash command safely."""
        # Safety checks
        dangerous = ['rm -rf /', 'rm -rf ~', 'dd if=', ':(){ :|:& };:', 'mkfs', 'format']
        if any(d in command for d in dangerous):
            return f"BLOCKED: Dangerous command rejected: {command}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.constitution_dir
            )

            output = result.stdout + result.stderr
            self.execution_log.append({
                "type": "bash",
                "command": command,
                "output": output[:500],
                "returncode": result.returncode,
                "time": datetime.now().isoformat()
            })

            return output[:1000]

        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out"
        except Exception as e:
            return f"ERROR: {str(e)}"

    async def _write_file(self, filepath: str, content: str) -> str:
        """Write content to a file."""
        # Resolve path relative to constitution dir
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.constitution_dir, filepath)

        try:
            # Create parent directories
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                f.write(content)

            self.execution_log.append({
                "type": "write",
                "path": filepath,
                "size": len(content),
                "time": datetime.now().isoformat()
            })

            return f"Successfully wrote {len(content)} bytes to {filepath}"

        except Exception as e:
            return f"ERROR writing file: {str(e)}"

    async def _handle_blocker(self, reason: str):
        """Handle a blocker that needs user input."""
        # Use new BLOCKED- prefix format
        blocker_file = os.path.join(self.blockers_dir, f"BLOCKED-{self.job_id}.md")

        with open(blocker_file, 'w') as f:
            f.write(f"# Blocker: {self.job_id}\n\n")
            f.write(f"**Time**: {datetime.now().isoformat()}\n")
            f.write(f"**Cycle**: {self.cycle_count}\n\n")
            f.write(f"## Reason\n\n{reason}\n")

        if self.telegram_callback:
            await self.telegram_callback(
                None,
                f"⚠️ **Job Blocked**: {self.job_id}\n\n{reason}\n\nReply with the information needed."
            )

    async def _wait_for_answer(self) -> str:
        """Wait for user to provide answer."""
        # Use new ANSWER- prefix format
        answer_file = os.path.join(self.blockers_dir, f"ANSWER-{self.job_id}.md")

        while self.running:
            if os.path.exists(answer_file):
                with open(answer_file, 'r') as f:
                    content = f.read()

                # Extract answer
                match = re.search(r'## Answer\s*\n+(.+)', content, re.DOTALL)
                answer = match.group(1).strip() if match else content.strip()

                # Clean up
                os.remove(answer_file)
                return answer

            await asyncio.sleep(5)

        return ""

    async def _report_progress(self, context: Dict):
        """Write progress to file and outbox for Telegram."""
        progress_file = os.path.join(self.progress_dir, f"{self.job_id}-progress.md")

        recent_actions = context["completed_actions"][-10:]
        timestamp = datetime.now().isoformat()

        # Write to progress file (detailed log)
        with open(progress_file, 'a') as f:
            f.write(f"\n\n---\n## Cycle {self.cycle_count}\n")
            f.write(f"**Time**: {timestamp}\n")
            f.write(f"**Phase**: {context['phase']}\n\n")
            f.write("### Recent Actions\n")
            for action in recent_actions:
                f.write(f"- {action}\n")

        # Write to outbox (AI-native format for Telegram)
        Path(self.outbox_dir).mkdir(parents=True, exist_ok=True)
        report_file = os.path.join(
            self.outbox_dir,
            f"REPORT-{self.job_id}-{self.cycle_count}.md"
        )
        with open(report_file, 'w') as f:
            f.write(f"# Report: {self.job_id}\n\n")
            f.write(f"**Time**: {timestamp}\n")
            f.write(f"**Phase**: {context['phase']}\n")
            f.write(f"**Cycle**: {self.cycle_count}\n")
            f.write(f"**Status**: IN_PROGRESS\n\n")
            f.write("## Summary\n\n")
            for action in recent_actions[-5:]:
                f.write(f"- {action}\n")
            f.write("\n## Next\n\nContinuing build...\n")

        if self.telegram_callback:
            summary = f"Cycle {self.cycle_count} - {context['phase']}\n"
            summary += "\n".join(f"• {a[:50]}" for a in recent_actions[:3])
            await self.telegram_callback(
                None,
                f"📊 **Progress**: {self.job_id}\n\n{summary}"
            )

    async def _finalize_job(self):
        """Mark job as complete."""
        # Write execution log
        log_file = os.path.join(self.progress_dir, f"{self.job_id}-execution-log.json")
        with open(log_file, 'w') as f:
            json.dump(self.execution_log, f, indent=2)

        if self.telegram_callback:
            await self.telegram_callback(
                None,
                f"✅ **Job Complete**: {self.job_id}\n\n"
                f"Completed in {self.cycle_count} cycles.\n"
                f"Execution log: {log_file}"
            )

    def stop(self):
        """Stop the invoker."""
        self.running = False
