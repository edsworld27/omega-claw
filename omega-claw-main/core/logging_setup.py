# core/logging_setup.py — Omega Claw (Cherry-picked from mac-commander)
import logging
import re

class RedactingFilter(logging.Filter):
    """Redacts sensitive tokens from log output."""
    
    PATTERNS = [
        (re.compile(r'(token[=:]\s*)([^\s&"]+)', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(passkey[=:]\s*)([^\s&"]+)', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(password[=:]\s*)([^\s&"]+)', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'\b\d{9,}:\w{30,}\b'), '[REDACTED_TOKEN]'),
    ]
    
    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True

def setup_logging():
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
