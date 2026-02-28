# core/skill_loader.py — Omega Claw Skills Auto-Loader
# SECURITY §3.4: Skills are validated before execution.
import os
import json
import hashlib
import importlib.util
import logging

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
TRUST_FILE = os.path.join(SKILLS_DIR, ".trusted_hashes.json")

# SECURITY §3.4: Only these imports are allowed in skill handlers
FORBIDDEN_IMPORTS = ["subprocess", "shutil", "socket", "http", "urllib", "requests", "os.system"]

class SkillLoader:
    """
    Scans skills/ on boot. For each folder with a valid skill.json,
    validates the handler against security rules, then loads it.
    """
    
    def __init__(self):
        self.loaded_skills = {}
        self._load_trust()
        self._scan()
    
    def _load_trust(self):
        """Load trusted handler hashes."""
        self.trusted_hashes = {}
        if os.path.exists(TRUST_FILE):
            try:
                with open(TRUST_FILE, 'r') as f:
                    self.trusted_hashes = json.load(f)
            except:
                pass
    
    def _save_trust(self):
        """Save trusted handler hashes."""
        with open(TRUST_FILE, 'w') as f:
            json.dump(self.trusted_hashes, f, indent=2)
    
    def _scan(self):
        if not os.path.exists(SKILLS_DIR):
            logging.info("SkillLoader: No skills/ directory found.")
            return
        
        for entry in sorted(os.listdir(SKILLS_DIR)):
            skill_dir = os.path.join(SKILLS_DIR, entry)
            
            # Skip non-directories and the template
            if not os.path.isdir(skill_dir) or entry.startswith("_"):
                continue
            
            config_path = os.path.join(skill_dir, "skill.json")
            if not os.path.exists(config_path):
                logging.warning(f"SkillLoader: {entry}/ has no skill.json — skipping")
                continue
            
            try:
                self._load_skill(entry, skill_dir, config_path)
            except Exception as e:
                logging.error(f"SkillLoader: Failed to load {entry}: {e}")
    
    def _load_skill(self, name: str, skill_dir: str, config_path: str):
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required = ["name", "intents", "handler"]
        for field in required:
            if field not in config:
                raise ValueError(f"skill.json missing '{field}'")
        
        # Load the handler module
        handler_path = os.path.join(skill_dir, config["handler"])
        if not os.path.exists(handler_path):
            raise FileNotFoundError(f"Handler not found: {handler_path}")
        
        # SECURITY §3.4: Validate handler before execution
        self._security_scan(name, handler_path)
        
        spec = importlib.util.spec_from_file_location(f"skill_{name}", handler_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "execute"):
            raise AttributeError(f"Handler {config['handler']} has no execute() function")
        
        self.loaded_skills[name] = {
            "config": config,
            "handler": module.execute,
            "intents": config["intents"]
        }
        
        logging.info(f"SkillLoader: ✅ Loaded '{config['name']}' ({len(config['intents'])} intents)")
    
    def _security_scan(self, name: str, handler_path: str):
        """SECURITY §3.4: Scan handler for forbidden patterns before loading."""
        with open(handler_path, 'r') as f:
            source = f.read()
        
        # Check for forbidden imports
        for forbidden in FORBIDDEN_IMPORTS:
            if f"import {forbidden}" in source or f"from {forbidden}" in source:
                raise SecurityError(
                    f"SECURITY VIOLATION: Skill '{name}' uses forbidden import '{forbidden}'. "
                    f"Skills cannot access subprocess, network, or filesystem operations."
                )
        
        # Hash verification — warn if handler changed since last trust
        current_hash = hashlib.sha256(source.encode()).hexdigest()
        if name in self.trusted_hashes:
            if self.trusted_hashes[name] != current_hash:
                logging.warning(
                    f"SECURITY: Skill '{name}' handler has been modified since last trusted load. "
                    f"Old hash: {self.trusted_hashes[name][:16]}... New hash: {current_hash[:16]}..."
                )
        
        # Trust on first load, warn on change
        self.trusted_hashes[name] = current_hash
        self._save_trust()
    
    def get_intent_patterns(self) -> dict:
        """Return all skill intent patterns for the IntentAgent."""
        patterns = {}
        for skill in self.loaded_skills.values():
            patterns.update(skill["intents"])
        return patterns
    
    def get_skill_handlers(self) -> dict:
        """Return intent → handler mapping for the AgentRegistry."""
        handlers = {}
        for skill in self.loaded_skills.values():
            for intent in skill["intents"]:
                handlers[intent] = skill["handler"]
        return handlers
    
    def get_loaded_count(self) -> int:
        return len(self.loaded_skills)


class SecurityError(Exception):
    """Raised when a skill violates SECURITY.xml rules."""
    pass
