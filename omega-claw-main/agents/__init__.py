# agents/__init__.py — Omega Claw
import logging
from agents.orchestrator_agent import OrchestratorAgent
from agents.reporter_agent import ReporterAgent
from agents.base_agent import BaseAgent

class SkillAgent(BaseAgent):
    """Lightweight wrapper that turns a loaded skill handler into an agent."""
    
    def __init__(self, skill_name: str, handlers: dict):
        self.skill_name = skill_name
        self._handlers = handlers
        super().__init__()
    
    def _build_registry(self):
        for intent, handler in self._handlers.items():
            self.registry[intent] = lambda handler=handler, **kw: handler(intent=intent, **kw)


class AgentRegistry:
    """Registry with core agents + dynamically loaded skills."""
    
    def __init__(self):
        self.agents = {}
        self._register_agents()
        self._load_skills()
    
    def _register_agents(self):
        self.agents["orchestrator"] = OrchestratorAgent()
        self.agents["report"] = ReporterAgent()
    
    def _load_skills(self):
        """Load skills and register them as lightweight agents."""
        try:
            from core.skill_loader import SkillLoader
            loader = SkillLoader()
            
            if loader.get_loaded_count() == 0:
                return
            
            # Group handlers by skill prefix (the part before the colon)
            skill_groups = {}
            for intent, handler in loader.get_skill_handlers().items():
                prefix = intent.split(":")[0] if ":" in intent else intent
                if prefix not in skill_groups:
                    skill_groups[prefix] = {}
                skill_groups[prefix][intent] = handler
            
            # Register each skill group as a SkillAgent
            for prefix, handlers in skill_groups.items():
                self.agents[prefix] = SkillAgent(prefix, handlers)
                logging.info(f"AgentRegistry: Registered skill agent '{prefix}' ({len(handlers)} intents)")
            
        except Exception as e:
            logging.error(f"AgentRegistry: Skills loading failed: {e}")
    
    def get_agent(self, agent_name: str):
        return self.agents.get(agent_name)
    
    def route_intent(self, intent: str):
        if ":" not in intent:
            return None, None
        agent_name, _ = intent.split(":", 1)
        agent = self.get_agent(agent_name)
        if agent and agent.can_handle(intent):
            return agent, intent
        return None, None
    
    def list_all_intents(self):
        return {name: agent.get_available_intents() for name, agent in self.agents.items()}
