# core/terminal_bridge.py — Direct Terminal Bridge to Claude Code
"""
The simplest, cleanest solution:
- Python spawns Claude Code in a PTY
- Telegram messages get typed directly to Claude
- Claude's responses get sent back to Telegram

No API costs. Full tool access. Real AI understanding.
"""

import os
import re
import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    import pexpect
    PEXPECT_AVAILABLE = True
except ImportError:
    PEXPECT_AVAILABLE = False
    logger.warning("pexpect not installed. Run: pip install pexpect")


class TerminalBridge:
    """
    Bridges Telegram to a running Claude Code terminal session.

    Usage:
        bridge = TerminalBridge()
        await bridge.start()  # Spawns Claude Code
        response = await bridge.send_message("Build me a landing page")
        print(response)  # Claude's full response
    """

    def __init__(self, constitution_dir: str = None):
        self.constitution_dir = constitution_dir or os.path.expanduser(
            "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10"
        )
        self.claude_process = None
        self.ready = False
        self.busy = False
        self.message_queue = asyncio.Queue()

    async def start(self) -> bool:
        """Spawn Claude Code in a PTY."""
        if not PEXPECT_AVAILABLE:
            logger.error("pexpect not available")
            return False

        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            claude_path = "claude"  # Try system PATH

        try:
            logger.info("Spawning Claude Code...")
            self.claude_process = pexpect.spawn(
                claude_path,
                encoding='utf-8',
                timeout=300,
                cwd=self.constitution_dir,
                env={**os.environ, 'TERM': 'dumb'},
                dimensions=(50, 200)  # rows, cols
            )

            # Wait for Claude to be ready
            await self._wait_for_ready()
            self.ready = True
            logger.info("Claude Code is ready")
            return True

        except Exception as e:
            logger.error(f"Failed to spawn Claude: {e}")
            return False

    async def _wait_for_ready(self):
        """Wait for Claude to show it's ready for input."""
        # Claude typically shows a prompt or greeting
        try:
            # Look for common ready indicators
            self.claude_process.expect([
                r'[>»›]',           # Prompt characters
                r'How can I',       # Greeting
                r'help you',        # Part of greeting
                pexpect.TIMEOUT
            ], timeout=30)
        except pexpect.TIMEOUT:
            logger.warning("Timeout waiting for Claude prompt, continuing anyway")

    async def send_message(self, message: str, timeout: int = 300) -> str:
        """
        Send a message to Claude and get the response.

        Args:
            message: The message to send
            timeout: Max seconds to wait for response

        Returns:
            Claude's response text
        """
        if not self.ready or not self.claude_process:
            return "Error: Claude not running. Call start() first."

        if self.busy:
            return "Error: Claude is busy with another request. Please wait."

        self.busy = True
        try:
            # Clear any pending output
            try:
                self.claude_process.read_nonblocking(size=10000, timeout=0.1)
            except pexpect.TIMEOUT:
                pass

            # Send the message
            logger.info(f"Sending to Claude: {message[:50]}...")
            self.claude_process.sendline(message)

            # Collect response
            response = await self._collect_response(timeout)
            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return f"Error: {str(e)}"
        finally:
            self.busy = False

    async def _collect_response(self, timeout: int) -> str:
        """Collect Claude's response until it's done."""
        response_parts = []
        start_time = asyncio.get_event_loop().time()
        silence_start = None

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning("Response timeout")
                break

            try:
                # Read available output
                chunk = self.claude_process.read_nonblocking(size=4096, timeout=0.5)
                if chunk:
                    response_parts.append(chunk)
                    silence_start = None  # Reset silence timer
                else:
                    # No output - start silence timer
                    if silence_start is None:
                        silence_start = asyncio.get_event_loop().time()

            except pexpect.TIMEOUT:
                # No output available
                if silence_start is None:
                    silence_start = asyncio.get_event_loop().time()

            except pexpect.EOF:
                logger.warning("Claude process ended")
                break

            # Check for silence (Claude done responding)
            if silence_start:
                silence_duration = asyncio.get_event_loop().time() - silence_start
                # If 3+ seconds of silence after getting some output, assume done
                if silence_duration > 3 and response_parts:
                    break

            await asyncio.sleep(0.1)

        # Clean up response
        raw_response = ''.join(response_parts)
        return self._clean_response(raw_response)

    def _clean_response(self, raw: str) -> str:
        """Clean up Claude's response for Telegram."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', raw)

        # Remove the echoed input (first line is usually what we sent)
        lines = cleaned.split('\n')
        if len(lines) > 1:
            lines = lines[1:]  # Skip echoed input

        # Remove prompt characters at end
        cleaned = '\n'.join(lines).strip()
        cleaned = re.sub(r'[>»›]\s*$', '', cleaned)

        return cleaned

    def stop(self):
        """Stop the Claude process."""
        if self.claude_process:
            try:
                self.claude_process.sendline('/exit')
                self.claude_process.close()
            except:
                pass
        self.ready = False
        self.claude_process = None
        logger.info("Claude process stopped")

    @property
    def is_ready(self) -> bool:
        return self.ready and self.claude_process and self.claude_process.isalive()


# Singleton instance for the bot to use
_bridge: Optional[TerminalBridge] = None


async def get_bridge() -> TerminalBridge:
    """Get or create the terminal bridge singleton."""
    global _bridge
    if _bridge is None or not _bridge.is_ready:
        _bridge = TerminalBridge()
        await _bridge.start()
    return _bridge


async def send_to_claude(message: str) -> str:
    """Convenience function to send a message to Claude."""
    bridge = await get_bridge()
    return await bridge.send_message(message)
