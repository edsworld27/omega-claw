# agents/terminal_agent/__init__.py
# Vector 1: The Stealth Engine (pexpect CLI wrapper)

import pexpect
import os
import logging
from typing import Callable

logger = logging.getLogger(__name__)

class TerminalAgent:
    def __init__(self, engine_cmd: str = "claude", workspace_root: str = None, autonomy_mode: str = "security"):
        """
        engine_cmd: 'claude' or 'aider'
        autonomy_mode: 'full', 'security', or 'manual'
        """
        self.engine_cmd = engine_cmd
        self.workspace_root = workspace_root or os.path.expanduser("~/Desktop/omega-builds")
        self.autonomy_mode = autonomy_mode
        self.child = None
    
    def spawn(self):
        # Ensure workspace exists
        os.makedirs(self.workspace_root, exist_ok=True)
        
        logger.info(f"[Vector 1] Spawning Stealth Engine: {self.engine_cmd} in {self.workspace_root}")
        
        try:
            self.child = pexpect.spawn(self.engine_cmd, cwd=self.workspace_root, encoding='utf-8', timeout=None)
            logger.info("[Vector 1] Spawn successful.")
        except Exception as e:
            logger.error(f"[Vector 1] Failed to spawn {self.engine_cmd}: {e}")
            raise
    
    def send_intent(self, prompt: str):
        if not self.child:
            self.spawn()
        
        logger.info(f"[Vector 1] Injecting Prompt: {prompt}")
        self.child.sendline(prompt)
    
    def watch_stdout(self, limit_callback: Callable):
        """
        Actively monitors the CLI output. If it detects a rate limit,
        it fires the callback so Orchestrator can failover to Vector 2.
        """
        if not self.child: return
        
        while True:
            try:
                # Read line by line non-blocking
                line = self.child.readline()
                if not line: break
                
                # Intercept (y/n) prompts based on autonomy mode
                if "(y/n)" in line.lower() or "approve" in line.lower():
                    if self.autonomy_mode == "full":
                        logger.info("[Vector 1] Full Autonomy: Auto-Approve (y)")
                        self.child.sendline("y")
                    elif self.autonomy_mode == "security":
                        # In a real build, we'd parse the command to see if it's safe 
                        # For now, default to manual warning
                        logger.warning(f"[Vector 1] Security Mode: Caught permission request: {line.strip()}")
                
                # Detect Claude Pro message limit
                if "run out of messages" in line.lower() or "usage limit" in line.lower():
                    logger.critical(f"[Vector 1] RATE LIMIT DETECTED! Shutting down {self.engine_cmd}.")
                    self.child.close()
                    limit_callback()
                    break
                    
            except pexpect.EOF:
                logger.info("[Vector 1] Child process ended naturally.")
                break
            except pexpect.TIMEOUT:
                continue
