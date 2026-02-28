import logging
import time
from agents.terminal_agent import TerminalAgent
from agents.phantom_agent import PhantomAgent

logger = logging.getLogger(__name__)

class DualVectorController:
    """
    Manages the lifecycle of both Vector 1 (Stealth/CLI) and Vector 2 (Phantom/GUI).
    Handles the handoff when one agent hits a rate limit.
    """
    
    def __init__(self, workspace_root: str, autonomy_mode: str = "security"):
        self.terminal = TerminalAgent(engine_cmd="claude", workspace_root=workspace_root, autonomy_mode=autonomy_mode)
        self.phantom = PhantomAgent(target_app_name="Antigravity")
        self.active_vector = 1  # 1 = Terminal, 2 = Phantom
        
    def execute_task(self, prompt: str):
        """
        Main entry point for task execution.
        Starts with Vector 1 (Claude Code) and fails over to Vector 2.
        """
        logger.info(f"[DualVector] Dispatching Task: {prompt[:50]}...")
        
        if self.active_vector == 1:
            try:
                self.terminal.spawn()
                self.terminal.send_intent(prompt)
                
                # Active watch for limits
                self.terminal.watch_stdout(limit_callback=lambda: self._handoff_to_phantom(prompt))
                
            except Exception as e:
                logger.error(f"[DualVector] Vector 1 failure: {e}. Attempting failover to Vector 2.")
                self._handoff_to_phantom(prompt)
        else:
            self._run_phantom(prompt)

    def _handoff_to_phantom(self, prompt: str):
        """
        Triggered when Claude CLI hits a limit.
        Cleans up the CLI and launches the GUI agent.
        """
        logger.critical("[DualVector] HANDOFF TRIGGERED: Claude CLI -> Antigravity GUI")
        self.active_vector = 2
        
        # 1. Clean up Terminal if still hanging
        if self.terminal.child and self.terminal.child.isalive():
            self.terminal.child.close()
            
        # 2. Start Phantom
        # We inject the same prompt to Antigravity as a starting point.
        # Future optimization: Partial task continuation.
        self._run_phantom(prompt)

    def _run_phantom(self, prompt: str):
        """Executes task via the GUI Ghost Agent."""
        logger.info("[DualVector] Executing via Phantom Agent (Vector 2)")
        
        # 1. Scaling + Focus + Inject
        self.phantom.force_window_resize(width_percent=0.8, height_percent=0.9)
        self.phantom.force_focus()
        
        # 2. Ultra-Optimized Model Routing
        # Use Gemini 3.1 Pro (Index 1) for Planning, Claude Opus (Index 4) for Complex Code
        if "plan" in prompt.lower() or "blueprint" in prompt.lower() or "design" in prompt.lower():
            logger.info("[DualVector] Task Type: PLANNING -> Selecting Gemini 3.1 Pro")
            self.phantom.switch_model(model_index=1)
        else:
            logger.info("[DualVector] Task Type: BUILDING -> Selecting Claude Opus")
            self.phantom.switch_model(model_index=4)
            
        # 3. Inject Prompt
        # use_mouse=True for multi-monitor support
        self.phantom.inject_prompt(prompt, use_mouse=True)
        
        # 4. Watch screen for 'Accept All', 'Model Limits', and 'Crashes'
        # We wrap the Telegram alert in a lambda to handle async send
        from core.telegram_bot import send_telegram_message
        import asyncio

        def alert_mega_problem():
            msg = "⚠️ **MEGA PROBLEM DETECTED** in Antigravity!\n\nThe IDE has frozen (Spinning Wheel of Death). I clicked 'Keep Waiting' but you may need to remote in via Tailscale/Chrome Desktop."
            logger.critical(msg)
            # Fire and forget Telegram alert
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(send_telegram_message(None, msg))
            except:
                pass

        self.phantom.vision_watch_loop(
            on_limit=lambda: self.phantom._rotate_model(),
            on_done=lambda: logger.info("[DualVector] Task Completed via Phantom."),
            on_crash=alert_mega_problem,
            max_idle_seconds=600 # 10 minutes per user request
        )
