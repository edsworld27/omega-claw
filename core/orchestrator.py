# core/orchestrator.py — Omega Claw Message Router
"""
Routes Telegram messages directly to Claude Code via terminal bridge.
No more dumb keyword matching - real AI understanding.
"""

import logging
import os
from db.database import log_command

# Check which mode we're in
BRIDGE_MODE = os.getenv("OMEGA_BRIDGE_MODE", "true").lower() == "true"


class Orchestrator:
    """
    Routes Telegram messages to Claude Code.

    Two modes:
    - Bridge Mode (default): Messages go directly to Claude terminal
    - Legacy Mode: Simple keyword matching (fallback)
    """

    def __init__(self):
        self.bridge = None
        self.bridge_ready = False

        if BRIDGE_MODE:
            logging.info("Orchestrator: Bridge mode enabled - messages go to Claude")
        else:
            logging.info("Orchestrator: Legacy mode - keyword matching")
            self._init_legacy()

    def _init_legacy(self):
        """Initialize legacy keyword matching (fallback)."""
        from core.intent_agent import IntentAgent
        from agents import AgentRegistry

        self.intent_agent = IntentAgent()
        self.agent_registry = AgentRegistry()

        try:
            from core.skill_loader import SkillLoader
            loader = SkillLoader()
            if loader.get_loaded_count() > 0:
                self.intent_agent.register_patterns(loader.get_intent_patterns())
        except Exception as e:
            logging.warning(f"Could not load skill patterns: {e}")

    async def _ensure_bridge(self):
        """Ensure the terminal bridge is ready."""
        if self.bridge is None:
            try:
                from core.terminal_bridge import TerminalBridge
                self.bridge = TerminalBridge()
                self.bridge_ready = await self.bridge.start()

                if self.bridge_ready:
                    logging.info("Terminal bridge to Claude is ready")
                else:
                    logging.warning("Terminal bridge failed to start")
            except Exception as e:
                logging.error(f"Failed to create terminal bridge: {e}")
                self.bridge_ready = False

        return self.bridge_ready

    async def handle_message(self, user_id: int, user_text: str) -> str:
        """Route message to Claude or fallback to legacy."""
        
        # Dual-Vector Routing
        if user_text.strip().lower().startswith("/phantom"):
            # Strip command and send to Vector 2 (GUI Automation)
            intent_text = user_text[len("/phantom"):].strip()
            return await self._handle_vector2_phantom(user_id, intent_text)
            
        elif user_text.strip().lower().startswith("/stealth"):
            # Strip command and send to Vector 1 (Terminal Pexpect)
            intent_text = user_text[len("/stealth"):].strip()
            return await self._handle_vector1_stealth(user_id, intent_text)

        elif user_text.strip().lower().startswith("/prompt"):
            # Phase 4: AI-to-AI Bridge
            # Syntax: /prompt NotebookLM "How do I build a SaaS?"
            intent_text = user_text[len("/prompt"):].strip()
            return await self._handle_vector2_prompt(user_id, intent_text)

        # Try legacy mode (intent agent -> founder jobs)
        return await self._handle_legacy(user_id, user_text)

    async def _handle_vector2_prompt(self, user_id: int, user_text: str) -> str:
        """[Phase 4] The AI-to-AI Bridge. Prompts one AI, extracts output, injects into another."""
        try:
            from agents.phantom_agent import PhantomAgent
            agent = PhantomAgent()
            
            # 1. Prompt External AI (NotebookLM/Gemini)
            # Simple parse: ToolName "Instruction"
            parts = user_text.split(" ", 1)
            tool = parts[0] if len(parts) > 0 else "Gemini"
            instruction = parts[1] if len(parts) > 1 else user_text
            
            agent.prompt_external_ai(tool, instruction)
            
            # 2. Wait for AI to 'Reason' (placeholder sleep or vision loop)
            # Future: Use vision_watch_loop to detect 'Done' on the browser
            time.sleep(15) 
            
            # 3. Extract Artifact
            artifact = agent.extract_ai_artifact()
            if not artifact:
                return "❌ AI-to-AI Bridge: Failed to extract artifact from external AI."

            # 4. Inject into Antigravity
            injection_prompt = f"Using the reasoning from {tool}, please implement the following:\n\n{artifact}"
            agent.force_focus() # Back to IDE
            agent.inject_prompt(injection_prompt, use_mouse=True)
            
            log_command(user_id, f"/prompt {user_text}", "phantom:prompt", f"Bridge successful: {tool} -> Antigravity")
            return f"🌩️ **Phase 4: AI-to-AI Bridge Successful**\n\nPrompted: `{tool}`\nExtracted Reasoning: `{len(artifact)} chars`\nInjected into: `Antigravity`"
            
        except Exception as e:
            return f"❌ AI-to-AI Bridge failed: {e}"

    async def _handle_vector1_stealth(self, user_id: int, user_text: str) -> str:
        """[Vector 1] Send message directly to invisible local CLI."""
        from agents.terminal_agent import TerminalAgent
        from db.database import get_autonomy_mode
        
        mode = get_autonomy_mode(user_id)
        agent = TerminalAgent(autonomy_mode=mode)
        
        try:
            agent.send_intent(user_text)
            # Log it
            log_command(user_id, f"/stealth {user_text}", "vector1:stealth", "Stealth engine spawned.")
            return f"🥷 **Vector 1 (Stealth Engine) Engaged**\n\nPrompt injected into invisible terminal running `claude`.\nAutonomy Mode: `{mode.upper()}`"
        except Exception as e:
            return f"❌ Failed to launch Vector 1: {e}"

    async def _handle_vector2_phantom(self, user_id: int, user_text: str) -> str:
        """[Vector 2] Send message to GUI Automation wrapper to take over the Mac."""
        try:
            from agents.phantom_agent import PhantomAgent
            agent = PhantomAgent()
            # The inject prompt holds the thread while PyAutoGui types
            agent.inject_prompt(user_text)
            
            log_command(user_id, f"/phantom {user_text}", "vector2:phantom", "Phantom engine spawned.")
            return f"👻 **Vector 2 (Phantom Engine) Engaged**\n\nAntigravity desktop app successfully focused.\nPrompt physically typed and executed via `pyautogui`."
        except Exception as e:
            return f"❌ Failed to launch Vector 2: {e}\nAre the robotic dependencies installed?"

    async def _handle_legacy(self, user_id: int, user_text: str) -> str:
        """Legacy keyword-based routing."""
        import time
        start = time.time()

        intent = self.intent_agent.classify(user_text)

        if intent == "chat":
            response = (
                "🦀 **Omega Claw** — Your Constitution-governed agent dispatcher.\n\n"
                "Commands:\n"
                "• `start project` — Launch a new Omega build\n"
                "• `status` — Full Hive + job report\n"
                "• `job history` — View past builds\n"
                "• `inbox` — Check pending Founder Jobs"
            )
            log_command(user_id, user_text, "chat", response)
            return response

        agent, routed_intent = self.agent_registry.route_intent(intent)

        if not agent:
            response = f"❌ No agent for intent: `{intent}`"
            log_command(user_id, user_text, intent, response)
            return response

        response = agent.execute(routed_intent, user_text=user_text, user_id=user_id)

        elapsed = int((time.time() - start) * 1000)
        logging.info(f"Orchestrator: {intent} -> {agent.name} ({elapsed}ms)")
        log_command(user_id, user_text, intent, response[:500])

        return response
