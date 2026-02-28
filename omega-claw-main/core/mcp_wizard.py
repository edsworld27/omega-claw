# core/mcp_wizard.py — Omega Claw MCP Onboarding
import json
import os
import re
from db.database import set_wizard_state, clear_wizard_state

# The blueprint for each MCP's wizard requirements
MCP_BLUEPRINTS = {
    "supabase": {
        "name": "Supabase PostgreSQL",
        "questions": [
            {"key": "SUPABASE_URL", "prompt": "🔌 **Supabase Setup (1/2)**\n\nWhat is your `SUPABASE_URL`? (e.g. https://xyz.supabase.co)"},
            {"key": "SUPABASE_KEY", "prompt": "🔑 **Supabase Setup (2/2)**\n\nWhat is your `SUPABASE_KEY` (service_role)?\n_This will be stored in your local .env securely._"}
        ],
        "template": {
            "mcpServers": {
                "supabase": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@supabase/mcp",
                        "start"
                    ],
                    "env": {
                        "SUPABASE_URL": "{SUPABASE_URL}",
                        "SUPABASE_SERVICE_ROLE_KEY": "{SUPABASE_KEY}"
                    }
                }
            }
        }
    },
    "github": {
        "name": "GitHub",
        "questions": [
            {"key": "GITHUB_TOKEN", "prompt": "🐙 **GitHub Setup (1/1)**\n\nPlease provide your Personal Access Token (`ghp_...`)."}
        ],
        "template": {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-github"
                    ],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "{GITHUB_TOKEN}"
                    }
                }
            }
        }
    }
}

def handle_wizard_input(user_id: int, user_text: str, state: dict) -> str:
    # Check for cancel
    if user_text.lower().strip() in ["cancel", "stop", "abort"]:
        clear_wizard_state(user_id)
        return "🛑 **MCP Setup Cancelled.**"

    mcp_id = state.get("mcp_id")
    step = state.get("step", 0)
    answers = state.get("answers", {})

    blueprint = MCP_BLUEPRINTS.get(mcp_id)
    if not blueprint:
        clear_wizard_state(user_id)
        return "❌ Error: Invalid MCP blueprint requested. Wizard closed."

    questions = blueprint["questions"]

    # Save the answer for the PREVIOUS question we just asked
    if step > 0:
        prev_q = questions[step - 1]
        answers[prev_q["key"]] = user_text.strip()
    
    # Are there more questions?
    if step < len(questions):
        # Ask the NEXT question
        next_q = questions[step]
        state["step"] = step + 1
        state["answers"] = answers
        set_wizard_state(user_id, state)
        return next_q["prompt"] + "\n\n_Type `cancel` to abort._"

    # All questions answered! Generate the config.
    config_dir = os.path.expanduser("~/Documents/omega-claw/mcps")
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, f"{mcp_id}-mcp.json")
    
    # Render template
    template_str = json.dumps(blueprint["template"], indent=2)
    for k, v in answers.items():
        template_str = template_str.replace(f"{{{k}}}", v)
        
    with open(config_path, "w") as f:
        f.write(template_str)

    # Append the environment variables directly to .env for fallback compatibility
    env_path = os.path.expanduser("~/Documents/omega-claw/.env")
    try:
        with open(env_path, "a") as f:
            f.write(f"\n# Auto-configured by {mcp_id} MCP wizard\n")
            for k, v in answers.items():
                f.write(f"{k}='{v}'\n")
    except Exception as e:
        pass
        
    clear_wizard_state(user_id)
    
    return f"✅ **{blueprint['name']} MCP configured successfully!**\n\n" \
           f"The JSON config has been created and context loaded into Omega Claw.\n" \
           f"Future jobs assigned to Claude Code will now inherit this MCP."
