# agents/reporter_agent/__init__.py — Omega Claw
from agents.base_agent import BaseAgent
from db.database import get_all_jobs
from datetime import datetime
import os

class ReporterAgent(BaseAgent):
    """
    Reads the Omega Hive and SQLite DB to report status back to Telegram.
    """
    
    # SECURITY §3.3: Capability Matrix
    AGENT_ROLE = "Read-only reporter of Hive status and job history"
    PERMITTED_INPUTS = ["Intent commands via Orchestrator"]
    PERMITTED_OUTPUTS = ["Read master-job-board.md", "Read SQLite jobs table", "Return formatted text to Telegram"]
    FORBIDDEN_ACTIONS = ["Write files", "Delete files", "Execute commands", "Modify database", "Send network requests"]
    MAX_BLAST_RADIUS = "Read-only. Cannot modify any data. Information disclosure only."
    
    def __init__(self):
        super().__init__()
        self.hive_dir = os.path.expanduser(os.getenv(
            "OMEGA_HIVE_DIR",
            "~/Documents/Omega Constitution Pack/Omega System Public/Constution V10/USER SPACE/dev-work/hive"
        ))
    
    def _build_registry(self):
        self.registry = {
            "report:hive":    lambda **kw: self._hive_status(),
            "report:jobs":    lambda **kw: self._job_history(),
            "report:full":    lambda **kw: self._full_report(),
        }
    
    def _hive_status(self) -> str:
        board = os.path.join(self.hive_dir, "master-job-board.md")
        if not os.path.exists(board):
            return "🐝 **Hive**: Idle — no active jobs on the master board."
        with open(board, 'r') as f:
            content = f.read(600)
        return f"🐝 **Hive Status**\n\n```\n{content}\n```"
    
    def _job_history(self) -> str:
        jobs = get_all_jobs()
        if not jobs:
            return "📋 **Job History**: No jobs recorded yet."
        
        lines = []
        for job in jobs[:10]:
            icon = {"PENDING": "⏳", "BUILDING": "🔄", "COMPLETE": "✅"}.get(job["status"], "❓")
            lines.append(f"{icon} **{job['id']}** — {job['name']} ({job['status']})")
        
        return f"📋 **Job History** (last {len(lines)})\n\n" + "\n".join(lines)
    
    def _full_report(self) -> str:
        now = datetime.now().strftime('%H:%M %d/%m/%Y')
        report = f"📊 **Full Omega Report** ({now})\n\n"
        report += self._hive_status() + "\n\n"
        report += self._job_history()
        return report
