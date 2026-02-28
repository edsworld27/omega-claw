# Skills

Drop folders here to extend Omega Claw.

Each skill folder must contain:
- `skill.json` — defines name, description, intents, and handler path
- `handler.py` — the Python function that executes when the intent triggers

See `_template/` for the blueprint.

## Installing a Skill

```bash
# From omega-store
cp -r ~/omega-store/skills/database-skill ./skills/

# Or manually
mkdir skills/my-skill
# Create skill.json + handler.py following the template
```

Restart Omega Claw. The skill auto-loads on boot.
