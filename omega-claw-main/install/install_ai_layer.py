#!/usr/bin/env python3
"""
install_ai_layer.py — Install AI Communication Layer into Constitution

Run this after cloning Omega Claw to make the Constitution AI-native.
Creates directories, copies protocol, updates INSTRUCTOR.xml.

Usage:
    python install_ai_layer.py [constitution_path]

If no path provided, uses default Constitution V10 location.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Default paths
DEFAULT_CONSTITUTION = os.path.expanduser(
    "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10"
)

SCRIPT_DIR = Path(__file__).parent


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           OMEGA CLAW — AI Layer Installation                 ║
║                                                              ║
║  This will make your Constitution AI-native by adding:      ║
║  • AI communication directories (inbox, outbox, state)       ║
║  • AI_PROTOCOL.xml for agent communication                   ║
║  • INSTRUCTOR.xml hook for startup detection                 ║
╚══════════════════════════════════════════════════════════════╝
""")


def create_directories(constitution_path: Path) -> bool:
    """Create AI communication directories."""
    hive_path = constitution_path / "USER SPACE" / "dev-work" / "hive"

    dirs = [
        hive_path / "ai_inbox",
        hive_path / "ai_outbox",
        hive_path / "ai_state",
        hive_path / "blockers",
        hive_path / "progress",
    ]

    print("\n📁 Creating directories...")
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ {d.relative_to(constitution_path)}")

    # Create .gitkeep files
    for d in dirs:
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    return True


def install_protocol(constitution_path: Path) -> bool:
    """Copy AI_PROTOCOL.xml to Constitution."""
    source = SCRIPT_DIR / "AI_PROTOCOL.xml"
    dest = constitution_path / "CONSTITUTION" / "AI_PROTOCOL.xml"

    if not source.exists():
        print(f"❌ AI_PROTOCOL.xml not found at {source}")
        return False

    print("\n📄 Installing AI_PROTOCOL.xml...")
    shutil.copy(source, dest)
    print(f"   ✓ Copied to {dest.relative_to(constitution_path)}")

    return True


def create_initial_state(constitution_path: Path) -> bool:
    """Create initial AGENT_STATUS.md."""
    state_dir = constitution_path / "USER SPACE" / "dev-work" / "hive" / "ai_state"
    status_file = state_dir / "AGENT_STATUS.md"

    print("\n📊 Creating initial agent state...")

    content = f"""# Agent Status

**Last Updated**: {datetime.now().isoformat()}
**State**: IDLE
**Current Job**: None
**Phase**: N/A

## Queue
(No jobs pending)

## Omega Claw
**Installed**: {datetime.now().strftime('%Y-%m-%d')}
**Status**: Ready

---
*This file is auto-managed by Omega Claw. Claude reads/writes this to track state.*
"""

    with open(status_file, 'w') as f:
        f.write(content)

    print(f"   ✓ Created {status_file.relative_to(constitution_path)}")
    return True


def update_instructor(constitution_path: Path) -> bool:
    """Add AI protocol hook to INSTRUCTOR.xml."""
    instructor_path = constitution_path / "CONSTITUTION" / "INSTRUCTOR.xml"

    if not instructor_path.exists():
        print(f"⚠️  INSTRUCTOR.xml not found at {instructor_path}")
        print("   You may need to manually add the AI protocol hook.")
        return False

    print("\n🔧 Updating INSTRUCTOR.xml...")

    with open(instructor_path, 'r') as f:
        content = f.read()

    # Check if already updated
    if "AI_PROTOCOL.xml" in content or "ai_inbox" in content:
        print("   ✓ Already has AI protocol hooks")
        return True

    # Find a good insertion point (before closing tag or at end)
    hook_xml = """
  <!-- ═══════════════════════════════════════════════════════════════ -->
  <!--                     OMEGA CLAW INTEGRATION                       -->
  <!-- ═══════════════════════════════════════════════════════════════ -->

  <omega_claw_hook>
    <description>
      Omega Claw is installed. Check for AI communication files.
    </description>

    <on_startup>
      <check_file>CONSTITUTION/AI_PROTOCOL.xml</check_file>
      <if_exists>
        <action>Read AI_PROTOCOL.xml for communication rules</action>
        <action>Check USER SPACE/dev-work/hive/ai_inbox/ for pending jobs</action>
        <action>Read USER SPACE/dev-work/hive/ai_state/AGENT_STATUS.md</action>
        <action>If pending jobs exist, start with oldest PENDING job</action>
      </if_exists>
    </on_startup>

    <communication_dirs>
      <inbox>USER SPACE/dev-work/hive/ai_inbox/</inbox>
      <outbox>USER SPACE/dev-work/hive/ai_outbox/</outbox>
      <state>USER SPACE/dev-work/hive/ai_state/</state>
      <blockers>USER SPACE/dev-work/hive/blockers/</blockers>
    </communication_dirs>

    <reporting>
      After each major phase, write a REPORT file to ai_outbox/.
      Omega Claw will send it to the user via Telegram.
    </reporting>
  </omega_claw_hook>

"""

    # Insert before closing </instructor> tag
    if "</instructor>" in content:
        content = content.replace("</instructor>", hook_xml + "</instructor>")
    elif "</constitution>" in content:
        content = content.replace("</constitution>", hook_xml + "</constitution>")
    else:
        # Just append
        content += hook_xml

    with open(instructor_path, 'w') as f:
        f.write(content)

    print("   ✓ Added Omega Claw hook to INSTRUCTOR.xml")
    return True


