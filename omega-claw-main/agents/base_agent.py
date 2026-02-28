# agents/base_agent.py — Omega Claw
# SECURITY §3.3: All agents enforce a formal capability matrix.
from abc import ABC, abstractmethod
from typing import Dict, Callable, List
import logging

class BaseAgent(ABC):
    """Base class for all Omega Claw agents. Enforces SECURITY.xml §3.3."""
    
    # SECURITY §3.3: Capability Matrix — subclasses MUST define these
    AGENT_ROLE: str = "Undefined"
    PERMITTED_INPUTS: List[str] = []
    PERMITTED_OUTPUTS: List[str] = []
    FORBIDDEN_ACTIONS: List[str] = []
    MAX_BLAST_RADIUS: str = "Undefined"
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.registry: Dict[str, Callable] = {}
        self._build_registry()
        self._log_capability_matrix()
    
    @abstractmethod
    def _build_registry(self):
        pass
    
    def _log_capability_matrix(self):
        logging.info(
            f"CAPABILITY_MATRIX [{self.name}]: "
            f"role={self.AGENT_ROLE}, "
            f"inputs={self.PERMITTED_INPUTS}, "
            f"outputs={self.PERMITTED_OUTPUTS}, "
            f"blast_radius={self.MAX_BLAST_RADIUS}"
        )
    
    def can_handle(self, intent: str) -> bool:
        return intent in self.registry
    
    def execute(self, intent: str, **kwargs) -> str:
        if not self.can_handle(intent):
            return f"❌ {self.name} cannot handle: {intent}"
        try:
            return self.registry[intent](**kwargs)
        except Exception as e:
            # SECURITY §0.8: Never leak internals
            logging.error(f"{self.name} execution failed: {e}", exc_info=True)
            return f"❌ {self.name} encountered an error. Check logs."
    
    def get_available_intents(self) -> list:
        return list(self.registry.keys())
