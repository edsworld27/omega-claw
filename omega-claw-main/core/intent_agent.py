# core/intent_agent.py — Omega Claw Intent Classifier
import logging

class IntentAgent:
    """
    Lightweight keyword-based intent classifier.
    Maps natural language from Telegram to agent:action intents.
    No LLM. No AI. Just pattern matching. Free forever.
    Dynamically extended by skills on boot.
    """
    
    def __init__(self):
        self.patterns = {
            # Orchestrator Agent
            "orchestrator:build": [
                "start project", "new project", "build an app",
                "create saas", "start build", "build me",
                "create app", "new app", "build project",
                "launch project", "make me", "create project"
            ],
            "orchestrator:status": [
                "inbox", "pending", "what's pending"
            ],
            "orchestrator:cancel": [
                "cancel", "stop", "abort"
            ],
            "orchestrator:install": [
                "install", "add kit", "fetch skill", "get mcp"
            ],
            
            # Reporter Agent
            "report:hive": [
                "hive status", "hive report", "what's happening"
            ],
            "report:jobs": [
                "job history", "past jobs", "completed jobs", "show jobs"
            ],
            "report:full": [
                "full report", "complete report", "omega report",
                "status", "report"
            ],
            
            # Phantom Agent (Phase 4 — AI-to-AI Bridge)
            "phantom:prompt": [
                "prompt notebooklm", "prompt gemini", "ask the prompter",
                "reasoning step", "external ai", "prompt ai"
            ],
        }
        logging.info("IntentAgent initialized (Omega Claw)")

    def register_patterns(self, extra_patterns: dict):
        """Dynamically add intent patterns from loaded skills."""
        for intent, keywords in extra_patterns.items():
            self.patterns[intent] = keywords
            logging.info(f"IntentAgent: Registered skill intent '{intent}' ({len(keywords)} keywords)")

    def classify(self, user_text: str) -> str:
        text_lower = user_text.lower()
        for intent, keywords in self.patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                logging.info(f"IntentAgent: '{user_text}' -> {intent}")
                return intent
        logging.info(f"IntentAgent: '{user_text}' -> chat (fallback)")
        return "chat"