def create_readme(constitution_path: Path) -> bool:
    """Create README in hive directory."""
    hive_path = constitution_path / "USER SPACE" / "dev-work" / "hive"
    readme_path = hive_path / "README.md"

    content = """# Hive — AI Communication Layer

This directory enables AI-to-AI and AI-to-human communication via Omega Claw.

## Directory Structure

```
hive/
├── ai_inbox/      ← Jobs/requests FROM users TO Claude
├── ai_outbox/     ← Reports/responses FROM Claude TO users
├── ai_state/      ← Current agent status
├── blockers/      ← When Claude needs user input
└── progress/      ← Detailed progress logs
```

## How It Works

1. **User sends message** via Telegram
2. **Omega Claw** writes job to `ai_inbox/`
3. **Claude** reads inbox on startup, picks up job
4. **Claude** writes progress to `ai_outbox/`
5. **Omega Claw** reads outbox, sends to Telegram
6. **User** gets update on phone

## Files

- `AGENT_STATUS.md` — Current Claude agent state
- `JOB-*.md` — Incoming job requests
- `REPORT-*.md` — Outgoing progress reports
- `BLOCKED-*.md` — Claude needs user input
- `ANSWER-*.md` — User responses to blockers

## Protocol

See `CONSTITUTION/AI_PROTOCOL.xml` for full specification.

---
*Created by Omega Claw installation*
"""

    print("\n📝 Creating hive README...")
    with open(readme_path, 'w') as f:
        f.write(content)
    print(f"   ✓ Created {readme_path.relative_to(constitution_path)}")

    return True


def main():
    print_banner()

    # Get constitution path
    if len(sys.argv) > 1:
        constitution_path = Path(sys.argv[1]).expanduser()
    else:
        constitution_path = Path(DEFAULT_CONSTITUTION)

    print(f"📍 Constitution path: {constitution_path}")

    # Verify it exists
    if not constitution_path.exists():
        print(f"\n❌ Constitution not found at {constitution_path}")
        print("   Please provide the correct path as an argument.")
        sys.exit(1)

    # Verify it's a constitution
    if not (constitution_path / "CONSTITUTION").exists():
        print(f"\n❌ This doesn't look like a Constitution directory.")
        print(f"   Expected CONSTITUTION/ folder inside {constitution_path}")
        sys.exit(1)

    # Run installation steps
    success = True
    success = create_directories(constitution_path) and success
    success = install_protocol(constitution_path) and success
    success = create_initial_state(constitution_path) and success
    success = update_instructor(constitution_path) and success
    success = create_readme(constitution_path) and success

    if success:
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    ✅ INSTALLATION COMPLETE                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Your Constitution is now AI-native!                         ║
║                                                              ║
║  Next steps:                                                 ║
║  1. Configure Omega Claw .env file                           ║
║  2. Run: python main.py                                      ║
║  3. Message your bot on Telegram                             ║
║                                                              ║
║  Claude will now check ai_inbox/ on startup and              ║
║  communicate via the hive directory.                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    else:
        print("\n⚠️  Installation completed with warnings. Check messages above.")


if __name__ == "__main__":
    main()
